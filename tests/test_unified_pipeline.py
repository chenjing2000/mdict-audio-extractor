import json
import io
import sys

import pytest

from audio_extractor import app, example_audio, extractor
from audio_extractor import cli
from audio_extractor.adapter_oald import parse_headword_pronunciations
from audio_extractor.mdict_index import ResourceLocation


HTML = '''<div class="entry"><div class="webtop"><span class="phonetics">
<div geo="br"><a class="pron-uk" href="sound://gb_2.mp3"></a><span class="phon">/first-uk/</span>
<a class="pron-uk" href="sound://gb_1.mp3"></a><span class="phon">/second-uk/</span></div>
<div geo="n_am"><a class="pron-us" href="sound://us_2.wav"></a><span class="phon">/first-us/</span>
<a class="pron-us" href="sound://us_1.mp3"></a><span class="phon">/second-us/</span></div>
</span></div></div>'''


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def recite(word="Test", **extra):
    return {"word": word, "phonetic_uk": "/old-uk/", "phonetic_us": "/old-us/",
            "senses": [{"pos": "n.", "chinese_meaning": "测试", **extra}]}


@pytest.fixture
def dictionary(monkeypatch):
    class MDX:
        loads = 0

        def __init__(self, path):
            MDX.loads += 1

        def lookup_all(self, word):
            return [HTML] if word.casefold() == "test" else []

    class MDD:
        missing = set()

        def __init__(self, paths):
            pass

        def find(self, resource):
            return None if resource in MDD.missing else ResourceLocation(0, 0, resource)

        def read(self, location):
            return location.original_key.encode()

    monkeypatch.setattr(extractor, "MdxIndex", MDX)
    monkeypatch.setattr(extractor, "MddCollection", MDD)
    return MDX, MDD


def run_extract(path, **kwargs):
    return extractor.extract(mdx_path=path.parent / "dict.mdx",
                             mdd_paths=[path.parent / "dict.mdd"], wordlist_path=path, **kwargs)


def test_each_recording_keeps_its_own_ipa():
    candidates = parse_headword_pronunciations(HTML)
    assert [(c.resource, c.ipa) for c in candidates] == [
        ("gb_2.mp3", "/first-uk/"), ("gb_1.mp3", "/second-uk/"),
        ("us_2.wav", "/first-us/"), ("us_1.mp3", "/second-us/")]


def test_missing_first_recording_does_not_update_ipa_or_try_second(tmp_path, dictionary):
    dictionary[1].missing = {"gb_2.mp3"}
    path = write(tmp_path / "words.json", {"words": [recite()]})
    report = run_extract(path)
    item = json.loads(path.read_text())["words"][0]
    assert item["phonetic_uk"] == "/old-uk/"
    assert item["phonetic_us"] == "/first-us/"
    assert not (tmp_path / "words/audio/test_uk.mp3").exists()
    assert (tmp_path / "words/audio/test_us.wav").read_bytes() == b"us_2.wav"
    assert report["summary"]["phonetics_updated"] == 1


def test_existing_other_extension_skips_only_that_accent(tmp_path, dictionary):
    path = write(tmp_path / "words.json", {"words": [recite()]})
    audio = tmp_path / "words/audio"
    audio.mkdir(parents=True)
    (audio / "test_uk.wav").write_bytes(b"keep")
    report = run_extract(path)
    item = json.loads(path.read_text())["words"][0]
    assert item["phonetic_uk"] == "/old-uk/"
    assert item["phonetic_us"] == "/first-us/"
    assert (audio / "test_uk.wav").read_bytes() == b"keep"
    assert not (audio / "test_uk.mp3").exists()
    assert report["summary"]["existing_audio_skipped"] == 1
    assert report["summary"]["audio_extracted"] == 1


def test_all_existing_never_loads_dictionary_or_updates_json(tmp_path, dictionary):
    path = write(tmp_path / "words.json", {"words": [recite()]})
    before = path.read_bytes()
    audio = tmp_path / "words/audio"
    audio.mkdir(parents=True)
    for accent in ("uk", "us"):
        (audio / f"test_{accent}.mp3").write_bytes(b"existing")
    report = run_extract(path)
    assert dictionary[0].loads == 0
    assert path.read_bytes() == before
    assert report["summary"]["existing_audio_skipped"] == 2
    assert report["summary"]["words_with_uk_and_us"] == 0


def test_vocabulary_uses_root_audio_and_removes_legacy_paths(tmp_path, dictionary):
    path = write(tmp_path / "article.vocabulary.json", {"filetype": "vocabulary", "words": [
        {"word": "Test", "phonetic_uk": "/old/", "phonetic_us": "", "meanings": [],
         "audio": {"uk": "old/path"}, "source": "kept"}]})
    run_extract(path)
    assert (tmp_path / "audio/test_uk.mp3").read_bytes() == b"gb_2.mp3"
    item = json.loads(path.read_text())["words"][0]
    assert item["phonetic_uk"] == "/first-uk/" and item["source"] == "kept"
    assert "audio" not in item


def test_first_without_ipa_still_wins(tmp_path, dictionary, monkeypatch):
    monkeypatch.setattr(extractor.MdxIndex, "lookup_all", lambda self, word: [HTML.replace('<span class="phon">/first-uk/</span>', '')])
    path = write(tmp_path / "words.json", {"words": [recite()]})
    run_extract(path)
    assert (tmp_path / "words/audio/test_uk.mp3").read_bytes() == b"gb_2.mp3"
    assert json.loads(path.read_text())["words"][0]["phonetic_uk"] == "/old-uk/"


def test_directory_routes_sid_eid_and_words_separately(tmp_path, dictionary, monkeypatch):
    write(tmp_path / "recite.json", {"words": [recite(eid="01", example="Example text.")]})
    write(tmp_path / "article.vocabulary.json", {"filetype": "vocabulary", "words": [
        {"word": "Test", "meanings": []}, {"word": "missing phrase", "meanings": []}]})
    passage = write(tmp_path / "article.json", {"filetype": "passage", "next_sid": 2,
        "paragraphs": [{"paragraph": [{"sid": "s001", "text": "Passage text."}]}]})
    original = passage.read_bytes()
    write(tmp_path / "progress.json", {"application": "ReciteWords", "words": {}})
    (tmp_path / "dict.mdx").touch()
    (tmp_path / "dict.mdd").touch()

    def synthesize(text, voice, output):
        output.write_bytes(text.encode())

    monkeypatch.setattr(example_audio, "_save_tts", synthesize)
    report = app.audio_extractor(tmp_path, tmp_path / "dict.mdx", wait_seconds=0, tts_enabled=True)
    assert (tmp_path / "recite/audio_sentences/test_e01_uk.mp3").read_bytes() == b"Example text."
    assert (tmp_path / "audio_sentences/s001_us.mp3").read_bytes() == b"Passage text."
    assert (tmp_path / "audio/test_us.wav").read_bytes() == b"us_2.wav"
    assert not (tmp_path / "audio/missing_phrase_uk.mp3").exists()
    assert passage.read_bytes() == original
    assert dictionary[0].loads == 1
    assert len(report["files"]) == 3


def test_successful_recording_refreshes_even_identical_ipa(tmp_path, dictionary):
    item = recite()
    item.update(phonetic_uk="/first-uk/", phonetic_us="/first-us/")
    path = write(tmp_path / "words.json", {"words": [item]})
    report = run_extract(path)
    assert report["summary"]["phonetics_updated"] == 2


def test_missing_word_reports_each_pending_accent(tmp_path, dictionary):
    path = write(tmp_path / "words.json", {"words": [recite("absent")]})
    report = run_extract(path)
    assert [(d["accent"], d["status"]) for d in report["words"][0]["pronunciations"]] == [
        ("uk", "mdx_entry_not_found"), ("us", "mdx_entry_not_found")]


def test_write_failure_keeps_ipa_and_continues_other_accent(tmp_path, dictionary, monkeypatch):
    original_write = extractor.atomic_write

    def fail_uk(path, payload):
        if path.name.endswith("_uk.mp3"):
            raise OSError("disk failure")
        original_write(path, payload)

    monkeypatch.setattr(extractor, "atomic_write", fail_uk)
    path = write(tmp_path / "words.json", {"words": [recite()]})
    report = run_extract(path)
    item = json.loads(path.read_text())["words"][0]
    assert item["phonetic_uk"] == "/old-uk/"
    assert item["phonetic_us"] == "/first-us/"
    assert report["summary"]["audio_extracted"] == 1
    assert not (tmp_path / "words/audio/test_uk.mp3").exists()


def test_json_failure_rolls_back_new_audio_without_touching_existing(tmp_path, dictionary, monkeypatch):
    path = write(tmp_path / "words.json", {"words": [recite()]})
    before = path.read_bytes()
    audio = tmp_path / "words/audio"
    audio.mkdir(parents=True)
    (audio / "test_uk.wav").write_bytes(b"keep")

    def fail_save(*args):
        raise OSError("JSON locked")

    monkeypatch.setattr(extractor, "save_wordlist", fail_save)
    with pytest.raises(OSError, match="JSON locked"):
        run_extract(path)
    assert path.read_bytes() == before
    assert (audio / "test_uk.wav").read_bytes() == b"keep"
    assert not (audio / "test_us.wav").exists()


def test_tts_skips_existing_wav_and_only_synthesizes_missing_accent(tmp_path, monkeypatch):
    path = write(tmp_path / "passage.json", {"filetype": "passage", "next_sid": 2,
        "paragraphs": [{"paragraph": [{"sid": "s001", "text": "Only this sentence."}]}]})
    folder = tmp_path / "audio_sentences"
    folder.mkdir()
    (folder / "s001_uk.wav").write_bytes(b"keep")

    def synthesize(text, voice, output):
        output.write_bytes(text.encode())

    monkeypatch.setattr(example_audio, "_save_tts", synthesize)
    report = app.audio_extractor(path, wait_seconds=0, tts_enabled=True)
    assert report["tts"]["reused_uk"] == 1
    assert report["tts"]["generated_us"] == 1
    assert not (folder / "s001_uk.mp3").exists()
    assert (folder / "s001_us.mp3").read_bytes() == b"Only this sentence."


def test_empty_stem_and_later_collision_have_no_audio(tmp_path, dictionary, monkeypatch):
    path = write(tmp_path / "words.json", {"words": [recite("!!!", eid="01", example="No."),
        recite("Test", eid="01", example="First."), recite("Test!", eid="01", example="Later.")]})
    monkeypatch.setattr(example_audio, "_save_tts", lambda text, voice, output: output.write_bytes(text.encode()))
    (tmp_path / "dict.mdx").touch()
    (tmp_path / "dict.mdd").touch()
    report = app.audio_extractor(path, tmp_path / "dict.mdx", wait_seconds=0, tts_enabled=True)
    assert report["summary"]["empty_audio_stem"] == 1
    assert report["summary"]["audio_stem_conflict"] == 1
    assert (tmp_path / "words/audio_sentences/test_e01_us.mp3").read_bytes() == b"First."
    assert not (tmp_path / "words/audio/_uk.mp3").exists()


@pytest.mark.parametrize("uk_count,us_count", [(1, 1), (1, 2), (2, 1), (2, 3)])
def test_variant_counts_are_independent(tmp_path, dictionary, monkeypatch, uk_count, us_count):
    html = '<div class="webtop"><span class="phonetics">'
    for accent, count in (("uk", uk_count), ("us", us_count)):
        html += f'<div geo="{accent}">'
        for index in range(count):
            html += f'<a class="pron-{accent}" href="sound://{accent}_{index}.mp3"></a><span class="phon">/{accent}-{index}/</span>'
        html += '</div>'
    html += '</span></div>'
    monkeypatch.setattr(extractor.MdxIndex, "lookup_all", lambda self, word: [html])
    path = write(tmp_path / "words.json", {"words": [recite()]})
    run_extract(path)
    item = json.loads(path.read_text())["words"][0]
    for accent in ("uk", "us"):
        assert item[f"phonetic_{accent}"] == f"/{accent}-0/"
        assert (tmp_path / f"words/audio/test_{accent}.mp3").read_bytes() == f"{accent}_0.mp3".encode()


def test_late_lookup_failure_never_leaves_audio_with_stale_json(tmp_path, dictionary, monkeypatch):
    def lookup(self, word):
        if word == "later":
            raise ValueError("broken MDX record")
        return [HTML]

    monkeypatch.setattr(extractor.MdxIndex, "lookup_all", lookup)
    path = write(tmp_path / "words.json", {"words": [recite(), recite("later")]})
    original = path.read_bytes()
    with pytest.raises(ValueError, match="broken MDX"):
        run_extract(path)
    assert path.read_bytes() == original
    assert not list((tmp_path / "words/audio").glob("*"))


def test_batch_invalid_filetype_does_not_abort_valid_passage(tmp_path, monkeypatch):
    write(tmp_path / "bad.json", {"filetype": []})
    write(tmp_path / "good.json", {"filetype": "passage", "next_sid": 2,
        "paragraphs": [{"paragraph": [{"sid": "s001", "text": "Good."}]}]})
    monkeypatch.setattr(example_audio, "_save_tts", lambda text, voice, path: path.write_bytes(b"good"))
    report = app.audio_extractor(tmp_path, wait_seconds=0, tts_enabled=True)
    assert len(report["errors"]) == 1
    assert (tmp_path / "audio_sentences/s001_uk.mp3").read_bytes() == b"good"


def test_app_all_existing_words_needs_no_dictionary(tmp_path):
    path = write(tmp_path / "words.json", {"words": [recite()]})
    folder = tmp_path / "words/audio"
    folder.mkdir(parents=True)
    (folder / "test_uk.mp3").touch()
    (folder / "test_us.wav").touch()
    report = app.audio_extractor(path)
    assert report["summary"]["existing_audio_skipped"] == 2


def test_default_tts_off_preserves_dictionary_extraction_and_ipa(tmp_path, dictionary, monkeypatch):
    path = write(tmp_path / "words.json", {"words": [recite(eid="01", example="Hello.")]})
    (tmp_path / "dict.mdx").touch()
    (tmp_path / "dict.mdd").touch()

    def forbidden(*args, **kwargs):
        pytest.fail("disabled TTS entered generation")

    monkeypatch.setattr(app, "example_audio_synthesis", forbidden)
    report = app.audio_extractor(path, tmp_path / "dict.mdx")
    assert report["summary"]["audio_extracted"] == 2
    assert report["summary"]["phonetics_updated"] == 2
    item = json.loads(path.read_text())["words"][0]
    assert item["phonetic_uk"] == "/first-uk/"
    assert item["phonetic_us"] == "/first-us/"
    assert (tmp_path / "words/audio/test_uk.mp3").read_bytes() == b"gb_2.mp3"
    assert not (tmp_path / "words/audio_sentences").exists()
    assert report["tts"]["enabled"] is False


def test_ipa_update_does_not_fail_on_windows_gbk_console(tmp_path, dictionary, monkeypatch):
    html = HTML.replace("/first-uk/", "/zuˈɒlədʒi/")
    monkeypatch.setattr(extractor.MdxIndex, "lookup_all", lambda self, word: [html])
    path = write(tmp_path / "words.json", {"words": [recite()]})
    with io.TextIOWrapper(io.BytesIO(), encoding="gbk") as console:
        monkeypatch.setattr(sys, "stdout", console)
        run_extract(path)
    assert json.loads(path.read_text(encoding="utf-8"))["words"][0]["phonetic_uk"] == "/zuˈɒlədʒi/"


def test_cli_tts_failure_has_nonzero_exit_and_no_partial_audio(tmp_path, monkeypatch):
    path = write(tmp_path / "passage.json", {"filetype": "passage", "next_sid": 2,
        "paragraphs": [{"paragraph": [{"sid": "s001", "text": "Test."}]}]})

    def fail_tts(text, voice, output):
        output.write_bytes(b"partial")
        raise RuntimeError("connection unavailable")

    monkeypatch.setattr(example_audio, "_save_tts", fail_tts)
    monkeypatch.setattr(sys, "argv", ["audio_extractor", "--wordlist", str(path), "--wait-seconds", "0", "--tts"])
    with pytest.raises(SystemExit) as exited:
        cli.main()
    assert exited.value.code == 1
    assert not list((tmp_path / "audio_sentences").glob("*"))


def test_cli_unsupported_dictionary_format_fails_without_changing_ipa(tmp_path, dictionary, monkeypatch, capsys):
    path = write(tmp_path / "words.json", {"words": [recite()]})
    before = path.read_bytes()
    (tmp_path / "dict.mdx").touch()
    html = HTML.replace(".mp3", ".ogg").replace(".wav", ".ogg")
    monkeypatch.setattr(extractor.MdxIndex, "lookup_all", lambda self, word: [html])
    monkeypatch.setattr(sys, "argv", ["audio_extractor", "--wordlist", str(path),
        "--mdx", str(tmp_path / "dict.mdx")])
    with pytest.raises(SystemExit) as exited:
        cli.main()
    assert exited.value.code == 1
    assert "不支持的词典音频格式" in capsys.readouterr().out
    assert path.read_bytes() == before
    assert not list((tmp_path / "words/audio").glob("*"))

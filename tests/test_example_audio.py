import json
import sys

from mdict_audio_extractor import example_audio


def _sense(example=None, eid=None):
    sense = {"pos": "n.", "chinese_meaning": "测试"}
    if eid is not None:
        sense["eid"] = eid
    if example is not None:
        sense["example"] = example
    return sense


def _word(word, senses):
    return {
        "word": word,
        "phonetic_uk": "",
        "phonetic_us": "",
        "senses": senses,
    }


def _write_wordlist(path, words):
    path.write_text(json.dumps({"schema_version": 2, "words": words}), encoding="utf-8")


def _install_fake_edge_tts(monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", object())


def test_examples_use_eid_in_filename_and_no_examples_json(tmp_path, monkeypatch):
    wordlist = tmp_path / "IELTS_Band7_WordList.json"
    _write_wordlist(
        wordlist,
        [
            _word(
                "articulate",
                [
                    _sense(
                        "She was able to articulate her concerns effectively during the meeting.",
                        "01",
                    ),
                    _sense("He is a highly articulate speaker.", "02"),
                ],
            )
        ],
    )
    _install_fake_edge_tts(monkeypatch)

    generated = []

    def fake_save(text, voice, output_path):
        generated.append(output_path.name)
        output_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    resource_dir = tmp_path / "IELTS_Band7_WordList"
    examples_dir = resource_dir / "examples"

    assert summary["examples"] == 2
    assert summary["generated_uk"] == 2
    assert summary["generated_us"] == 2
    assert len(generated) == 4
    assert (examples_dir / "articulate_e01_uk.mp3").is_file()
    assert (examples_dir / "articulate_e01_us.mp3").is_file()
    assert (examples_dir / "articulate_e02_uk.mp3").is_file()
    assert (examples_dir / "articulate_e02_us.mp3").is_file()
    assert not (resource_dir / "examples.json").exists()


def test_existing_example_audio_is_reused(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    _write_wordlist(wordlist, [_word("test", [_sense("Example.", "01")])])
    _install_fake_edge_tts(monkeypatch)

    calls = []

    def fake_save(text, voice, output_path):
        calls.append(output_path.name)
        output_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)
    first = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)
    assert first["generated_uk"] == 1
    assert first["generated_us"] == 1

    def should_not_run(*args, **kwargs):
        raise AssertionError("existing audio should be reused")

    monkeypatch.setattr(example_audio, "_save_tts", should_not_run)
    second = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)
    assert second["reused_uk"] == 1
    assert second["reused_us"] == 1


def test_example_without_eid_is_skipped(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    _write_wordlist(wordlist, [_word("test word", [_sense("This example has no eid.")])])
    _install_fake_edge_tts(monkeypatch)

    def should_not_run(*args, **kwargs):
        raise AssertionError("example without eid must not synthesize audio")

    monkeypatch.setattr(example_audio, "_save_tts", should_not_run)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["examples"] == 0
    assert summary["missing_eid_skipped"] == 1
    assert not (tmp_path / "wordlist" / "examples" / "test_word_e01_uk.mp3").exists()


def test_stem_conflict_skips_all_later_word_example_audio(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    _write_wordlist(
        wordlist,
        [
            _word("well-being", [_sense("First.", "01")]),
            _word("well being", [_sense("Conflict.", "01")]),
            _word("final", [_sense("Final.", "01")]),
        ],
    )
    _install_fake_edge_tts(monkeypatch)

    def fake_save(text, voice, output_path):
        output_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["stem_conflicts_skipped"] == 1
    assert summary["stem_conflict_examples_skipped"] == 1
    assert summary["examples"] == 2

    examples_dir = tmp_path / "wordlist" / "examples"
    assert (examples_dir / "well_being_e01_uk.mp3").is_file()
    assert (examples_dir / "final_e01_us.mp3").is_file()


def test_first_stem_owner_keeps_ownership_even_if_tts_fails(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    _write_wordlist(
        wordlist,
        [
            _word("well-being", [_sense("First.", "01")]),
            _word("well being", [_sense("Second.", "01")]),
        ],
    )
    _install_fake_edge_tts(monkeypatch)

    attempted_texts = []

    def always_fail(text, voice, output_path):
        attempted_texts.append(text)
        raise RuntimeError("tts failed")

    monkeypatch.setattr(example_audio, "_save_tts", always_fail)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["failed"] == 2
    assert summary["stem_conflicts_skipped"] == 1
    assert set(attempted_texts) == {"First."}

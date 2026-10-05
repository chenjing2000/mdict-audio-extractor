import json

from mdict_audio_extractor import extractor


def _sense():
    return {"pos": "n.", "chinese_meaning": "测试"}


def _word(word, uk="", us=""):
    return {
        "word": word,
        "phonetic_uk": uk,
        "phonetic_us": us,
        "senses": [_sense()],
    }


def test_extract_updates_dual_phonetics_from_mdx(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps({"schema_version": 2, "words": [_word("test", "/old-uk/", "/old-us/")]}),
        encoding="utf-8",
    )

    html = """
    <div class="entry"><div class="webtop"><span class="phonetics">
      <div geo="br"><a href="sound://test__gb_1.mp3" class="pron-uk"></a><span class="phon">/new-uk/</span></div>
      <div geo="n_am"><a href="sound://test__us_1.mp3" class="pron-us"></a><span class="phon">/new-us/</span></div>
    </span></div></div>
    """

    class FakeMdxIndex:
        def __init__(self, path):
            pass

        def lookup_all(self, word):
            return [html]

    class FakeMddCollection:
        def __init__(self, paths):
            pass

        def find(self, resource):
            return None

    monkeypatch.setattr(extractor, "MdxIndex", FakeMdxIndex)
    monkeypatch.setattr(extractor, "MddCollection", FakeMddCollection)

    output_dir = tmp_path / "wordlist"
    report = extractor.extract(
        mdx_path=tmp_path / "dictionary.mdx",
        mdd_paths=[],
        wordlist_path=wordlist,
        output_dir=output_dir,
    )

    data = json.loads(wordlist.read_text(encoding="utf-8"))
    assert data["words"][0]["phonetic_uk"] == "/new-uk/"
    assert data["words"][0]["phonetic_us"] == "/new-us/"
    assert report["summary"]["phonetics_updated"] == 2
    assert not (output_dir / "audio.json").exists()
    assert not (output_dir / "report.json").exists()


def test_later_audio_stem_collision_is_skipped_not_fatal(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "words": [
                    _word("well-being"),
                    _word("well being"),
                    _word("next"),
                ]
            }
        ),
        encoding="utf-8",
    )

    looked_up = []

    class FakeMdxIndex:
        def __init__(self, path):
            pass

        def lookup_all(self, word):
            looked_up.append(word)
            return []

    class FakeMddCollection:
        def __init__(self, paths):
            pass

    monkeypatch.setattr(extractor, "MdxIndex", FakeMdxIndex)
    monkeypatch.setattr(extractor, "MddCollection", FakeMddCollection)

    report = extractor.extract(
        mdx_path=tmp_path / "dictionary.mdx",
        mdd_paths=[],
        wordlist_path=wordlist,
        output_dir=tmp_path / "out",
    )

    assert looked_up == ["well-being", "next"]
    assert report["summary"]["audio_stem_conflict"] == 1
    conflict = next(item for item in report["words"] if item["status"] == "audio_stem_conflict")
    assert conflict["word"] == "well being"
    assert conflict["audio_stem"] == "well_being"
    assert conflict["conflict_with"] == "well-being"


def test_later_duplicate_word_is_skipped_not_fatal(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "words": [
                    _word("lead"),
                    _word("LEAD"),
                    _word("next"),
                ]
            }
        ),
        encoding="utf-8",
    )

    looked_up = []

    class FakeMdxIndex:
        def __init__(self, path):
            pass

        def lookup_all(self, word):
            looked_up.append(word)
            return []

    class FakeMddCollection:
        def __init__(self, paths):
            pass

    monkeypatch.setattr(extractor, "MdxIndex", FakeMdxIndex)
    monkeypatch.setattr(extractor, "MddCollection", FakeMddCollection)

    report = extractor.extract(
        mdx_path=tmp_path / "dictionary.mdx",
        mdd_paths=[],
        wordlist_path=wordlist,
        output_dir=tmp_path / "out",
    )

    assert looked_up == ["lead", "next"]
    assert report["summary"]["duplicate_word"] == 1
    duplicate = next(item for item in report["words"] if item["status"] == "duplicate_word")
    assert duplicate["word"] == "LEAD"
    assert duplicate["duplicate_of"] == "lead"

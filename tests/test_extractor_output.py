import json

from mdict_audio_extractor import extractor


def test_extract_writes_audio_json_but_not_report_json(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [{"wid": "test", "word": "test"}],
            }
        ),
        encoding="utf-8",
    )

    class FakeMdxIndex:
        def __init__(self, path):
            pass

        def lookup_all(self, word):
            return []

    class FakeMddCollection:
        def __init__(self, paths):
            pass

    monkeypatch.setattr(extractor, "MdxIndex", FakeMdxIndex)
    monkeypatch.setattr(extractor, "MddCollection", FakeMddCollection)

    output_dir = tmp_path / "wordlist"
    report = extractor.extract(
        mdx_path=tmp_path / "dictionary.mdx",
        mdd_paths=[],
        wordlist_path=wordlist,
        output_dir=output_dir,
    )

    assert (output_dir / "audio.json").is_file()
    assert not (output_dir / "report.json").exists()
    assert report["summary"]["requested_words"] == 1

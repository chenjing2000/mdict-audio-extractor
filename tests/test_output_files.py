import json
from pathlib import Path

from mdict_audio_extractor import extractor


class FakeMdxIndex:
    def __init__(self, _path: Path):
        pass

    def lookup_all(self, _word: str) -> list[str]:
        return []


class FakeMddCollection:
    def __init__(self, _paths: list[Path]):
        pass


def test_extract_writes_audio_json_not_pronunciation_json(tmp_path, monkeypatch):
    wordlist_path = tmp_path / "words.json"
    wordlist_path.write_text("{}", encoding="utf-8")
    mdx_path = tmp_path / "dict.mdx"
    mdd_path = tmp_path / "dict.mdd"

    monkeypatch.setattr(extractor, "load_words", lambda _path: ["apple"])
    monkeypatch.setattr(extractor, "MdxIndex", FakeMdxIndex)
    monkeypatch.setattr(extractor, "MddCollection", FakeMddCollection)

    extractor.extract(
        mdx_path=mdx_path,
        mdd_paths=[mdd_path],
        wordlist_path=wordlist_path,
        output_dir=tmp_path,
    )

    audio_json = tmp_path / "audio.json"
    assert audio_json.is_file()
    assert not (tmp_path / "pronunciation.json").exists()

    data = json.loads(audio_json.read_text(encoding="utf-8"))
    assert data == {"schema_version": 1, "words": {}}

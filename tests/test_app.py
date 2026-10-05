import pytest

from mdict_audio_extractor import app


def test_limit_must_be_positive(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    mdx = tmp_path / "dictionary.mdx"
    mdd = tmp_path / "dictionary.mdd"
    wordlist.write_text('{"words": []}', encoding="utf-8")
    mdx.write_bytes(b"")
    mdd.write_bytes(b"")

    with pytest.raises(ValueError, match="limit"):
        app.mdict_audio_extractor(wordlist, mdx, mdd, limit=0)

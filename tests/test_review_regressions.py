import importlib.util
import json
import io
import sys

import pytest

from audio_extractor import app, example_audio


def test_new_package_name_is_importable():
    assert importlib.util.find_spec("audio_extractor") is not None


@pytest.mark.parametrize("wait_seconds", [0, 0.01])
def test_tts_retries_after_first_failure_regardless_of_wait(tmp_path, monkeypatch, wait_seconds):
    path = tmp_path / "passage.json"
    path.write_text(json.dumps({"filetype": "passage", "next_sid": 2,
        "paragraphs": [{"paragraph": [{"sid": "s001", "text": "Retry this sentence."}]}]}), encoding="utf-8")
    attempts = {}

    def fail_once(text, voice, output):
        attempts[voice] = attempts.get(voice, 0) + 1
        if attempts[voice] == 1:
            output.write_bytes(b"partial")
            raise RuntimeError("temporary failure")
        output.write_bytes(b"complete recording")

    monkeypatch.setattr(example_audio, "_save_tts", fail_once)
    report = example_audio.example_audio_synthesis(path, wait_seconds=wait_seconds)
    assert report["failed"] == 0
    assert (tmp_path / "audio_sentences/s001_uk.mp3").read_bytes() == b"complete recording"
    assert (tmp_path / "audio_sentences/s001_us.mp3").read_bytes() == b"complete recording"


def test_corrupt_dictionary_does_not_block_later_passage(tmp_path, monkeypatch):
    (tmp_path / "a_words.json").write_text(json.dumps({"words": [{"word": "test", "phonetic_uk": "",
        "phonetic_us": "", "senses": [{"pos": "n.", "chinese_meaning": "测试"}]}]}), encoding="utf-8")
    (tmp_path / "b_passage.json").write_text(json.dumps({"filetype": "passage", "next_sid": 2,
        "paragraphs": [{"paragraph": [{"sid": "s001", "text": "Still generate this sentence."}]}]}), encoding="utf-8")
    mdx = tmp_path / "corrupt.mdx"
    mdx.touch()
    monkeypatch.setattr(example_audio, "_save_tts", lambda text, voice, path: path.write_bytes(b"generated"))
    report = app.audio_extractor(tmp_path, mdx, wait_seconds=0)
    assert len(report["errors"]) == 1
    assert "corrupt.mdx" in report["errors"][0]["error"]
    assert (tmp_path / "audio_sentences/s001_uk.mp3").read_bytes() == b"generated"


def test_gbk_console_handles_unicode_filenames_words_and_sentences(tmp_path, monkeypatch):
    path = tmp_path / "cœur.json"
    sentence = "An œuvre is an artist's body of work."
    path.write_text(json.dumps({"words": [{"word": "œuvre", "phonetic_uk": "", "phonetic_us": "",
        "senses": [{"pos": "n.", "chinese_meaning": "作品", "eid": "01", "example": sentence}]}]}), encoding="utf-8")
    folder = tmp_path / "cœur/audio"
    folder.mkdir(parents=True)
    for accent in ("uk", "us"):
        (folder / f"uvre_{accent}.mp3").write_bytes(b"existing")
    monkeypatch.setattr(example_audio, "_save_tts", lambda text, voice, output: output.write_bytes(text.encode("utf-8")))
    with io.TextIOWrapper(io.BytesIO(), encoding="gbk") as console:
        monkeypatch.setattr(sys, "stdout", console)
        report = app.audio_extractor(path, wait_seconds=0)
    assert report["tts"]["generated_uk"] == 1
    assert (tmp_path / "cœur/audio_sentences/uvre_e01_us.mp3").read_bytes() == sentence.encode("utf-8")

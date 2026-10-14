import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from audio_extractor import app, cli, example_audio, reporting


def test_tts_uses_default_communicate_connection(tmp_path, monkeypatch):
    path = passage(tmp_path)
    calls = []

    class Communicate:
        def __init__(self, text, voice):
            calls.append((text, voice))

        def save_sync(self, output):
            Path(output).write_bytes(b"audio")

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=Communicate))
    report = app.audio_extractor(path, tts_enabled=True, wait_seconds=0)
    assert report["tts"]["generated_uk"] == report["tts"]["generated_us"] == 1
    assert calls == [("Hello.", "en-GB-SoniaNeural"), ("Hello.", "en-US-JennyNeural")]


def passage(tmp_path):
    path = tmp_path / "passage.json"
    path.write_text(json.dumps({"filetype": "passage", "next_sid": 2,
        "paragraphs": [{"paragraph": [{"sid": "s001", "text": "Hello."}]}]}), encoding="utf-8")
    return path


@pytest.mark.parametrize("explicit", [False, True])
def test_disabled_tts_never_enters_generation(tmp_path, monkeypatch, capsys, explicit):
    path = passage(tmp_path)
    before = path.read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("disabled TTS entered generation")

    monkeypatch.setattr(app, "example_audio_synthesis", forbidden)
    options = {"tts_enabled": False} if explicit else {}
    report = app.audio_extractor(path, **options)
    assert report["tts"] == {"enabled": False, "generated_uk": 0,
        "generated_us": 0, "reused_uk": 0, "reused_us": 0, "failed": 0}
    assert not reporting.has_failures(report)
    assert list(tmp_path.iterdir()) == [path]
    assert path.read_bytes() == before
    assert "TTS：已关闭" in capsys.readouterr().out


def test_disabled_tts_still_validates_passage(tmp_path):
    path = passage(tmp_path)
    data = json.loads(path.read_text())
    data["next_sid"] = 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="next_sid"):
        app.audio_extractor(path)
    assert not (tmp_path / "audio_sentences").exists()


@pytest.mark.parametrize("enabled", [False, True])
def test_cli_switch_matches_function(tmp_path, monkeypatch, capsys, enabled):
    path = passage(tmp_path)
    monkeypatch.setattr(example_audio, "_save_tts",
        lambda text, voice, output: output.write_bytes(b"audio"))
    argv = ["audio_extractor", "--wordlist", str(path)]
    if enabled:
        argv.append("--tts")
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    output = capsys.readouterr().out
    assert "{'" not in output
    if enabled:
        assert "TTS：\n生成成功：2\n已有跳过：0\n生成失败：0" in output
        assert len(list((tmp_path / "audio_sentences").glob("*.mp3"))) == 2
    else:
        assert "TTS：已关闭" in output
        assert not (tmp_path / "audio_sentences").exists()


def test_dictionary_console_counts_files_separately(capsys):
    words = [{"status": "partial", "pronunciations": [
        {"status": "extracted"}, {"status": "mdd_resource_not_found"}]},
        {"status": "partial", "pronunciations": [
        {"status": "existing_audio_skipped"}, {"status": "audio_write_failed"}]}]
    report = {"summary": reporting.summarize_words(words, 1, [], []),
        "words": words, "tts": {"enabled": False}}
    reporting.print_report(report)
    assert capsys.readouterr().out == (
        "词典音频：\n提取成功：1\n已有跳过：1\n缺失：1\n失败：1\nTTS：已关闭\n")

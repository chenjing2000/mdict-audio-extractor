import json
import sys

import pytest

from mdict_audio_extractor import example_audio


def _write_wordlist(
    path,
    second_sentence="He is a highly articulate speaker.",
    second_eid="654321",
):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [
                    {
                        "wid": "articulate",
                        "word": "articulate",
                        "senses": [
                            {
                                "pos": "v.",
                                "eid": "123456",
                                "example": (
                                    "She was able to articulate her concerns "
                                    "effectively during the meeting."
                                ),
                            },
                            {"pos": "n."},
                            {
                                "pos": "adj.",
                                "eid": second_eid,
                                "example": second_sentence,
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_generates_examples_with_eid_and_reuses_existing_audio(tmp_path, monkeypatch):
    wordlist = tmp_path / "IELTS_Band7_WordList.json"
    _write_wordlist(wordlist)
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    generated = []

    def fake_save(text, voice, output_path):
        generated.append((text, voice, output_path.name))
        output_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)

    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    resource_dir = tmp_path / "IELTS_Band7_WordList"
    data = json.loads((resource_dir / "examples.json").read_text(encoding="utf-8"))

    assert summary["examples"] == 2
    assert summary["generated_uk"] == 2
    assert summary["generated_us"] == 2
    assert summary["skipped_invalid_eid"] == 0
    assert summary["failed"] == 0
    assert len(generated) == 4

    assert data["words"]["articulate"] == [
        {
            "eid": "123456",
            "text": (
                "She was able to articulate her concerns effectively during the meeting."
            ),
            "uk": "examples/articulate_e01_uk.mp3",
            "us": "examples/articulate_e01_us.mp3",
        },
        {
            "eid": "654321",
            "text": "He is a highly articulate speaker.",
            "uk": "examples/articulate_e02_uk.mp3",
            "us": "examples/articulate_e02_us.mp3",
        },
    ]

    assert (resource_dir / "examples" / "articulate_e01_uk.mp3").is_file()
    assert (resource_dir / "examples" / "articulate_e02_us.mp3").is_file()

    def should_not_run(*args, **kwargs):
        raise AssertionError("existing unchanged audio should be reused")

    monkeypatch.setattr(example_audio, "_save_tts", should_not_run)
    second = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert second["generated_uk"] == 0
    assert second["generated_us"] == 0
    assert second["reused_uk"] == 2
    assert second["reused_us"] == 2


def test_regenerated_example_with_new_eid_generates_new_audio(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    _write_wordlist(wordlist)
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    def fake_save(text, voice, output_path):
        output_path.write_bytes(text.encode("utf-8"))

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)
    example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    new_sentence = "He is an articulate and persuasive speaker."
    _write_wordlist(
        wordlist,
        second_sentence=new_sentence,
        second_eid="777777",
    )

    generated = []

    def record_save(text, voice, output_path):
        generated.append((text, voice, output_path.name))
        output_path.write_bytes(text.encode("utf-8"))

    monkeypatch.setattr(example_audio, "_save_tts", record_save)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["reused_uk"] == 1
    assert summary["reused_us"] == 1
    assert summary["generated_uk"] == 1
    assert summary["generated_us"] == 1
    assert len(generated) == 2
    assert all(item[0] == new_sentence for item in generated)

    data = json.loads(
        (tmp_path / "wordlist" / "examples.json").read_text(encoding="utf-8")
    )
    assert data["words"]["articulate"][1]["eid"] == "777777"


def test_example_without_valid_eid_is_skipped(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [
                    {
                        "wid": "test",
                        "word": "test",
                        "senses": [
                            {"example": "This example has no eid."},
                            {
                                "eid": "12x456",
                                "example": "This example has a wrong eid.",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    def should_not_run(*args, **kwargs):
        raise AssertionError("invalid eid examples must not be synthesized")

    monkeypatch.setattr(example_audio, "_save_tts", should_not_run)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["examples"] == 0
    assert summary["skipped_invalid_eid"] == 2
    data = json.loads(
        (tmp_path / "wordlist" / "examples.json").read_text(encoding="utf-8")
    )
    assert data == {"schema_version": 1, "words": {}}


def test_eid_may_start_with_zero(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    _write_wordlist(wordlist, second_eid="001234")
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    def fake_save(text, voice, output_path):
        output_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["examples"] == 2
    data = json.loads(
        (tmp_path / "wordlist" / "examples.json").read_text(encoding="utf-8")
    )
    assert data["words"]["articulate"][1]["eid"] == "001234"


def test_duplicate_eid_is_rejected(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [
                    {
                        "wid": "test",
                        "word": "test",
                        "senses": [
                            {"eid": "123456", "example": "First."},
                            {"eid": "123456", "example": "Second."},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    with pytest.raises(ValueError, match="eid 重复"):
        example_audio.example_audio_synthesis(wordlist, wait_seconds=0)


def test_duplicate_word_is_rejected_case_insensitively(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [
                    {
                        "wid": "lead_1",
                        "word": "lead",
                        "senses": [{"eid": "111111", "example": "First."}],
                    },
                    {
                        "wid": "lead_2",
                        "word": "LEAD",
                        "senses": [{"eid": "222222", "example": "Second."}],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    with pytest.raises(ValueError, match="word 重复"):
        example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

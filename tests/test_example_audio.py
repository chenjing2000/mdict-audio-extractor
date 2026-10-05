import json
import sys

from mdict_audio_extractor import example_audio


def _write_wordlist(path, second_sentence="He is a highly articulate speaker."):
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "words": [
                    {
                        "word": "articulate",
                        "phonetic_uk": "/ɑːˈtɪkjuleɪt/",
                        "phonetic_us": "/ɑːrˈtɪkjuleɪt/",
                        "senses": [
                            {
                                "pos": "v.",
                                "chinese_meaning": "清晰表达",
                                "eid": "123456",
                                "example": (
                                    "She was able to articulate her concerns "
                                    "effectively during the meeting."
                                ),
                            },
                            {"pos": "n.", "chinese_meaning": "测试义"},
                            {
                                "pos": "adj.",
                                "chinese_meaning": "表达清晰的",
                                "eid": "654321",
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


def test_generates_word_stem_local_ids_and_reuses_existing_audio(tmp_path, monkeypatch):
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
    assert len(generated) == 4

    assert data == {
        "schema_version": 2,
        "words": {
            "articulate": [
                {
                    "id": "01",
                    "text": "She was able to articulate her concerns effectively during the meeting.",
                    "uk": "examples/articulate_e01_uk.mp3",
                    "us": "examples/articulate_e01_us.mp3",
                },
                {
                    "id": "02",
                    "text": "He is a highly articulate speaker.",
                    "uk": "examples/articulate_e02_uk.mp3",
                    "us": "examples/articulate_e02_us.mp3",
                },
            ]
        },
    }

    assert (resource_dir / "examples" / "articulate_e01_uk.mp3").is_file()
    assert (resource_dir / "examples" / "articulate_e02_us.mp3").is_file()

    def should_not_run(*args, **kwargs):
        raise AssertionError("existing unchanged audio should be reused")

    monkeypatch.setattr(example_audio, "_save_tts", should_not_run)
    second = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)
    assert second["reused_uk"] == 2
    assert second["reused_us"] == 2


def test_example_without_eid_is_still_synthesized(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "words": [
                    {
                        "word": "test word",
                        "phonetic_uk": "",
                        "phonetic_us": "",
                        "senses": [
                            {
                                "pos": "n.",
                                "chinese_meaning": "测试",
                                "example": "This example has no eid.",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    def fake_save(text, voice, output_path):
        output_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["examples"] == 1
    assert (tmp_path / "wordlist" / "examples" / "test_word_e01_uk.mp3").is_file()


def test_duplicate_word_and_stem_conflict_are_skipped_but_processing_continues(tmp_path, monkeypatch):
    wordlist = tmp_path / "wordlist.json"
    wordlist.write_text(
        json.dumps(
            {
                "words": [
                    {
                        "word": "well-being",
                        "phonetic_uk": "",
                        "phonetic_us": "",
                        "senses": [{"pos": "n.", "chinese_meaning": "A", "example": "First."}],
                    },
                    {
                        "word": "well being",
                        "phonetic_uk": "",
                        "phonetic_us": "",
                        "senses": [{"pos": "n.", "chinese_meaning": "B", "example": "Conflict."}],
                    },
                    {
                        "word": "NEXT",
                        "phonetic_uk": "",
                        "phonetic_us": "",
                        "senses": [{"pos": "n.", "chinese_meaning": "C", "example": "Next first."}],
                    },
                    {
                        "word": "next",
                        "phonetic_uk": "",
                        "phonetic_us": "",
                        "senses": [{"pos": "n.", "chinese_meaning": "D", "example": "Duplicate."}],
                    },
                    {
                        "word": "final",
                        "phonetic_uk": "",
                        "phonetic_us": "",
                        "senses": [{"pos": "n.", "chinese_meaning": "E", "example": "Final."}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(sys.modules, "edge_tts", object())

    def fake_save(text, voice, output_path):
        output_path.write_bytes(b"fake mp3")

    monkeypatch.setattr(example_audio, "_save_tts", fake_save)
    summary = example_audio.example_audio_synthesis(wordlist, wait_seconds=0)

    assert summary["duplicate_words_skipped"] == 1
    assert summary["duplicate_word_examples_skipped"] == 1
    assert summary["stem_conflicts_skipped"] == 1
    assert summary["stem_conflict_examples_skipped"] == 1
    assert summary["examples"] == 3

    examples_dir = tmp_path / "wordlist" / "examples"
    assert (examples_dir / "well_being_e01_uk.mp3").is_file()
    assert not (examples_dir / "well_being_e02_uk.mp3").exists()
    assert (examples_dir / "NEXT_e01_uk.mp3").is_file()
    assert (examples_dir / "final_e01_us.mp3").is_file()

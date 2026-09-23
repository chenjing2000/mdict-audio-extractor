import json

import pytest

from mdict_audio_extractor.wordlist import WordListError, load_words


def test_current_words_review_schema(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "demo",
                "description": "",
                "words": [
                    {
                        "wid": "apple",
                        "word": "apple",
                        "phonetic": "/ˈæpl/",
                        "senses": [],
                    },
                    {
                        "wid": "ubiquitous",
                        "word": "ubiquitous",
                        "phonetic": "/juːˈbɪkwɪtəs/",
                        "senses": [],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert load_words(path) == ["apple", "ubiquitous"]


def test_old_id_field_is_not_accepted(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [{"id": "apple", "word": "apple"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(WordListError, match="wid"):
        load_words(path)


def test_duplicate_word_is_rejected_case_insensitively(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [
                    {"wid": "lead_1", "word": "lead"},
                    {"wid": "lead_2", "word": "LEAD"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(WordListError, match="word.*重复"):
        load_words(path)

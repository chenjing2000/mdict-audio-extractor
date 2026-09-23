import json

from mdict_audio_extractor.wordlist import load_words


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
                        "id": "apple",
                        "word": "apple",
                        "phonetic": "/ˈæpl/",
                        "senses": [],
                    },
                    {
                        "id": "ubiquitous",
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

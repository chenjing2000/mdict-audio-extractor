import json

import pytest

from mdict_audio_extractor.wordlist import (
    WordListError,
    audio_stem,
    find_word_conflicts,
    load_wordlist,
)


def _sense(**extra):
    value = {"pos": "n.", "chinese_meaning": "测试"}
    value.update(extra)
    return value


def _word(word, *, eid=None):
    sense = _sense()
    if eid is not None:
        sense["eid"] = eid
    return {
        "word": word,
        "phonetic_uk": "",
        "phonetic_us": "",
        "senses": [sense],
    }


def test_current_dual_phonetic_schema_without_wid(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "words": [
                    _word("apple", eid="001234"),
                    _word("ubiquitous"),
                ],
            }
        ),
        encoding="utf-8",
    )

    data = load_wordlist(path)
    assert [item["word"] for item in data["words"]] == ["apple", "ubiquitous"]


def test_legacy_single_phonetic_schema_is_rejected(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "words": [
                    {
                        "word": "apple",
                        "phonetic": "/ˈæpl/",
                        "senses": [_sense()],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(WordListError, match="phonetic_uk"):
        load_wordlist(path)


def test_duplicate_word_is_valid_and_reported_as_runtime_conflict(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps(
            {
                "words": [
                    _word("lead", eid="123456"),
                    _word("LEAD", eid="654321"),
                ]
            }
        ),
        encoding="utf-8",
    )

    data = load_wordlist(path)
    words = [item["word"] for item in data["words"]]
    duplicate_words, stem_conflicts = find_word_conflicts(words)

    assert duplicate_words == {1: "lead"}
    assert stem_conflicts == {}


def test_eid_must_be_unique_even_when_word_is_duplicate(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps(
            {
                "words": [
                    _word("lead", eid="123456"),
                    _word("LEAD", eid="123456"),
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(WordListError, match="eid 重复"):
        load_wordlist(path)


def test_eid_must_be_six_ascii_digits(tmp_path):
    path = tmp_path / "wordlist.json"
    path.write_text(
        json.dumps({"words": [_word("one", eid="12x456")]}),
        encoding="utf-8",
    )

    with pytest.raises(WordListError, match="六位 ASCII"):
        load_wordlist(path)


def test_audio_stem_replaces_every_non_ascii_alnum_character():
    assert audio_stem("take care of") == "take_care_of"
    assert audio_stem("one's own") == "one_s_own"
    assert audio_stem("well-being") == "well_being"
    assert audio_stem("a / b") == "a___b"
    assert audio_stem("café") == "caf_"
    assert audio_stem("  A--B  ") == "A__B"


def test_word_stem_conflict_reports_later_word_only():
    duplicate_words, stem_conflicts = find_word_conflicts(
        ["well-being", "well being", "next"]
    )

    assert duplicate_words == {}
    assert stem_conflicts == {1: ("well-being", "well_being")}

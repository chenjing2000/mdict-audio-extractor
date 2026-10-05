import json

import pytest

from mdict_audio_extractor.wordlist import (
    WordListError,
    audio_stem,
    find_stem_conflicts,
    load_wordlist,
)


def _sense(**extra):
    value = {"pos": "n.", "chinese_meaning": "测试"}
    value.update(extra)
    return value


def _word(word, senses=None):
    return {
        "word": word,
        "phonetic_uk": "",
        "phonetic_us": "",
        "senses": senses or [_sense()],
    }


def _write(tmp_path, data):
    path = tmp_path / "wordlist.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_current_dual_phonetic_schema_without_wid(tmp_path):
    path = _write(
        tmp_path,
        {
            "schema_version": 2,
            "words": [
                _word("apple", [_sense(eid="01", example="An apple.")]),
                _word("ubiquitous"),
            ],
        },
    )

    data = load_wordlist(path)
    assert [item["word"] for item in data["words"]] == ["apple", "ubiquitous"]


def test_legacy_single_phonetic_schema_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        {
            "schema_version": 1,
            "words": [
                {
                    "word": "apple",
                    "phonetic": "/ˈæpl/",
                    "senses": [_sense()],
                }
            ],
        },
    )

    with pytest.raises(WordListError, match="phonetic_uk"):
        load_wordlist(path)


def test_duplicate_word_is_rejected_by_casefold(tmp_path):
    path = _write(
        tmp_path,
        {"words": [_word("lead"), _word("LEAD")]},
    )

    with pytest.raises(WordListError, match="单词重复"):
        load_wordlist(path)


def test_eid_is_two_digits_and_local_to_each_word(tmp_path):
    path = _write(
        tmp_path,
        {
            "words": [
                _word("one", [_sense(eid="01", example="One example.")]),
                _word("two", [_sense(eid="01", example="Two example.")]),
            ]
        },
    )

    load_wordlist(path)


def test_old_six_digit_eid_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        {"words": [_word("one", [_sense(eid="123456", example="Example.")])]},
    )

    with pytest.raises(WordListError, match="两位 ASCII"):
        load_wordlist(path)


def test_eid_requires_nonempty_example(tmp_path):
    path = _write(
        tmp_path,
        {"words": [_word("one", [_sense(eid="01")])]},
    )

    with pytest.raises(WordListError, match="非空.*example"):
        load_wordlist(path)


def test_eid_follows_actual_nonempty_example_order(tmp_path):
    path = _write(
        tmp_path,
        {
            "words": [
                _word(
                    "one",
                    [
                        _sense(example="First, no eid."),
                        _sense(eid="02", example="Second example."),
                    ],
                )
            ]
        },
    )

    load_wordlist(path)


def test_wrong_eid_order_is_rejected(tmp_path):
    path = _write(
        tmp_path,
        {
            "words": [
                _word(
                    "one",
                    [
                        _sense(example="First, no eid."),
                        _sense(eid="01", example="Second example."),
                    ],
                )
            ]
        },
    )

    with pytest.raises(WordListError, match="应为 \"02\""):
        load_wordlist(path)


def test_audio_stem_replaces_every_non_ascii_alnum_character():
    assert audio_stem("take care of") == "take_care_of"
    assert audio_stem("one's own") == "one_s_own"
    assert audio_stem("well-being") == "well_being"
    assert audio_stem("a / b") == "a___b"
    assert audio_stem("café") == "caf_"
    assert audio_stem("  A--B  ") == "A__B"


def test_word_stem_conflict_reports_later_word_only():
    conflicts = find_stem_conflicts(["well-being", "well being", "next"])
    assert conflicts == {1: ("well-being", "well_being")}

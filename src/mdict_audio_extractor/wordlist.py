import json
import re
from pathlib import Path


class WordListError(ValueError):
    pass


_AUDIO_STEM_RE = re.compile(r"[^0-9a-zA-Z]")
_EID_RE = re.compile(r"[0-9]{6}")


def audio_stem(word: str) -> str:
    """Return the filename stem used by word and example audio files."""
    return _AUDIO_STEM_RE.sub("_", word.strip())


def find_word_conflicts(
    words: list[str],
) -> tuple[dict[int, str], dict[int, tuple[str, str]]]:
    """Find later duplicate words and later filename-stem conflicts."""
    word_owners: dict[str, str] = {}
    stem_owners: dict[str, str] = {}
    duplicate_words: dict[int, str] = {}
    stem_conflicts: dict[int, tuple[str, str]] = {}

    for index, raw_word in enumerate(words):
        word = raw_word.strip()
        word_key = word.casefold()

        first_word = word_owners.get(word_key)
        if first_word is not None:
            duplicate_words[index] = first_word
            continue
        word_owners[word_key] = word

        stem = audio_stem(word)
        stem_key = stem.casefold()
        first_stem_word = stem_owners.get(stem_key)
        if first_stem_word is None:
            stem_owners[stem_key] = word
        else:
            stem_conflicts[index] = (first_stem_word, stem)

    return duplicate_words, stem_conflicts


def _require_string(value, message: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise WordListError(message)
    if not allow_empty and not value.strip():
        raise WordListError(message)
    return value


def _validate_string_list(value, message: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise WordListError(message)


def load_wordlist(wordlist_path: Path) -> dict:
    """Load and validate the current ReciteWords wordlist format."""
    try:
        data = json.loads(wordlist_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WordListError(f"单词本不存在：{wordlist_path}") from exc
    except json.JSONDecodeError as exc:
        raise WordListError(
            f"wordlist.json 不是有效 JSON：第 {exc.lineno} 行，第 {exc.colno} 列"
        ) from exc

    if not isinstance(data, dict):
        raise WordListError("wordlist.json 根节点必须是 JSON object。")

    if "schema_version" in data:
        schema_version = data["schema_version"]
        if type(schema_version) is not int or schema_version <= 0:
            raise WordListError("schema_version 必须是正整数。")

    for field in ("name", "description"):
        if field in data and not isinstance(data[field], str):
            raise WordListError(f'顶层字段 "{field}" 必须是字符串。')

    words = data.get("words")
    if not isinstance(words, list) or not words:
        raise WordListError('wordlist.json 必须包含非空数组字段 "words"。')

    seen_eids: set[str] = set()

    for word_index, item in enumerate(words):
        if not isinstance(item, dict):
            raise WordListError(f"words[{word_index}] 必须是 object。")

        word = _require_string(
            item.get("word"),
            f'words[{word_index}] 缺少有效的 "word" 字段。',
        )
        word = word.strip()

        _require_string(
            item.get("phonetic_uk"),
            f'Word "{word}" 缺少字符串字段 "phonetic_uk"。',
            allow_empty=True,
        )
        _require_string(
            item.get("phonetic_us"),
            f'Word "{word}" 缺少字符串字段 "phonetic_us"。',
            allow_empty=True,
        )

        for field in ("notes", "etymology"):
            if field in item and not isinstance(item[field], str):
                raise WordListError(f'Word "{word}" 的 "{field}" 必须是字符串。')

        senses = item.get("senses")
        if not isinstance(senses, list) or not senses:
            raise WordListError(f'Word "{word}" 的 "senses" 必须是非空数组。')

        for sense_index, sense in enumerate(senses):
            label = f'Word "{word}" senses[{sense_index}]'
            if not isinstance(sense, dict):
                raise WordListError(f"{label} 必须是 object。")

            _require_string(sense.get("pos"), f'{label} 缺少有效的 "pos"。')
            _require_string(
                sense.get("chinese_meaning"),
                f'{label} 缺少有效的 "chinese_meaning"。',
            )

            for field in ("english_meaning", "example", "example_translation"):
                if field in sense and not isinstance(sense[field], str):
                    raise WordListError(f'{label} 的 "{field}" 必须是字符串。')

            for field in ("register", "synonyms", "antonyms", "collocations"):
                if field in sense:
                    _validate_string_list(
                        sense[field],
                        f'{label} 的 "{field}" 必须是字符串数组。',
                    )

            if "eid" in sense:
                eid = sense["eid"]
                if not isinstance(eid, str) or _EID_RE.fullmatch(eid) is None:
                    raise WordListError(f'{label} 的 "eid" 必须是六位 ASCII 数字字符串。')
                if eid in seen_eids:
                    raise WordListError(f"eid 重复：{eid}")
                seen_eids.add(eid)

    return data

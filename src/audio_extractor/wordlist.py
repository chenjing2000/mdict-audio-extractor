import json
import re
from pathlib import Path

from .audio_files import atomic_write


class WordListError(ValueError):
    pass


_AUDIO_STEM_RE = re.compile(r"[^a-z0-9]+")
_EID_RE = re.compile(r"[0-9]{2}")


def audio_stem(word: str) -> str:
    """Return the filename stem used by word and example audio files."""
    return _AUDIO_STEM_RE.sub("_", word.strip().lower()).strip("_")


def find_stem_conflicts(words: list[str]) -> dict[int, tuple[str, str]]:
    """Return later words whose audio stems are already owned by earlier words."""
    stem_owners: dict[str, str] = {}
    conflicts: dict[int, tuple[str, str]] = {}

    for index, raw_word in enumerate(words):
        word = raw_word.strip()
        stem = audio_stem(word)
        if not stem:
            continue
        owner = stem_owners.get(stem)
        if owner is None:
            stem_owners[stem] = word
        else:
            conflicts[index] = (owner, stem)

    return conflicts


def _require_string(value, message: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise WordListError(message)
    if not allow_empty and not value.strip():
        raise WordListError(message)
    return value


def _validate_string_list(value, message: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise WordListError(message)


def read_json(wordlist_path: Path) -> dict:
    try:
        data = json.loads(wordlist_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise WordListError(f"单词本不存在：{wordlist_path}") from exc
    except json.JSONDecodeError as exc:
        raise WordListError(
            f"wordlist.json 不是有效 JSON：第 {exc.lineno} 行，第 {exc.colno} 列"
        ) from exc

    if not isinstance(data, dict):
        raise WordListError("wordlist.json 根节点必须是 JSON object。")
    return data


def resource_root(path: Path, data: dict) -> Path:
    return path.parent if data.get("filetype") in {"vocabulary", "passage"} else path.parent / path.stem


def load_wordlist(wordlist_path: Path, *, data: dict | None = None) -> dict:
    """Validate ReciteWords or ReadArticles vocabulary without converting data."""
    data = read_json(wordlist_path) if data is None else data
    if data.get("filetype") == "vocabulary":
        _validate_vocabulary(data)
        return data
    if "filetype" in data:
        raise WordListError("此文件不是支持的单词本。")

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

    seen_words: dict[str, str] = {}

    for word_index, item in enumerate(words):
        if not isinstance(item, dict):
            raise WordListError(f"words[{word_index}] 必须是 object。")

        word = _require_string(
            item.get("word"),
            f'words[{word_index}] 缺少有效的 "word" 字段。',
        ).strip()

        word_key = word.casefold()
        duplicate = seen_words.get(word_key)
        if duplicate is not None:
            raise WordListError(f'单词重复："{word}" 与 "{duplicate}"。')
        seen_words[word_key] = word

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

        example_number = 0
        seen_eids: set[str] = set()

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

            example = sense.get("example")
            has_example = isinstance(example, str) and bool(example.strip())
            if has_example:
                example_number += 1
                if example_number > 99:
                    raise WordListError(f'Word "{word}" 的非空例句不能超过 99 条。')

            if "eid" not in sense:
                continue

            eid = sense["eid"]
            if not isinstance(eid, str) or _EID_RE.fullmatch(eid) is None or eid == "00":
                raise WordListError(f'{label} 的 "eid" 必须是 01 到 99 的两位 ASCII 数字字符串。')
            if not has_example:
                raise WordListError(f'{label} 提供 "eid" 时必须同时提供非空 "example"。')
            if eid in seen_eids:
                raise WordListError(f'Word "{word}" 的 eid 重复：{eid}')

            expected_eid = f"{example_number:02d}"
            if eid != expected_eid:
                raise WordListError(
                    f'Word "{word}" 的 eid 顺序错误：当前例句应为 "{expected_eid}"，实际为 "{eid}"。'
                )
            seen_eids.add(eid)

    return data


def _validate_vocabulary(data: dict) -> None:
    words = data.get("words")
    if not isinstance(words, list):
        raise WordListError("vocabulary 的 words 必须是数组。")
    seen: set[str] = set()
    for item in words:
        if not isinstance(item, dict):
            raise WordListError("词条必须是 object。")
        word = _require_string(item.get("word"), "词条缺少有效 word。")
        key = " ".join(word.split()).casefold()
        if key in seen:
            raise WordListError(f"单词重复：{word}")
        seen.add(key)
        for accent in ("uk", "us"):
            field = f"phonetic_{accent}"
            if field in item:
                _require_string(item[field], f"{word} 的 {field} 必须是字符串。", allow_empty=True)
        meanings = item.get("meanings")
        if not isinstance(meanings, list):
            raise WordListError(f"{word} 的 meanings 必须是数组。")
        for meaning in meanings:
            if not isinstance(meaning, dict):
                raise WordListError(f"{word} 的 meaning 必须是 object。")
            for field in ("pos", "meaning"):
                _require_string(meaning.get(field), f"{word} 的 {field} 必须是字符串。", allow_empty=True)


def select_words(
    all_words: list[str],
    only_words: list[str] | None,
    limit: int | None,
) -> tuple[list[tuple[int, str]], list[str], list[str]]:
    requested: list[str] = []
    missing: list[str] = []
    selected = list(enumerate(all_words))

    if only_words:
        requested = [word.strip() for word in only_words if word.strip()]
        wanted = {word.casefold() for word in requested}
        available = {word.casefold() for word in all_words}
        missing = [word for word in requested if word.casefold() not in available]
        selected = [
            (index, word)
            for index, word in selected
            if word.casefold() in wanted
        ]

    if limit is not None:
        selected = selected[:limit]

    return selected, requested, missing


def save_wordlist(path: Path, data: dict) -> None:
    for item in data["words"]:
        item.pop("audio", None)
    atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def passage_tasks(data: dict, root: Path) -> list[tuple[str, Path]]:
    paragraphs = data.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise WordListError("passage 必须包含非空 paragraphs 数组。")
    seen: set[str] = set()
    tasks = []
    for paragraph in paragraphs:
        segments = paragraph.get("paragraph") if isinstance(paragraph, dict) else None
        if not isinstance(segments, list) or not segments:
            raise WordListError("paragraph 必须包含非空片段数组。")
        for segment in segments:
            if not isinstance(segment, dict):
                raise WordListError("segment 必须是 object。")
            sid, text = segment.get("sid"), segment.get("text")
            if not isinstance(sid, str) or not re.fullmatch(r"s[0-9]{3}", sid) or sid == "s000" or sid in seen:
                raise WordListError(f"非法或重复 sid：{sid}")
            if not isinstance(text, str) or not text.strip() or text != text.strip():
                raise WordListError(f"{sid} 的 text 为空或含首尾空白。")
            seen.add(sid)
            tasks.append((text, root / "audio_sentences" / sid))
    next_sid = data.get("next_sid")
    if type(next_sid) is not int or not max(int(sid[1:]) for sid in seen) < next_sid <= 1000:
        raise WordListError("next_sid 必须大于已有 sid，且不超过 1000。")
    return tasks

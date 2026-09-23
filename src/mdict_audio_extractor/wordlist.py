import json
from pathlib import Path


class WordListError(ValueError):
    pass


def load_words(wordlist_path: Path) -> list[str]:
    """
    Read the current words_review WordList JSON schema.

    Expected root:
      {
        "schema_version": 1,
        "name": ...,
        "description": ...,
        "words": [
          {"wid": "...", "word": "...", ...},
          ...
        ]
      }

    The current schema requires both "wid" and "word". The extractor still
    returns only the visible word strings needed by the MDX/MDD lookup path.
    """
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
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        raise WordListError("wordlist.json schema_version 必须为整数 1。")

    words_raw = data.get("words")
    if not isinstance(words_raw, list):
        raise WordListError('wordlist.json 必须包含数组字段 "words"。')

    words: list[str] = []
    seen_wids: set[str] = set()
    seen_words: set[str] = set()

    for i, item in enumerate(words_raw, start=1):
        if not isinstance(item, dict):
            raise WordListError(f"words[{i - 1}] 必须是 object。")

        wid = item.get("wid")
        if not isinstance(wid, str) or not wid.strip():
            raise WordListError(f'words[{i - 1}] 缺少有效的 "wid" 字段。')
        wid = wid.strip()
        if wid in seen_wids:
            raise WordListError(f'words[{i - 1}] 的 "wid" 重复：{wid}')
        seen_wids.add(wid)

        word = item.get("word")
        if not isinstance(word, str) or not word.strip():
            raise WordListError(f'words[{i - 1}] 缺少有效的 "word" 字段。')

        word = word.strip()
        key = word.casefold()
        if key in seen_words:
            raise WordListError(
                f'words[{i - 1}] 的 "word" 重复（忽略大小写）：{word}'
            )

        seen_words.add(key)
        words.append(word)

    return words

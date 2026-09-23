import json
from pathlib import Path


class WordListError(ValueError):
    pass


def load_words(wordlist_path: Path) -> list[str]:
    """
    Read the current words_review WordList JSON schema.

    Expected root:
      {
        "schema_version": ...,
        "name": ...,
        "description": ...,
        "words": [
          {"id": "...", "word": "...", ...},
          ...
        ]
      }

    Only the "word" field is required by this extractor.
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

    words_raw = data.get("words")
    if not isinstance(words_raw, list):
        raise WordListError('wordlist.json 必须包含数组字段 "words"。')

    words: list[str] = []
    seen: set[str] = set()

    for i, item in enumerate(words_raw, start=1):
        if not isinstance(item, dict):
            raise WordListError(f"words[{i - 1}] 必须是 object。")

        word = item.get("word")
        if not isinstance(word, str) or not word.strip():
            raise WordListError(f'words[{i - 1}] 缺少有效的 "word" 字段。')

        word = word.strip()
        key = word.casefold()
        if key in seen:
            continue

        seen.add(key)
        words.append(word)

    return words

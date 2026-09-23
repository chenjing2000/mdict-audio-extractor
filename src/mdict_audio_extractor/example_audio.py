import json
import re
import time
from pathlib import Path


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_word_filename(word: str) -> str:
    value = _INVALID_FILENAME_CHARS.sub("_", word.strip())
    value = re.sub(r"\s+", "_", value).rstrip(". ")
    return value or "word"


def _load_wordlist(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("wordlist.json 根节点必须是 JSON object。")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        raise ValueError("wordlist.json schema_version 必须为整数 1。")

    words = data.get("words")
    if not isinstance(words, list):
        raise ValueError("wordlist.json 缺少 words 数组。")
    return words


def _load_existing_examples(path: Path) -> dict:
    if not path.is_file():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return {}

    words = data.get("words")
    return words if isinstance(words, dict) else {}


def _valid_eid(eid: str) -> bool:
    return len(eid) == 6 and eid.isdigit()


def _old_entries_by_eid(entries) -> dict[str, dict]:
    if not isinstance(entries, list):
        return {}

    result = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        eid = item.get("eid")
        if isinstance(eid, str) and eid.strip():
            result[eid.strip()] = item
    return result


def _save_tts(text: str, voice: str, output_path: Path) -> None:
    import edge_tts

    communicator = edge_tts.Communicate(text, voice)
    communicator.save_sync(str(output_path))


def _generate_with_retry(
    text: str,
    voice: str,
    output_path: Path,
    wait_seconds: float,
) -> str | None:
    for attempt in range(2):
        try:
            _save_tts(text, voice, output_path)
            return None
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            if attempt == 0 and wait_seconds > 0:
                time.sleep(wait_seconds)
            else:
                return str(exc)

    return "unknown error"


def _reuse_old_audio(
    old_entry: dict,
    accent: str,
    resource_dir: Path,
) -> str | None:
    relative = old_entry.get(accent)
    if not isinstance(relative, str) or not relative.strip():
        return None

    relative = relative.strip()
    if not (resource_dir / relative).is_file():
        return None

    return relative


def example_audio_synthesis(
    wordlist_path: str | Path,
    uk_voice: str = "en-GB-SoniaNeural",
    us_voice: str = "en-US-JennyNeural",
    wait_seconds: float = 2,
) -> dict:
    """Generate UK/US TTS audio for valid senses[].example + senses[].eid pairs."""
    wordlist = Path(wordlist_path).expanduser().resolve()
    if not wordlist.is_file():
        raise FileNotFoundError(f"wordlist.json 不存在：{wordlist}")
    if wait_seconds < 0:
        raise ValueError("wait_seconds 不能小于 0。")

    try:
        import edge_tts  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("缺少 edge-tts，请先运行 uv sync。") from exc

    resource_dir = wordlist.parent / wordlist.stem
    examples_dir = resource_dir / "examples"
    examples_json = resource_dir / "examples.json"
    examples_dir.mkdir(parents=True, exist_ok=True)

    old_words = _load_existing_examples(examples_json)
    source_words = _load_wordlist(wordlist)
    new_words: dict[str, list[dict[str, str]]] = {}
    seen_eids: set[str] = set()
    seen_wids: set[str] = set()
    seen_words: set[str] = set()

    total_examples = 0
    generated_uk = 0
    generated_us = 0
    reused_uk = 0
    reused_us = 0
    failed = 0
    skipped_invalid_eid = 0

    for word_index, item in enumerate(source_words, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"words[{word_index - 1}] 必须是 object。")

        wid = item.get("wid")
        word = item.get("word")
        senses = item.get("senses")

        if not isinstance(wid, str) or not wid.strip():
            raise ValueError(f'words[{word_index - 1}] 缺少有效的 "wid" 字段。')
        wid = wid.strip()
        if wid in seen_wids:
            raise ValueError(f"wid 重复：{wid}")
        seen_wids.add(wid)

        if not isinstance(word, str) or not word.strip():
            raise ValueError(f'words[{word_index - 1}] 缺少有效的 "word" 字段。')
        word = word.strip()
        word_key = word.casefold()
        if word_key in seen_words:
            raise ValueError(f"word 重复（忽略大小写）：{word}")
        seen_words.add(word_key)

        if not isinstance(senses, list):
            raise ValueError(f'Word "{word}" 缺少 senses 数组。')

        examples: list[tuple[int, str, str]] = []
        example_number = 0

        for sense_index, sense in enumerate(senses, start=1):
            if not isinstance(sense, dict):
                continue

            example = sense.get("example", "")
            if not isinstance(example, str) or not example.strip():
                continue

            example_number += 1
            sentence = example.strip()
            eid = sense.get("eid", "")

            if not isinstance(eid, str) or not eid.strip():
                skipped_invalid_eid += 1
                print(
                    f"[{word}] e{example_number:02d}: 跳过，sense {sense_index} 例句缺少 eid"
                )
                continue

            eid = eid.strip()
            if not _valid_eid(eid):
                skipped_invalid_eid += 1
                print(
                    f"[{word}] e{example_number:02d}: 跳过，sense {sense_index} eid 无效：{eid}"
                )
                continue

            if eid in seen_eids:
                raise ValueError(f"eid 重复：{eid}")
            seen_eids.add(eid)
            examples.append((example_number, eid, sentence))

        if not examples:
            continue

        old_entries = _old_entries_by_eid(old_words.get(word))
        word_entries: list[dict[str, str]] = []
        stem = _safe_word_filename(word)

        for example_index, eid, sentence in examples:
            total_examples += 1
            label = f"e{example_index:02d}"
            print(f"[{word}] {label} {eid}: {sentence}")

            uk_path = examples_dir / f"{stem}_{label}_uk.mp3"
            us_path = examples_dir / f"{stem}_{label}_us.mp3"
            uk_relative = uk_path.relative_to(resource_dir).as_posix()
            us_relative = us_path.relative_to(resource_dir).as_posix()

            old_entry = old_entries.get(eid, {})
            same_text = old_entry.get("text") == sentence
            entry: dict[str, str] = {"eid": eid, "text": sentence}

            reused_relative = (
                _reuse_old_audio(old_entry, "uk", resource_dir)
                if same_text
                else None
            )
            if reused_relative is not None:
                entry["uk"] = reused_relative
                reused_uk += 1
                print(f"  UK: 复用 {reused_relative}")
            else:
                error = _generate_with_retry(
                    sentence, uk_voice, uk_path, wait_seconds
                )
                if error is None:
                    entry["uk"] = uk_relative
                    generated_uk += 1
                    print(f"  UK: 生成 {uk_relative}")
                else:
                    failed += 1
                    print(f"  UK: 失败 - {error}")

            reused_relative = (
                _reuse_old_audio(old_entry, "us", resource_dir)
                if same_text
                else None
            )
            if reused_relative is not None:
                entry["us"] = reused_relative
                reused_us += 1
                print(f"  US: 复用 {reused_relative}")
            else:
                error = _generate_with_retry(
                    sentence, us_voice, us_path, wait_seconds
                )
                if error is None:
                    entry["us"] = us_relative
                    generated_us += 1
                    print(f"  US: 生成 {us_relative}")
                else:
                    failed += 1
                    print(f"  US: 失败 - {error}")

            word_entries.append(entry)

        if word_entries:
            new_words[word] = word_entries

    output = {
        "schema_version": 1,
        "words": new_words,
    }
    examples_json.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "words": len(new_words),
        "examples": total_examples,
        "generated_uk": generated_uk,
        "generated_us": generated_us,
        "reused_uk": reused_uk,
        "reused_us": reused_us,
        "failed": failed,
        "skipped_invalid_eid": skipped_invalid_eid,
    }

    print("\n例句音频完成：")
    print(f"  单词数：{summary['words']}")
    print(f"  例句数：{summary['examples']}")
    print(f"  UK 新生成：{summary['generated_uk']}")
    print(f"  US 新生成：{summary['generated_us']}")
    print(f"  UK 已复用：{summary['reused_uk']}")
    print(f"  US 已复用：{summary['reused_us']}")
    print(f"  无效 eid 跳过：{summary['skipped_invalid_eid']}")
    print(f"  失败：{summary['failed']}")
    print(f"  输出目录：{resource_dir}")

    return summary

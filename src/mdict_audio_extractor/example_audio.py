import json
import time
from pathlib import Path

from .wordlist import audio_stem, find_word_conflicts, load_wordlist


def _load_existing_examples(path: Path) -> dict[str, list[dict]]:
    if not path.is_file():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict) or data.get("schema_version") != 2:
        return {}

    words = data.get("words")
    return words if isinstance(words, dict) else {}


def _save_tts(text: str, voice: str, output_path: Path) -> None:
    import edge_tts

    edge_tts.Communicate(text, voice).save_sync(str(output_path))


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
    return relative if (resource_dir / relative).is_file() else None


def _prepare_audio(
    *,
    sentence: str,
    voice: str,
    accent: str,
    output_path: Path,
    relative_path: str,
    old_entry: dict,
    same_identity: bool,
    resource_dir: Path,
    wait_seconds: float,
) -> tuple[str | None, str]:
    if same_identity:
        reused = _reuse_old_audio(old_entry, accent, resource_dir)
        if reused is not None:
            print(f"  {accent.upper()}: 复用 {reused}")
            return reused, "reused"

    error = _generate_with_retry(sentence, voice, output_path, wait_seconds)
    if error is not None:
        print(f"  {accent.upper()}: 失败 - {error}")
        return None, "failed"

    print(f"  {accent.upper()}: 生成 {relative_path}")
    return relative_path, "generated"


def _valid_example_count(item: dict) -> int:
    return sum(
        isinstance(sense.get("example"), str) and bool(sense["example"].strip())
        for sense in item["senses"]
    )


def example_audio_synthesis(
    wordlist_path: str | Path,
    uk_voice: str = "en-GB-SoniaNeural",
    us_voice: str = "en-US-JennyNeural",
    wait_seconds: float = 2,
) -> dict:
    """Generate UK/US TTS audio for each non-empty sense example."""
    wordlist = Path(wordlist_path).expanduser().resolve()
    if not wordlist.is_file():
        raise FileNotFoundError(f"wordlist.json 不存在：{wordlist}")
    if wait_seconds < 0:
        raise ValueError("wait_seconds 不能小于 0。")

    try:
        import edge_tts  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("缺少 edge-tts，请先运行 uv sync。") from exc

    data = load_wordlist(wordlist)
    items: list[dict] = data["words"]
    words = [item["word"].strip() for item in items]
    duplicate_words, stem_conflicts = find_word_conflicts(words)

    resource_dir = wordlist.parent / wordlist.stem
    examples_dir = resource_dir / "examples"
    examples_json = resource_dir / "examples.json"
    examples_dir.mkdir(parents=True, exist_ok=True)

    old_words = _load_existing_examples(examples_json)
    old_words_by_key = {
        key.casefold(): value
        for key, value in old_words.items()
        if isinstance(key, str) and isinstance(value, list)
    }
    new_words: dict[str, list[dict[str, str]]] = {}

    total_examples = 0
    generated = {"uk": 0, "us": 0}
    reused = {"uk": 0, "us": 0}
    failed = 0
    duplicate_words_skipped = 0
    duplicate_word_examples_skipped = 0
    stem_conflicts_skipped = 0
    stem_conflict_examples_skipped = 0

    for word_index, item in enumerate(items):
        word = words[word_index]
        example_count = _valid_example_count(item)

        duplicate_of = duplicate_words.get(word_index)
        if duplicate_of is not None:
            duplicate_words_skipped += 1
            duplicate_word_examples_skipped += example_count
            print(
                f'[{word}] 跳过例句音频：单词重复，首次出现为 "{duplicate_of}"；'
                f"跳过 {example_count} 条例句。"
            )
            continue

        conflict = stem_conflicts.get(word_index)
        if conflict is not None:
            owner, stem = conflict
            stem_conflicts_skipped += 1
            stem_conflict_examples_skipped += example_count
            print(
                f'[{word}] 跳过例句音频：word_stem 冲突，"{owner}" 与 '
                f'"{word}" 都会转换为 "{stem}"；跳过 {example_count} 条例句。'
            )
            continue

        stem = audio_stem(word)
        old_entries = old_words_by_key.get(stem.casefold(), [])
        entries: list[dict[str, str]] = []
        example_id = 0

        for sense in item["senses"]:
            example = sense.get("example")
            if not isinstance(example, str) or not example.strip():
                continue

            sentence = example.strip()
            example_id += 1
            example_code = f"{example_id:02d}"
            total_examples += 1
            print(f"[{word}] e{example_code}: {sentence}")

            base_name = f"{stem}_e{example_code}"
            old_entry = (
                old_entries[example_id - 1]
                if example_id - 1 < len(old_entries)
                and isinstance(old_entries[example_id - 1], dict)
                else {}
            )
            same_identity = (
                old_entry.get("id") == example_code
                and old_entry.get("text") == sentence
            )

            entry: dict[str, str] = {"id": example_code, "text": sentence}
            for accent, voice in (("uk", uk_voice), ("us", us_voice)):
                output_path = examples_dir / f"{base_name}_{accent}.mp3"
                relative_path = output_path.relative_to(resource_dir).as_posix()
                audio_path, status = _prepare_audio(
                    sentence=sentence,
                    voice=voice,
                    accent=accent,
                    output_path=output_path,
                    relative_path=relative_path,
                    old_entry=old_entry,
                    same_identity=same_identity,
                    resource_dir=resource_dir,
                    wait_seconds=wait_seconds,
                )

                if audio_path is not None:
                    entry[accent] = audio_path
                if status == "generated":
                    generated[accent] += 1
                elif status == "reused":
                    reused[accent] += 1
                else:
                    failed += 1

            entries.append(entry)

        if entries:
            new_words[stem] = entries

    examples_json.write_text(
        json.dumps(
            {"schema_version": 2, "words": new_words},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = {
        "examples": total_examples,
        "generated_uk": generated["uk"],
        "generated_us": generated["us"],
        "reused_uk": reused["uk"],
        "reused_us": reused["us"],
        "failed": failed,
        "duplicate_words_skipped": duplicate_words_skipped,
        "duplicate_word_examples_skipped": duplicate_word_examples_skipped,
        "stem_conflicts_skipped": stem_conflicts_skipped,
        "stem_conflict_examples_skipped": stem_conflict_examples_skipped,
    }

    print("\n例句音频完成：")
    print(f"  例句数：{summary['examples']}")
    print(f"  UK 新生成：{summary['generated_uk']}")
    print(f"  US 新生成：{summary['generated_us']}")
    print(f"  UK 已复用：{summary['reused_uk']}")
    print(f"  US 已复用：{summary['reused_us']}")
    print(
        f"  重复单词跳过：{summary['duplicate_words_skipped']} 个单词，"
        f"{summary['duplicate_word_examples_skipped']} 条例句"
    )
    print(
        f"  word_stem 冲突跳过：{summary['stem_conflicts_skipped']} 个单词，"
        f"{summary['stem_conflict_examples_skipped']} 条例句"
    )
    print(f"  失败：{summary['failed']}")
    print(f"  输出目录：{resource_dir}")

    return summary

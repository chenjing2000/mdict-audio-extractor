import time
from pathlib import Path

from .wordlist import audio_stem, find_stem_conflicts, load_wordlist


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


def _prepare_audio(
    sentence: str,
    voice: str,
    accent: str,
    output_path: Path,
    wait_seconds: float,
) -> str:
    if output_path.is_file():
        print(f"  {accent.upper()}: 复用 {output_path.name}")
        return "reused"

    error = _generate_with_retry(sentence, voice, output_path, wait_seconds)
    if error is not None:
        print(f"  {accent.upper()}: 失败 - {error}")
        return "failed"

    print(f"  {accent.upper()}: 生成 {output_path.name}")
    return "generated"


def _nonempty_example_count(item: dict) -> int:
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
    """Generate UK/US TTS audio for examples that provide an eid."""
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
    stem_conflicts = find_stem_conflicts(words)

    resource_dir = wordlist.parent / wordlist.stem
    examples_dir = resource_dir / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    processed_examples = 0
    generated = {"uk": 0, "us": 0}
    reused = {"uk": 0, "us": 0}
    failed = 0
    missing_eid_skipped = 0
    stem_conflicts_skipped = 0
    stem_conflict_examples_skipped = 0

    for word_index, item in enumerate(items):
        word = words[word_index]
        conflict = stem_conflicts.get(word_index)
        if conflict is not None:
            owner, stem = conflict
            example_count = _nonempty_example_count(item)
            stem_conflicts_skipped += 1
            stem_conflict_examples_skipped += example_count
            print(
                f'[{word}] 跳过全部例句音频：word_stem 冲突，"{owner}" 与 '
                f'"{word}" 都会转换为 "{stem}"；跳过 {example_count} 条例句。'
            )
            continue

        stem = audio_stem(word)

        for sense in item["senses"]:
            example = sense.get("example")
            if not isinstance(example, str) or not example.strip():
                continue

            sentence = example.strip()
            eid = sense.get("eid")
            if eid is None:
                missing_eid_skipped += 1
                print(f'[{word}] 跳过例句音频：例句没有 eid：{sentence}')
                continue

            processed_examples += 1
            print(f"[{word}] e{eid}: {sentence}")
            base_name = f"{stem}_e{eid}"

            for accent, voice in (("uk", uk_voice), ("us", us_voice)):
                output_path = examples_dir / f"{base_name}_{accent}.mp3"
                status = _prepare_audio(
                    sentence,
                    voice,
                    accent,
                    output_path,
                    wait_seconds,
                )
                if status == "generated":
                    generated[accent] += 1
                elif status == "reused":
                    reused[accent] += 1
                else:
                    failed += 1

    summary = {
        "examples": processed_examples,
        "generated_uk": generated["uk"],
        "generated_us": generated["us"],
        "reused_uk": reused["uk"],
        "reused_us": reused["us"],
        "failed": failed,
        "missing_eid_skipped": missing_eid_skipped,
        "stem_conflicts_skipped": stem_conflicts_skipped,
        "stem_conflict_examples_skipped": stem_conflict_examples_skipped,
    }

    print("\n例句音频完成：")
    print(f"  处理例句：{summary['examples']}")
    print(f"  UK 新生成：{summary['generated_uk']}")
    print(f"  US 新生成：{summary['generated_us']}")
    print(f"  UK 已复用：{summary['reused_uk']}")
    print(f"  US 已复用：{summary['reused_us']}")
    print(f"  缺少 eid 跳过：{summary['missing_eid_skipped']} 条例句")
    print(
        f"  word_stem 冲突跳过：{summary['stem_conflicts_skipped']} 个单词，"
        f"{summary['stem_conflict_examples_skipped']} 条例句"
    )
    print(f"  失败：{summary['failed']}")
    print(f"  输出目录：{resource_dir}")

    return summary

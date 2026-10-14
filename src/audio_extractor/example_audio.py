import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from .audio_files import existing_audio
from .reporting import print_message
from .wordlist import (
    audio_stem, find_stem_conflicts, load_wordlist, read_json,
    resource_root, select_words, passage_tasks,
)


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
            if not output_path.is_file() or not output_path.stat().st_size:
                raise ValueError("TTS 未生成非空音频。")
            return None
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            if attempt == 1:
                return str(exc)
            if wait_seconds > 0:
                time.sleep(wait_seconds)


def _prepare_audio(
    sentence: str,
    voice: str,
    accent: str,
    output_path: Path,
    wait_seconds: float,
) -> str:
    existing = existing_audio(output_path)
    if existing is not None:
        print_message(f"  {accent.upper()}: 已有音频跳过 {existing.name}")
        return "reused"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output_path.parent, suffix=".mp3", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        error = _generate_with_retry(sentence, voice, temporary, wait_seconds)
        if error is not None:
            print_message(f"  {accent.upper()}: 失败 - {error}")
            return "failed"
        temporary.replace(output_path)
    except OSError as exc:
        print_message(f"  {accent.upper()}: 写入失败 - {exc}")
        return "failed"
    finally:
        temporary.unlink(missing_ok=True)

    print_message(f"  {accent.upper()}: 生成 {output_path.name}")
    return "generated"


def _nonempty_example_count(item: dict) -> int:
    return sum(
        isinstance(sense.get("example"), str) and bool(sense["example"].strip())
        for sense in item["senses"]
    )


def _synthesize_tasks(
    tasks: list[tuple[str, Path]], summary: dict,
    uk_voice: str, us_voice: str, wait_seconds: float,
) -> dict:
    for text, base in tasks:
        for accent, voice in (("uk", uk_voice), ("us", us_voice)):
            output = base.with_name(f"{base.name}_{accent}.mp3")
            status = _prepare_audio(text, voice, accent, output, wait_seconds)
            summary["failed" if status == "failed" else f"{status}_{accent}"] += 1
    return summary


def example_audio_synthesis(
    wordlist_path: str | Path,
    uk_voice: str = "en-GB-SoniaNeural",
    us_voice: str = "en-US-JennyNeural",
    wait_seconds: float = 2,
    *,
    limit: int | None = None,
    words: list[str] | None = None,
    data: dict | None = None,
) -> dict:
    """Synthesize SID segments or EID examples; never synthesize words."""
    wordlist = Path(wordlist_path).expanduser().resolve()
    if not wordlist.is_file():
        raise FileNotFoundError(f"wordlist.json 不存在：{wordlist}")
    if wait_seconds < 0:
        raise ValueError("wait_seconds 不能小于 0。")
    if limit is not None and limit < 1:
        raise ValueError("limit 必须大于 0。")

    data = read_json(wordlist) if data is None else data
    summary = {"generated_uk": 0, "generated_us": 0,
               "reused_uk": 0, "reused_us": 0, "failed": 0}
    if data.get("filetype") == "passage":
        tasks = passage_tasks(data, wordlist.parent)
        if limit is not None:
            tasks = tasks[:limit]
        summary["segments"] = len(tasks)
        return _synthesize_tasks(tasks, summary, uk_voice, us_voice, wait_seconds)

    data = load_wordlist(wordlist, data=data)
    if data.get("filetype") == "vocabulary":
        summary["examples"] = 0
        return summary
    items: list[dict] = data["words"]
    all_words = [item["word"].strip() for item in items]
    stem_conflicts = find_stem_conflicts(all_words)

    selected, _, missing = select_words(all_words, words, limit)
    if missing:
        print_message(f"例句合成：以下指定单词不在本词表，已跳过：{', '.join(missing)}")
    resource_dir = resource_root(wordlist, data)
    examples_dir = resource_dir / "audio_sentences"
    summary.update(examples=0, missing_eid_skipped=0, stem_conflicts_skipped=0,
                   stem_conflict_examples_skipped=0, empty_stem_skipped=0)
    tasks = []

    for word_index, word in selected:
        item = items[word_index]
        conflict = stem_conflicts.get(word_index)
        if conflict is not None:
            owner, stem = conflict
            example_count = _nonempty_example_count(item)
            summary["stem_conflicts_skipped"] += 1
            summary["stem_conflict_examples_skipped"] += example_count
            print_message(
                f'[{word}] 跳过全部例句音频：word_stem 冲突，"{owner}" 与 '
                f'"{word}" 都会转换为 "{stem}"；跳过 {example_count} 条例句。'
            )
            continue

        stem = audio_stem(word)
        if not stem:
            summary["empty_stem_skipped"] += 1
            continue

        for sense in item["senses"]:
            example = sense.get("example")
            if not isinstance(example, str) or not example.strip():
                continue

            sentence = example.strip()
            eid = sense.get("eid")
            if eid is None:
                summary["missing_eid_skipped"] += 1
                print_message(f'[{word}] 跳过例句音频：例句没有 eid：{sentence}')
                continue

            print_message(f"[{word}] e{eid}: {sentence}")
            tasks.append((sentence, examples_dir / f"{stem}_e{eid}"))

    summary["examples"] = len(tasks)
    return _synthesize_tasks(tasks, summary, uk_voice, us_voice, wait_seconds)

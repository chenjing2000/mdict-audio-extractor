import time
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from .audio_files import existing_audio
from .wordlist import WordListError, audio_stem, find_stem_conflicts, load_wordlist, read_json, resource_root, select_words


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
        print(f"  {accent.upper()}: 已有音频跳过 {existing.name}")
        return "reused"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=output_path.parent, suffix=".mp3", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        error = _generate_with_retry(sentence, voice, temporary, wait_seconds)
        if error is not None:
            print(f"  {accent.upper()}: 失败 - {error}")
            return "failed"
        temporary.replace(output_path)
    except OSError as exc:
        print(f"  {accent.upper()}: 写入失败 - {exc}")
        return "failed"
    finally:
        temporary.unlink(missing_ok=True)

    print(f"  {accent.upper()}: 生成 {output_path.name}")
    return "generated"


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

    selected, _, _ = select_words(all_words, words, limit)
    selected_indices = {index for index, _ in selected}
    resource_dir = resource_root(wordlist, data)
    examples_dir = resource_dir / "audio_sentences"
    summary.update(examples=0, missing_eid_skipped=0, stem_conflicts_skipped=0,
                   stem_conflict_examples_skipped=0, empty_stem_skipped=0)
    tasks = []

    for word_index, item in enumerate(items):
        if word_index not in selected_indices:
            continue
        word = all_words[word_index]
        conflict = stem_conflicts.get(word_index)
        if conflict is not None:
            owner, stem = conflict
            example_count = _nonempty_example_count(item)
            summary["stem_conflicts_skipped"] += 1
            summary["stem_conflict_examples_skipped"] += example_count
            print(
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
                print(f'[{word}] 跳过例句音频：例句没有 eid：{sentence}')
                continue

            print(f"[{word}] e{eid}: {sentence}")
            tasks.append((sentence, examples_dir / f"{stem}_e{eid}"))

    summary["examples"] = len(tasks)
    return _synthesize_tasks(tasks, summary, uk_voice, us_voice, wait_seconds)

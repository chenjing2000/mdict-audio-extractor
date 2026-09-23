import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from .adapter_oald import parse_headword_pronunciations
from .mdict_index import MddCollection, MdxIndex
from .models import PronunciationCandidate
from .wordlist import load_words


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_word_filename(word: str) -> str:
    value = _INVALID_FILENAME_CHARS.sub("_", word.strip())
    value = re.sub(r"\s+", "_", value).rstrip(". ")
    return value or "word"


def _extension_from_resource(resource: str) -> str:
    suffix = Path(resource.replace("\\", "/")).suffix.lower()
    return suffix if suffix and len(suffix) <= 10 else ".bin"


def _unique_candidates(
    candidates: Iterable[PronunciationCandidate],
) -> list[PronunciationCandidate]:
    result: list[PronunciationCandidate] = []
    seen: set[tuple[str, str]] = set()

    for item in candidates:
        key = (item.accent, item.resource.casefold())
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def _build_output_names(
    word: str,
    candidates: list[PronunciationCandidate],
) -> dict[tuple[str, str], str]:
    stem = safe_word_filename(word)
    counts = Counter(item.accent for item in candidates)
    running: Counter[str] = Counter()
    names: dict[tuple[str, str], str] = {}

    for item in candidates:
        running[item.accent] += 1
        suffix = _extension_from_resource(item.resource)

        if counts[item.accent] == 1:
            filename = f"{stem}_{item.accent}{suffix}"
        else:
            filename = f"{stem}_{item.accent}_{running[item.accent]}{suffix}"

        names[(item.accent, item.resource.casefold())] = filename

    return names


def _select_words(
    all_words: list[str],
    only_words: list[str] | None,
    limit: int | None,
) -> tuple[list[str], list[str], list[str]]:
    requested: list[str] = []
    missing: list[str] = []
    words = all_words

    if only_words:
        requested = [word.strip() for word in only_words if word.strip()]
        wanted = {word.casefold() for word in requested}
        available = {word.casefold() for word in all_words}
        missing = [word for word in requested if word.casefold() not in available]
        words = [word for word in all_words if word.casefold() in wanted]

        if missing:
            print("注意：以下指定单词不在当前 wordlist.json 中，已跳过：")
            for word in missing:
                print(f"  - {word}")

    if limit is not None:
        words = words[:limit]

    return words, requested, missing


def extract(
    *,
    mdx_path: Path,
    mdd_paths: list[Path],
    wordlist_path: Path,
    output_dir: Path | None = None,
    overwrite: bool = False,
    limit: int | None = None,
    only_words: list[str] | None = None,
) -> dict:
    words, requested_filter, missing_filter = _select_words(
        load_words(wordlist_path),
        only_words,
        limit,
    )

    output_dir = output_dir or wordlist_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    print(f"加载 MDX 索引：{mdx_path}")
    mdx = MdxIndex(mdx_path)

    print("加载 MDD 索引：")
    for path in mdd_paths:
        print(f"  - {path}")
    mdds = MddCollection(mdd_paths)

    pronunciation_words: dict[str, dict[str, list[str]]] = {}
    word_reports: list[dict] = []
    total = len(words)

    for number, word in enumerate(words, start=1):
        print(f"[{number}/{total}] {word}")
        records = mdx.lookup_all(word)

        if not records:
            word_reports.append(
                {
                    "word": word,
                    "status": "mdx_entry_not_found",
                    "mdx_records": 0,
                    "pronunciations": [],
                }
            )
            print("  MDX 中没有找到词条")
            continue

        candidates = _unique_candidates(
            candidate
            for html in records
            for candidate in parse_headword_pronunciations(html)
        )

        if not candidates:
            word_reports.append(
                {
                    "word": word,
                    "status": "headword_audio_not_found",
                    "mdx_records": len(records),
                    "pronunciations": [],
                }
            )
            print("  找到词条，但没有识别到词头发音")
            continue

        output_names = _build_output_names(word, candidates)
        word_audio: dict[str, list[str]] = {"uk": [], "us": []}
        details: list[dict] = []

        for candidate in candidates:
            location = mdds.find(candidate.resource)
            output_name = output_names[
                (candidate.accent, candidate.resource.casefold())
            ]
            output_path = audio_dir / output_name
            relative_path = output_path.relative_to(output_dir).as_posix()

            detail = {
                "accent": candidate.accent,
                "ipa": candidate.ipa,
                "source_resource": candidate.resource,
                "output": relative_path,
            }

            if location is None:
                detail["status"] = "mdd_resource_not_found"
                details.append(detail)
                print(
                    f"  {candidate.accent.upper()}: "
                    f"MDD 中未找到 {candidate.resource}"
                )
                continue

            detail["mdd"] = mdd_paths[location.mdd_index].name
            detail["mdd_key"] = location.original_key

            if output_path.exists() and not overwrite:
                detail["status"] = "reused_existing"
                print(f"  {candidate.accent.upper()}: 复用 {relative_path}")
            else:
                payload = mdds.read(location)
                output_path.write_bytes(payload)
                detail["status"] = "extracted"
                detail["bytes"] = len(payload)
                print(
                    f"  {candidate.accent.upper()}: "
                    f"{candidate.resource} -> {relative_path}"
                )

            word_audio[candidate.accent].append(relative_path)
            details.append(detail)

        available_audio = {
            accent: paths for accent, paths in word_audio.items() if paths
        }
        if available_audio:
            pronunciation_words[word] = available_audio

        has_uk = bool(word_audio["uk"])
        has_us = bool(word_audio["us"])
        if has_uk and has_us:
            status = "ok"
        elif has_uk or has_us:
            status = "partial"
        else:
            status = "audio_not_extracted"

        word_reports.append(
            {
                "word": word,
                "status": status,
                "mdx_records": len(records),
                "pronunciations": details,
            }
        )

    pronunciation = {
        "schema_version": 1,
        "words": pronunciation_words,
    }

    report = {
        "schema_version": 1,
        "source": {
            "mdx": mdx_path.name,
            "mdds": [path.name for path in mdd_paths],
            "wordlist": wordlist_path.name,
        },
        "summary": {
            "requested_words": len(words),
            "filter_words": requested_filter,
            "filter_words_not_in_wordlist": missing_filter,
            "words_with_any_audio": sum(
                item["status"] in {"ok", "partial"} for item in word_reports
            ),
            "words_with_uk_and_us": sum(
                item["status"] == "ok" for item in word_reports
            ),
            "partial_words": sum(
                item["status"] == "partial" for item in word_reports
            ),
            "mdx_entry_not_found": sum(
                item["status"] == "mdx_entry_not_found" for item in word_reports
            ),
            "headword_audio_not_found": sum(
                item["status"] == "headword_audio_not_found"
                for item in word_reports
            ),
            "audio_not_extracted": sum(
                item["status"] == "audio_not_extracted" for item in word_reports
            ),
        },
        "words": word_reports,
    }

    (output_dir / "audio.json").write_text(
        json.dumps(pronunciation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report

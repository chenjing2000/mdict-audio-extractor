import json
from pathlib import Path

from .adapter_oald import PronunciationCandidate, parse_headword_pronunciations
from .mdict_index import MddCollection, MdxIndex
from .wordlist import audio_stem, find_stem_conflicts, load_wordlist


def _extension_from_resource(resource: str) -> str:
    suffix = Path(resource.replace("\\", "/")).suffix.lower()
    return suffix if suffix in {".mp3", ".wav"} else ".mp3"


def _primary_candidates(
    candidates: list[PronunciationCandidate],
) -> list[PronunciationCandidate]:
    """Keep one preferred recording per accent."""
    selected: dict[str, PronunciationCandidate] = {}

    for item in candidates:
        current = selected.get(item.accent)
        if current is None or (not current.ipa and item.ipa):
            selected[item.accent] = item

    return [selected[accent] for accent in ("uk", "us") if accent in selected]


def _select_words(
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

        if missing:
            print("注意：以下指定单词不在当前 wordlist.json 中，已跳过：")
            for word in missing:
                print(f"  - {word}")

    if limit is not None:
        selected = selected[:limit]

    return selected, requested, missing


def _update_phonetic(word_item: dict, accent: str, ipa: str | None) -> bool:
    if not isinstance(ipa, str) or not ipa.strip():
        return False

    field = f"phonetic_{accent}"
    new_value = ipa.strip()
    old_value = word_item.get(field, "")
    if old_value == new_value:
        return False

    print(f"  {accent.upper()} 音标：{old_value or '—'} -> {new_value}")
    word_item[field] = new_value
    return True


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
    wordlist_data = load_wordlist(wordlist_path)
    all_items: list[dict] = wordlist_data["words"]
    all_words = [item["word"].strip() for item in all_items]
    selected, requested_filter, missing_filter = _select_words(
        all_words,
        only_words,
        limit,
    )
    stem_conflicts = find_stem_conflicts(all_words)

    output_dir = output_dir or wordlist_path.parent / wordlist_path.stem
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    print(f"加载 MDX 索引：{mdx_path}")
    mdx = MdxIndex(mdx_path)

    print("加载 MDD 索引：")
    for path in mdd_paths:
        print(f"  - {path}")
    mdds = MddCollection(mdd_paths)

    word_reports: list[dict] = []
    total = len(selected)
    phonetics_updated = 0

    for number, (word_index, word) in enumerate(selected, start=1):
        print(f"[{number}/{total}] {word}")

        conflict = stem_conflicts.get(word_index)
        if conflict is not None:
            owner, stem = conflict
            print(
                f'  跳过：音频文件名主体冲突，"{owner}" 与 "{word}" '
                f'都会转换为 "{stem}"。'
            )
            word_reports.append(
                {
                    "word": word,
                    "status": "audio_stem_conflict",
                    "audio_stem": stem,
                    "conflict_with": owner,
                    "pronunciations": [],
                }
            )
            continue

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

        candidates = _primary_candidates(
            [
                candidate
                for html in records
                for candidate in parse_headword_pronunciations(html)
            ]
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

        word_item = all_items[word_index]
        for candidate in candidates:
            if _update_phonetic(word_item, candidate.accent, candidate.ipa):
                phonetics_updated += 1

        stem = audio_stem(word)
        successful_accents: set[str] = set()
        details: list[dict] = []

        for candidate in candidates:
            suffix = _extension_from_resource(candidate.resource)
            output_name = f"{stem}_{candidate.accent}{suffix}"
            output_path = audio_dir / output_name
            relative_path = output_path.relative_to(output_dir).as_posix()
            location = mdds.find(candidate.resource)

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

            successful_accents.add(candidate.accent)
            details.append(detail)

        has_uk = "uk" in successful_accents
        has_us = "us" in successful_accents
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

    report = {
        "schema_version": 1,
        "source": {
            "mdx": mdx_path.name,
            "mdds": [path.name for path in mdd_paths],
            "wordlist": wordlist_path.name,
        },
        "summary": {
            "requested_words": len(selected),
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
            "audio_stem_conflict": sum(
                item["status"] == "audio_stem_conflict" for item in word_reports
            ),
            "phonetics_updated": phonetics_updated,
        },
        "words": word_reports,
    }

    if phonetics_updated:
        wordlist_path.write_text(
            json.dumps(wordlist_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return report

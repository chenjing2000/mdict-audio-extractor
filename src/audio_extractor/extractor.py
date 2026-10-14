from pathlib import Path

from .adapter_oald import PronunciationCandidate, parse_headword_pronunciations
from .mdict_index import MddCollection, MdxIndex, find_mdd_files
from .audio_files import atomic_write, existing_audio
from .reporting import print_message, summarize_words
from .wordlist import (
    audio_stem, find_stem_conflicts, load_wordlist,
    resource_root, select_words, save_wordlist,
)


def _extension_from_resource(resource: str) -> str:
    suffix = Path(resource.replace("\\", "/")).suffix.lower()
    if suffix not in {".mp3", ".wav"}:
        raise ValueError(f"不支持的词典音频格式：{resource}")
    return suffix


def _primary_candidates(
    candidates: list[PronunciationCandidate],
) -> list[PronunciationCandidate]:
    """Keep one preferred recording per accent."""
    selected: dict[str, PronunciationCandidate] = {}

    for item in candidates:
        if item.accent not in selected:
            selected[item.accent] = item

    return [selected[accent] for accent in ("uk", "us") if accent in selected]


class DictionaryResources:
    """Lazy, per-run indexes and lookup cache shared by multiple wordlists."""

    def __init__(self, mdx_path: Path | None, mdd_paths: list[Path] | None, mdd_path: str | Path | None = None):
        self.mdx_path = mdx_path
        self.mdd_paths = mdd_paths
        self.mdd_path = mdd_path
        self.mdx = None
        self.mdds = None
        self.cache: dict[str, list[str]] = {}

    def lookup(self, word: str) -> list[str]:
        if self.mdx is None:
            if self.mdx_path is None:
                raise ValueError("提取缺失单词音频需要提供 MDX 路径。")
            print_message(f"加载 MDX 索引：{self.mdx_path}")
            self.mdx = MdxIndex(self.mdx_path)
        key = word.strip().casefold()
        if key not in self.cache:
            self.cache[key] = self.mdx.lookup_all(word)
        return self.cache[key]

    def resources(self):
        if self.mdds is None:
            if self.mdd_paths is None:
                # Resolve volumes only when a selected recording is actually needed.
                self.mdd_paths = find_mdd_files(self.mdx_path, self.mdd_path)
            print_message("加载 MDD 索引")
            self.mdds = MddCollection(self.mdd_paths)
        return self.mdds


def _update_phonetic(word_item: dict, accent: str, ipa: str | None) -> bool:
    if not isinstance(ipa, str) or not ipa.strip():
        return False

    field = f"phonetic_{accent}"
    new_value = ipa.strip()
    old_value = word_item.get(field, "")
    if old_value != new_value:
        message = f"  {accent.upper()} 音标：{old_value or '—'} -> {new_value}"
        print_message(message)
    word_item[field] = new_value
    return True


def extract(
    *,
    mdx_path: Path | None,
    mdd_paths: list[Path],
    wordlist_path: Path,
    output_dir: Path | None = None,
    limit: int | None = None,
    only_words: list[str] | None = None,
    dictionary: DictionaryResources | None = None,
    data: dict | None = None,
) -> dict:
    created_paths: list[Path] = []
    try:
        wordlist_data = load_wordlist(wordlist_path, data=data)
        all_items: list[dict] = wordlist_data["words"]
        all_words = [item["word"].strip() for item in all_items]
        selected, requested_filter, missing_filter = select_words(
            all_words,
            only_words,
            limit,
        )
        if missing_filter:
            print_message(f"词典提取：以下指定单词不在本词表，已跳过：{', '.join(missing_filter)}")
        stem_conflicts = find_stem_conflicts(all_words)

        output_dir = output_dir or resource_root(wordlist_path, wordlist_data)
        audio_dir = output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        dictionary = dictionary or DictionaryResources(mdx_path, mdd_paths)

        word_reports: list[dict] = []
        total = len(selected)
        phonetics_updated = 0

        for number, (word_index, word) in enumerate(selected, start=1):
            print_message(f"[{number}/{total}] {word}")
            stem = audio_stem(word)
            if not stem:
                word_reports.append({"word": word, "status": "empty_audio_stem", "pronunciations": []})
                print_message("  跳过：空音频文件名主体")
                continue

            conflict = stem_conflicts.get(word_index)
            if conflict is not None:
                owner, stem = conflict
                print_message(
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

            details: list[dict] = []
            pending = []
            for accent in ("uk", "us"):
                old = existing_audio(audio_dir / f"{stem}_{accent}.mp3")
                if old is not None:
                    details.append({"accent": accent, "status": "existing_audio_skipped",
                                    "output": old.relative_to(output_dir).as_posix()})
                    print_message(f"  {accent.upper()}: 已有音频跳过 {old.name}")
                else:
                    pending.append(accent)
            if not pending:
                word_reports.append({"word": word, "status": "existing_audio_skipped", "pronunciations": details})
                continue

            records = dictionary.lookup(word)
            if not records:
                details.extend({"accent": accent, "status": "mdx_entry_not_found"} for accent in pending)
                word_reports.append(
                    {
                        "word": word,
                        "status": "mdx_entry_not_found",
                        "mdx_records": 0,
                        "pronunciations": details,
                    }
                )
                print_message("  MDX 中没有找到词条")
                continue

            all_candidates = []
            for html in records:
                all_candidates.extend(parse_headword_pronunciations(html))
            candidates = _primary_candidates(all_candidates)
            if not candidates:
                details.extend({"accent": accent, "status": "headword_audio_not_found"} for accent in pending)
                word_reports.append(
                    {
                        "word": word,
                        "status": "headword_audio_not_found",
                        "mdx_records": len(records),
                        "pronunciations": details,
                    }
                )
                print_message("  找到词条，但没有识别到词头发音")
                continue

            word_item = all_items[word_index]
            successful_accents: set[str] = set()

            for candidate in candidates:
                if candidate.accent not in pending:
                    continue
                try:
                    suffix = _extension_from_resource(candidate.resource)
                except ValueError as exc:
                    details.append({"accent": candidate.accent, "status": "unsupported_audio_format", "error": str(exc)})
                    print_message(f"  {candidate.accent.upper()}: 提取失败：{exc}")
                    continue
                output_name = f"{stem}_{candidate.accent}{suffix}"
                output_path = audio_dir / output_name
                relative_path = output_path.relative_to(output_dir).as_posix()
                mdds = dictionary.resources()
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
                    print_message(
                        f"  {candidate.accent.upper()}: "
                        f"MDD 中未找到 {candidate.resource}"
                    )
                    continue

                detail["mdd"] = dictionary.mdd_paths[location.mdd_index].name
                detail["mdd_key"] = location.original_key

                try:
                    payload = mdds.read(location)
                    if not payload:
                        raise ValueError("词典音频内容为空。")
                    atomic_write(output_path, payload)
                    created_paths.append(output_path)
                    detail["status"] = "extracted"
                    detail["bytes"] = len(payload)
                    print_message(
                        f"  {candidate.accent.upper()}: "
                        f"{candidate.resource} -> {relative_path}"
                    )
                except (OSError, ValueError, TypeError) as exc:
                    detail["status"] = "audio_write_failed"
                    detail["error"] = str(exc)
                    details.append(detail)
                    print_message(f"  {candidate.accent.upper()}: 提取失败：{exc}")
                    continue

                # Only a newly written recording authorizes its paired IPA update.
                if _update_phonetic(word_item, candidate.accent, candidate.ipa):
                    phonetics_updated += 1
                if not candidate.ipa:
                    detail["ipa_missing"] = True
                    print_message(f"  {candidate.accent.upper()}: 对应 IPA 缺失，保留原音标")
                successful_accents.add(candidate.accent)
                details.append(detail)

            candidate_accents = {candidate.accent for candidate in candidates}
            for accent in pending:
                if accent not in candidate_accents:
                    details.append({"accent": accent, "status": "headword_audio_not_found"})

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
                "mdx": mdx_path.name if mdx_path else None,
                "mdds": [path.name for path in (dictionary.mdd_paths or [])],
                "wordlist": wordlist_path.name,
            },
            "summary": summarize_words(word_reports, phonetics_updated, requested_filter, missing_filter),
            "words": word_reports,
        }

        if created_paths:
            save_wordlist(wordlist_path, wordlist_data)

        return report
    except Exception:
        # Any later failure must not leave audio paired with uncommitted IPA.
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise

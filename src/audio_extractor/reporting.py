import sys


def print_message(message: str) -> None:
    """Escape unsupported console characters without changing stored data."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(message.encode(encoding, errors="backslashreplace").decode(encoding))


def summarize_words(word_reports: list[dict], phonetics_updated: int,
                    requested_filter: list[str], missing_filter: list[str]) -> dict:
    summary = {
        "requested_words": len(word_reports),
        "filter_words": requested_filter,
        "filter_words_not_in_wordlist": missing_filter,
        "phonetics_updated": phonetics_updated,
        "words_with_any_audio": 0,
        "words_with_uk_and_us": 0,
        "partial_words": 0,
        "mdx_entry_not_found": 0,
        "headword_audio_not_found": 0,
        "audio_not_extracted": 0,
        "audio_stem_conflict": 0,
        "empty_audio_stem": 0,
        "audio_extracted": 0,
        "existing_audio_skipped": 0,
        "audio_missing": 0,
        "audio_failed": 0,
        "ipa_missing": 0,
    }
    for word in word_reports:
        status = word["status"]
        if status in ("ok", "partial"):
            summary["words_with_any_audio"] += 1
        if status == "ok":
            summary["words_with_uk_and_us"] += 1
        elif status == "partial":
            summary["partial_words"] += 1
        elif status in ("mdx_entry_not_found", "headword_audio_not_found",
                        "audio_not_extracted", "audio_stem_conflict", "empty_audio_stem"):
            summary[status] += 1
        for detail in word["pronunciations"]:
            status = detail["status"]
            if status == "extracted":
                summary["audio_extracted"] += 1
            elif status == "existing_audio_skipped":
                summary["existing_audio_skipped"] += 1
            elif status in ("mdx_entry_not_found", "headword_audio_not_found", "mdd_resource_not_found"):
                summary["audio_missing"] += 1
            elif status in ("audio_write_failed", "unsupported_audio_format"):
                summary["audio_failed"] += 1
            if detail.get("ipa_missing"):
                summary["ipa_missing"] += 1
    return summary


def has_failures(report: dict) -> bool:
    if report.get("errors"):
        return True
    for item in report.get("files", [report]):
        if item.get("tts", {}).get("failed", 0):
            return True
        if item.get("summary", {}).get("audio_failed", 0):
            return True
    return False


def print_report(report: dict) -> None:
    """Show primary counts per audio file, one item per line."""
    summary = report["summary"]
    if summary:
        print_message(f"词典音频：\n提取成功：{summary['audio_extracted']}\n"
                      f"已有跳过：{summary['existing_audio_skipped']}\n"
                      f"缺失：{summary['audio_missing']}\n失败：{summary['audio_failed']}")
    tts = report["tts"]
    if not tts["enabled"]:
        print_message("TTS：已关闭")
    else:
        generated = tts["generated_uk"] + tts["generated_us"]
        reused = tts["reused_uk"] + tts["reused_us"]
        print_message(f"TTS：\n生成成功：{generated}\n已有跳过：{reused}\n生成失败：{tts['failed']}")

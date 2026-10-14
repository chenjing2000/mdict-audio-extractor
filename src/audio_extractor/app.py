from pathlib import Path

from .extractor import DictionaryResources, extract
from .example_audio import example_audio_synthesis
from .reporting import print_message
from .wordlist import WordListError, read_json


def _as_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def audio_extractor(
    wordlist_path: str | Path,
    mdx_path: str | Path | None = None,
    mdd_path: str | Path | None = None,
    *,
    limit: int | None = None,
    words: list[str] | None = None,
    uk_voice: str = "en-GB-SoniaNeural",
    us_voice: str = "en-US-JennyNeural",
    wait_seconds: float = 2,
) -> dict:
    """Process a JSON or folder: dictionary words, TTS examples and segments."""
    wordlist = _as_path(wordlist_path)
    if not wordlist.exists():
        raise FileNotFoundError(f"输入路径不存在：{wordlist}")
    if limit is not None and limit < 1:
        raise ValueError("limit 必须大于 0。")
    if wait_seconds < 0:
        raise ValueError("wait_seconds 不能小于 0。")

    if wordlist.is_dir():
        paths = sorted(wordlist.glob("*.json"), key=lambda p: (p.name.casefold(), p.name))
    else:
        paths = [wordlist]
    documents, skipped, errors = [], [], []
    for path in paths:
        try:
            data = read_json(path)
            kind = data.get("filetype")
            if kind is not None and not isinstance(kind, str):
                raise WordListError("filetype 必须是字符串。")
            if kind in {"vocabulary", "passage"} or (kind is None and isinstance(data.get("words"), list)):
                documents.append((path, kind, data))
            elif wordlist.is_file():
                raise WordListError("输入文件不是支持的单词本或 passage。")
            else:
                skipped.append(str(path))
        except (OSError, ValueError) as exc:
            if wordlist.is_file():
                raise
            errors.append({"file": str(path), "error": str(exc)})

    mdx, dictionary = None, None
    if any(kind != "passage" for _, kind, _ in documents):
        mdx = _as_path(mdx_path) if mdx_path is not None else None
        dictionary = DictionaryResources(mdx, None, mdd_path)

    reports = []
    for path, kind, data in documents:
        print_message(f"\n处理文件：{path}")
        try:
            if kind == "passage":
                report = {"summary": {}}
            else:
                report = extract(
                    mdx_path=mdx, mdd_paths=[], wordlist_path=path,
                    limit=limit, only_words=words, dictionary=dictionary, data=data)
            report["tts"] = example_audio_synthesis(
                path, uk_voice, us_voice, wait_seconds, limit=limit, words=words, data=data)
            report["file"] = str(path)
            reports.append(report)
            print_message(f"  词典：{report['summary']}")
            print_message(f"  TTS：{report['tts']}")
        except (OSError, ValueError, RuntimeError) as exc:
            if wordlist.is_file():
                raise
            errors.append({"file": str(path), "error": str(exc)})
            print_message(f"  文件处理失败：{exc}")

    if wordlist.is_file():
        return reports[0]
    print_message(f"\n批量完成：处理 {len(reports)}，无关文件跳过 {len(skipped)}，文件错误 {len(errors)}")
    return {"files": reports, "skipped_files": skipped, "errors": errors}

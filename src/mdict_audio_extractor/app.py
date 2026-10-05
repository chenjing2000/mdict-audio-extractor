from pathlib import Path

from .extractor import extract


def _as_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _numbered_mdds(base_mdd: Path) -> list[Path]:
    paths = [base_mdd]
    stem = base_mdd.with_suffix("")

    index = 1
    while True:
        candidate = Path(f"{stem}.{index}.mdd")
        if not candidate.exists():
            break
        paths.append(candidate)
        index += 1

    return paths


def find_mdd_files(mdx_path: Path, mdd_path: str | Path | None) -> list[Path]:
    """Return the main MDD and contiguous numbered MDD parts."""
    main_mdd = mdx_path.with_suffix(".mdd") if mdd_path is None else _as_path(mdd_path)
    if not main_mdd.is_file():
        raise FileNotFoundError(f"MDD 文件不存在：{main_mdd}")
    return _numbered_mdds(main_mdd)


def mdict_audio_extractor(
    wordlist_path: str | Path,
    mdx_path: str | Path,
    mdd_path: str | Path | None = None,
    *,
    overwrite: bool = False,
    limit: int | None = None,
    words: list[str] | None = None,
) -> dict:
    """Extract UK/US headword audio and update IPA returned by the MDX."""
    wordlist = _as_path(wordlist_path)
    mdx = _as_path(mdx_path)

    if not wordlist.is_file():
        raise FileNotFoundError(f"wordlist.json 不存在：{wordlist}")
    if not mdx.is_file():
        raise FileNotFoundError(f"MDX 文件不存在：{mdx}")
    if limit is not None and limit < 1:
        raise ValueError("limit 必须大于 0。")

    mdds = find_mdd_files(mdx, mdd_path)
    output = wordlist.parent / wordlist.stem

    print("当前配置：")
    print(f"  单词本：{wordlist}")
    print(f"  MDX：{mdx}")
    print(f"  主 MDD：{mdds[0]}")
    print(f"  输出目录：{output}")
    print(f"  覆盖已有音频：{'是' if overwrite else '否'}")

    if limit is not None:
        print(f"  最多处理：{limit} 个单词")

    if words:
        print("  仅处理：")
        for word in words:
            print(f"    - {word}")

    print("\n实际加载的 MDD：")
    for path in mdds:
        print(f"  - {path}")

    report = extract(
        mdx_path=mdx,
        mdd_paths=mdds,
        wordlist_path=wordlist,
        output_dir=output,
        overwrite=overwrite,
        limit=limit,
        only_words=words,
    )

    summary = report["summary"]
    print("\n完成：")
    print(f"  处理单词：{summary['requested_words']}")
    print(f"  英美音均成功：{summary['words_with_uk_and_us']}")
    print(f"  只有部分发音：{summary['partial_words']}")
    print(f"  MDX 无词条：{summary['mdx_entry_not_found']}")
    print(f"  有词条但无词头发音：{summary['headword_audio_not_found']}")
    print(f"  未能提取音频：{summary['audio_not_extracted']}")
    print(f"  重复单词跳过：{summary['duplicate_word']}")
    print(f"  文件名冲突跳过：{summary['audio_stem_conflict']}")
    print(f"  音标更新：{summary['phonetics_updated']}")
    print(f"  输出目录：{output}")

    return report

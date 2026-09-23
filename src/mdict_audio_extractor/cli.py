import argparse

from .app import extract_wordlist_audio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdict-audio-extractor",
        description=(
            "从 MDX/MDD 中提取 words_review 单词本的英音/美音，"
            "保存为本地 audio 文件并生成 audio.json。"
        ),
    )
    parser.add_argument("--wordlist", required=True, help="wordlist.json 路径。")
    parser.add_argument("--mdx", required=True, help="MDX 文件路径。")
    parser.add_argument(
        "--mdd",
        default=None,
        help="主 MDD 路径；省略时自动使用与 MDX 同名的 .mdd。",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出目录；默认使用 wordlist.json 所在目录。",
    )
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有音频。")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个单词。")
    parser.add_argument("--words", nargs="+", default=None, help="只处理指定单词。")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        extract_wordlist_audio(
            args.wordlist,
            args.mdx,
            args.mdd,
            output_dir=args.output,
            overwrite=args.overwrite,
            limit=args.limit,
            words=args.words,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

import argparse

from .app import mdict_audio_extractor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdict-audio-extractor",
        description="从 MDX/MDD 中提取单词或词组的英音/美音并更新可用 IPA。",
    )
    parser.add_argument("--wordlist", required=True, help="单词本 JSON 路径。")
    parser.add_argument("--mdx", required=True, help="MDX 文件路径。")
    parser.add_argument(
        "--mdd",
        default=None,
        help="主 MDD 路径；省略时自动使用与 MDX 同名的 .mdd。",
    )
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有音频。")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 个单词。")
    parser.add_argument("--words", nargs="+", default=None, help="只处理指定单词。")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        mdict_audio_extractor(
            args.wordlist,
            args.mdx,
            args.mdd,
            overwrite=args.overwrite,
            limit=args.limit,
            words=args.words,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

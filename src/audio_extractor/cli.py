import argparse

from .app import audio_extractor
from .reporting import has_failures, print_message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio_extractor",
        description="统一处理单词本/文章：词典提取单词发音和 IPA，Edge TTS 合成例句与片段。",
    )
    parser.add_argument("--wordlist", required=True, help="JSON 文件或包含单词本/passage 的文件夹。")
    parser.add_argument("--mdx", help="MDX 文件路径；仅处理 passage 时可省略。")
    parser.add_argument(
        "--mdd",
        default=None,
        help="主 MDD 路径；省略时自动使用与 MDX 同名的 .mdd。",
    )
    parser.add_argument("--limit", type=int, default=None, help="每本只处理前 N 个单词；passage 为前 N 个片段。")
    parser.add_argument("--words", nargs="+", default=None, help="只处理指定单词。")
    parser.add_argument("--uk-voice", default="en-GB-SoniaNeural")
    parser.add_argument("--us-voice", default="en-US-JennyNeural")
    parser.add_argument("--wait-seconds", type=float, default=2, help="TTS 失败重试前等待秒数。")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        report = audio_extractor(
            args.wordlist,
            args.mdx,
            args.mdd,
            limit=args.limit,
            words=args.words,
            uk_voice=args.uk_voice,
            us_voice=args.us_voice,
            wait_seconds=args.wait_seconds,
        )
        if has_failures(report):
            for item in report.get("errors", []):
                print_message(f"错误：{item['file']}：{item['error']}")
            parser.exit(1, "存在文件处理或音频生成失败，请查看以上报告。\n")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))

# mdict-audio-extractor

从 MDict 的 `MDX + MDD` 中批量提取单词词头的英音/美音，供 `words_review` 或其他程序直接读取普通音频文件。

当前解析器针对已验证的 Oxford/OALD 词条结构：

- 只提取词头发音；
- 忽略例句录音；
- 自动识别 UK / US；
- 自动加载 `.mdd`、`.1.mdd`、`.2.mdd` 等连续分卷；
- 输出统一命名的本地音频，如 `apple_uk.mp3`、`apple_us.mp3`；
- 生成 `audio.json` 和诊断用 `report.json`。

## 环境

需要 Python 3.11+，推荐使用 `uv`：

```bash
uv sync
```

运行测试：

```bash
uv run pytest
```

## 推荐用法：直接运行 main.py

修改 `main.py` 中 `if __name__ == "__main__":` 后的三个路径：

```python
WORDLIST_PATH = r"E:\path\to\wordlist.json"
MDX_PATH = r"D:\path\to\dictionary.mdx"
MDD_PATH = r"D:\path\to\dictionary.mdd"
```

然后直接点击 Run，或执行：

```bash
uv run python main.py
```

`MDD_PATH` 只需要填写主 `.mdd`。程序会自动继续寻找：

```text
dictionary.mdd
dictionary.1.mdd
dictionary.2.mdd
...
```

核心入口函数为：

```python
extract_wordlist_audio(
    wordlist_path,
    mdx_path,
    mdd_path,
    output_dir=None,
    overwrite=False,
    limit=None,
    words=None,
)
```

第一个参数始终是 `wordlist.json`。

## CLI

CLI 保留为备用入口，并与 `main.py` 共用同一套运行逻辑：

```bash
uv run mdict-audio-extractor \
  --wordlist "E:\path\to\wordlist.json" \
  --mdx "D:\path\to\dictionary.mdx" \
  --mdd "D:\path\to\dictionary.mdd"
```

如果主 MDD 与 MDX 同名且在同一目录，可省略 `--mdd`：

```bash
uv run mdict-audio-extractor \
  --wordlist "E:\path\to\wordlist.json" \
  --mdx "D:\path\to\dictionary.mdx"
```

可选参数：

```text
--output DIR       指定输出目录
--overwrite        覆盖已有音频
--limit N          只处理前 N 个单词
--words WORD ...   只处理单词本中指定的词
```

## 输出

默认输出到 `wordlist.json` 所在目录：

```text
wordlist-directory/
├── wordlist.json
├── audio.json
├── report.json
└── audio/
    ├── apple_uk.mp3
    ├── apple_us.mp3
    ├── record_uk_1.mp3
    └── record_uk_2.mp3
```

如果某一口音存在多个词头录音，则使用 `_1`、`_2` 编号。

`audio.json` 示例：

```json
{
  "schema_version": 1,
  "words": {
    "apple": {
      "uk": ["audio/apple_uk.mp3"],
      "us": ["audio/apple_us.mp3"]
    }
  }
}
```

所有路径均为相对路径，移动整个单词本目录不会失效。

## 设计说明

`words_review` 不需要依赖 MDict。这个工具负责：

```text
wordlist.json + MDX + MDD
            ↓
mdict-audio-extractor
            ↓
audio.json + audio/
```

`words_review` 只需要消费最终的 `audio.json` 和音频文件。

为保证几百个单词的批量提取速度，本项目固定使用 `mdict-utils==1.3.14`，并通过其内部 key 索引按 record 位置读取资源。因此升级 `mdict-utils` 时应重新运行测试和实际词典验证。

`xxhash` 是显式依赖，因为 `mdict-utils` 读取 MDict 3.0 时需要它。

## GitHub 注意事项

`.gitignore` 已排除：

- 虚拟环境和 Python 缓存；
- 测试临时文件；
- IDE 本地配置；
- `.mdx` / `.mdd` 大型词典文件；
- 提取出的音频；
- `audio.json` / `report.json`。

因此不要强制添加这些被忽略的词典或生成文件到仓库。

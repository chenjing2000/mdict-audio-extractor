# mdict-audio-extractor

这是一个给 `words_review` 单词本离线准备音频资源的小工具，目前包含两个彼此独立的功能：

1. 从 Oxford/OALD 的 `MDX + MDD` 中提取单词词头的 UK / US 真人发音；
2. 读取单词本中 `words[] -> senses[] -> eid + example`，使用 `edge-tts` 合成例句的 UK / US 音频。

两个功能只共用同一个单词本路径和统一的资源目录规则，不互相调用。

## 环境

需要 Python 3.11+，推荐使用 `uv`：

```bash
uv sync
```

运行测试：

```bash
uv run pytest
```

## 目录约定

资源目录名固定为单词本 JSON 文件去掉 `.json` 后的文件名。

例如：

```text
vocabulary/
├── IELTS_Band7_WordList.json
├── IELTS_Human_WordList.json
├── other_WordList.json
│
└── IELTS_Band7_WordList/
    ├── audio.json
    ├── examples.json
    ├── progress.json
    │
    ├── audio/
    │   ├── ubiquitous_uk.mp3
    │   └── ubiquitous_us.mp3
    │
    └── examples/
        ├── ubiquitous_e01_uk.mp3
        ├── ubiquitous_e01_us.mp3
        ├── articulate_e01_uk.mp3
        ├── articulate_e01_us.mp3
        ├── articulate_e02_uk.mp3
        └── articulate_e02_us.mp3
```

`progress.json` 由 `words_review` 管理，本工具不会创建或修改它。

MDX/MDD 提取函数会返回诊断信息字典，并在控制台打印摘要，但不会在单词本资源目录中保留 `report.json`。

## 推荐用法：直接运行 main.py

修改 `main.py` 中 `if __name__ == "__main__":` 后的路径，然后直接点击 Run：

```python
WORDLIST_PATH = r"E:\path\to\IELTS_Band7_WordList.json"
MDX_PATH = r"D:\path\to\dictionary.mdx"
MDD_PATH = r"D:\path\to\dictionary.mdd"
```

### 1. 单词真人发音

```python
mdict_audio_extractor(
    WORDLIST_PATH,
    MDX_PATH,
    MDD_PATH,
)
```

默认生成：

```text
<wordlist.stem>/
├── audio.json
└── audio/
```

`MDD_PATH` 只需要填写主 `.mdd`，程序会自动继续寻找：

```text
dictionary.mdd
dictionary.1.mdd
dictionary.2.mdd
...
```

### 2. 例句 TTS

```python
example_audio_synthesis(
    WORDLIST_PATH,
)
```

函数默认参数为：

```python
example_audio_synthesis(
    wordlist_path,
    uk_voice="en-GB-SoniaNeural",
    us_voice="en-US-JennyNeural",
    wait_seconds=2,
)
```

`main.py` 已在调用旁边列出常用 UK / US voice，想换音色时取消对应参数的注释即可。

`wait_seconds` 只在一次 TTS 失败后、第二次重试前等待。正常生成成功时不会额外等待。

## 例句读取规则

当前单词本结构按下面的真实格式读取：

```text
words[]
  ├── wid
  └── senses[]
       ├── eid
       └── example
```

每个非空 `example` 必须带有合法 `eid`，格式为恰好 6 位数字字符串，例如 `501372`，并允许以 `0` 开头。`eid` 由 WordList 生成，本工具只读取并原样写入 `examples.json`，不会自行生成。

音频文件仍按例句出现顺序编号：

```text
word_e01_uk.mp3
word_e01_us.mp3
word_e02_uk.mp3
word_e02_us.mp3
```

没有 `example` 的 sense 会直接跳过。存在 `example` 但缺少或包含无效 `eid` 时，该例句会被跳过并在控制台提示。重复 `eid` 会直接报错，避免建立错误映射。

同一 WordList 中的 `word` 也必须唯一（忽略大小写）；同一拼写的多个含义应放在同一个 Word 的 `senses` 中。

WordList 仍使用 `schema_version: 1`，但当前工具只接受新的 `wid` / `eid` 字段结构，不兼容旧的 `id` 字段格式。

## examples.json

例句映射文件保持简单：

```json
{
  "schema_version": 1,
  "words": {
    "ubiquitous": [
      {
        "eid": "271828",
        "text": "Smartphones have become ubiquitous in modern society.",
        "uk": "examples/ubiquitous_e01_uk.mp3",
        "us": "examples/ubiquitous_e01_us.mp3"
      }
    ]
  }
}
```

`eid` 是 Words Review 与例句音频之间的唯一关联键；`text` 继续保留用于人工检查和增量安全判断。

增量规则：

- `eid` 相同、`text` 相同且对应音频文件存在：复用已有文件；
- `eid` 相同、`text` 相同但只缺一个口音：只补缺失的文件；
- 英文例句重新生成时应同时生成新的 `eid`，因此新 `eid` 会生成新的音频映射；
- 如果手工违反规则，在 `eid` 不变的情况下修改 `text`，程序仍会重新生成该例句音频，避免复用错误内容；
- TTS 第一次失败后等待 `wait_seconds`，再重试一次；
- 第二次仍失败则记录错误并继续处理后续例句。

`examples.json` 每次都根据当前单词本重新构造；旧 MP3 不会自动删除。Words Review 只按 `eid` 精确匹配，不依赖 `text` 或 e01/e02 顺序。

如果修改了 `uk_voice` 或 `us_voice` 并希望全部例句改用新音色，请手动删除对应单词本资源目录中的 `examples/` 和 `examples.json` 后重新运行。程序不会为此额外保存 voice 元数据。

## CLI

CLI 继续保留为 MDX/MDD 单词真人发音的备用入口，并复用 `mdict_audio_extractor()`：

```bash
uv run mdict-audio-extractor \
  --wordlist "E:\path\to\wordlist.json" \
  --mdx "D:\path\to\dictionary.mdx" \
  --mdd "D:\path\to\dictionary.mdd"
```

如果主 MDD 与 MDX 同名且在同一目录，可省略 `--mdd`。

可选参数：

```text
--output DIR       指定输出目录；默认 <wordlist.parent>/<wordlist.stem>/
--overwrite        覆盖已有单词发音
--limit N          只处理前 N 个单词
--words WORD ...   只处理单词本中指定的词
```

## audio.json

`audio.json` 只管理 `audio/` 中的单词真人发音：

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

`examples.json` 只管理 `examples/` 中的例句 TTS，两者互不修改对方的数据。

## GitHub 注意事项

`.gitignore` 已排除：

- 虚拟环境和 Python 缓存；
- 测试临时文件；
- IDE 本地配置；
- `.mdx` / `.mdd` 大型词典文件；
- 提取或合成的音频文件；
- `audio.json`、`examples.json`、`progress.json`。

不要使用 `git add -f` 强制提交词典或生成的音频资源。

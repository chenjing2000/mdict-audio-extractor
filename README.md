# mdict-audio-extractor

给 ReciteWords 单词本离线准备音频的小工具，包含两个低耦合功能：

1. `mdict_audio_extractor()`：从 Oxford/OALD 的 `MDX + MDD` 提取单词或词组的 UK / US 真人发音，并用 MDX 返回的 IPA 更新 `phonetic_uk` / `phonetic_us`；
2. `example_audio_synthesis()`：读取 `words[] -> senses[] -> example`，使用 `edge-tts` 合成例句 UK / US 音频。

当前版本只支持新的双音标单词本格式，不兼容旧 `wid` / 单一 `phonetic` 格式，也不自动迁移旧文件。

## 环境

需要 Python 3.11+，推荐使用 `uv`：

```bash
uv sync
uv run pytest
```

## 单词本格式

顶层必须包含非空 `words` 数组。每个单词至少包含：

```text
word
phonetic_uk
phonetic_us
senses
```

要求：

- `word`：非空字符串，可为单词或词组；
- `phonetic_uk` / `phonetic_us`：字符串，可为空；
- `senses`：非空数组；
- 每个 sense 必须包含非空 `pos` 和 `chinese_meaning`；
- `eid` 可选；存在时必须是全词库唯一的六位 ASCII 数字字符串；
- 不使用 `wid`，也不接受旧 `phonetic` 代替双音标字段。

## 目录结构

资源目录固定为：

```python
wordlist_path.parent / wordlist_path.stem
```

以 `IELTS_Band7_WordList.json` 为例：

```text
vocabulary/
│
├── IELTS_Band7_WordList.json
│
└── IELTS_Band7_WordList/
    │
    ├── progress.json
    ├── examples.json
    │
    ├── audio/
    │   ├── ubiquitous_uk.mp3
    │   ├── ubiquitous_us.mp3
    │   ├── take_care_of_uk.mp3
    │   └── take_care_of_us.mp3
    │
    └── examples/
        ├── ubiquitous_e01_uk.mp3
        ├── ubiquitous_e01_us.mp3
        ├── articulate_e01_uk.mp3
        ├── articulate_e01_us.mp3
        ├── articulate_e02_uk.mp3
        └── articulate_e02_us.mp3
```

`progress.json` 由背词程序管理，本工具不会创建或修改它。

单词音频文件名已经是确定性的，背词程序可直接查找 `audio/{stem}_uk.mp3` / `audio/{stem}_us.mp3`，因此本版本不再生成 `audio.json`。

## word_stem 规则

只在计算或生成路径时转换 `word`，JSON 中原始 `word` 不改变。

规则：

1. 去除首尾空白；
2. 每个 `[^0-9a-zA-Z]` 字符替换为 `_`；
3. 不合并连续 `_`；
4. 不删除首尾 `_`；
5. 不改变 ASCII 字母大小写。

例如：

```text
take care of  -> take_care_of
one's own     -> one_s_own
well-being    -> well_being
a / b         -> a___b
café          -> caf_
```

单词真人发音命名：

```text
audio/{word_stem}_uk.mp3
audio/{word_stem}_us.mp3
```

如果词典资源是 WAV，则保留 `.wav`。

例句音频命名：

```text
examples/{word_stem}_e01_uk.mp3
examples/{word_stem}_e01_us.mp3
examples/{word_stem}_e02_uk.mp3
examples/{word_stem}_e02_us.mp3
```

例句编号只统计非空 `example`，每个单词从 `01` 重新开始。

## 重复与路径冲突

`word` 按 `strip().casefold()` 判断重复。不同 `word` 还会按不区分大小写的 `word_stem` 检查文件名冲突。

例如：

```text
well-being -> well_being
well being -> well_being
```

处理规则：

- 首次出现的词正常处理；
- 后续重复 `word` 或冲突 `word_stem` 打印提示并跳过；
- 不自动追加编号；
- 不因单个冲突中止整本词库；
- 最终统计汇总跳过数量。

## 直接运行 main.py

在 `if __name__ == "__main__":` 下修改路径，然后点击 Run：

```python
WORDLIST_PATH = r"E:\path\to\IELTS_Band7_WordList.json"
MDX_PATH = r"D:\path\to\dictionary.mdx"
MDD_PATH = r"D:\path\to\dictionary.mdd"
```

### 单词真人发音

```python
mdict_audio_extractor(
    WORDLIST_PATH,
    MDX_PATH,
    MDD_PATH,
)
```

主 MDD 只需填写 `dictionary.mdd`，程序会继续寻找连续分卷：

```text
dictionary.1.mdd
dictionary.2.mdd
...
```

可选参数：

```python
mdict_audio_extractor(
    WORDLIST_PATH,
    MDX_PATH,
    MDD_PATH,
    # overwrite=False,
    # limit=None,
    # words=None,
)
```

MDX 返回某个口音 IPA 时，会覆盖对应的 `phonetic_uk` 或 `phonetic_us`。没有可靠 IPA 时保留原值，不用另一口音替代。只有实际发生音标更新时才写回单词本文件。

### 例句 TTS

```python
example_audio_synthesis(
    WORDLIST_PATH,
    # uk_voice="en-GB-SoniaNeural",
    # us_voice="en-US-JennyNeural",
    # wait_seconds=2,
)
```

默认 voice：

```text
UK: en-GB-SoniaNeural
US: en-US-JennyNeural
```

`wait_seconds` 只在第一次 TTS 失败后、第二次重试前等待。正常成功时不额外等待。

## examples.json

`examples.json` 保存例句文本和 UK / US 音频相对路径，例如：

```json
{
  "schema_version": 2,
  "words": {
    "articulate": [
      {
        "id": "01",
        "text": "She was able to articulate her concerns effectively during the meeting.",
        "uk": "examples/articulate_e01_uk.mp3",
        "us": "examples/articulate_e01_us.mp3"
      },
      {
        "id": "02",
        "text": "He is a highly articulate speaker.",
        "uk": "examples/articulate_e02_uk.mp3",
        "us": "examples/articulate_e02_us.mp3"
      }
    ]
  }
}
```

增量规则：

- 同一 `word_stem`、例句编号和 `text` 未变化且文件存在：复用；
- 只缺一个口音：只补该口音；
- `text` 改变：重新生成该例句 UK / US；
- 第一次 TTS 失败后等待 `wait_seconds`，再重试一次；
- 第二次仍失败则记录错误并继续；
- `examples.json` 每次按当前单词本重新构造；旧的孤立 MP3 不自动删除。

## CLI

CLI 只负责 MDX/MDD 单词真人发音，并复用 `mdict_audio_extractor()`：

```bash
uv run mdict-audio-extractor \
  --wordlist "E:\path\to\wordlist.json" \
  --mdx "D:\path\to\dictionary.mdx" \
  --mdd "D:\path\to\dictionary.mdd"
```

如果主 MDD 与 MDX 同名且在同一目录，可省略 `--mdd`。

可选参数：

```text
--overwrite        覆盖已有单词发音
--limit N          只处理前 N 个单词
--words WORD ...   只处理指定单词
```

## GitHub

`.gitignore` 已排除虚拟环境、缓存、构建产物、MDX/MDD、生成音频、生成的资源 JSON 和压缩包。不要使用 `git add -f` 强制提交词典或生成音频。

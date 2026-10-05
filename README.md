# mdict_audio_extractor

从 MDict 的 MDX/MDD 中提取单词或词组的英式、美式词头发音，并可使用 `edge-tts` 为单词本中的英文例句生成英音和美音。

程序面向当前 ReciteWords 单词本格式，不兼容旧单音标字段和旧六位 `eid`。

## 功能

- 从 MDX 查找单词或词组；
- 从一个或多个 MDD 分卷中提取词头 UK / US 音频；
- MDX 能返回 IPA 时，覆盖单词本对应的 `phonetic_uk` / `phonetic_us`；
- 为带 `eid` 的英文例句生成 UK / US TTS；
- 单词音频和例句音频均使用确定性文件名，不生成 `audio.json` 或 `examples.json`；
- 后续 `word_stem` 冲突词只提示并跳过全部音频，不中止整本词库。

## 单词本要求

顶层必须包含非空 `words` 数组。每个单词至少包含：

```json
{
  "word": "articulate",
  "phonetic_uk": "/ɑːˈtɪkjuleɪt/",
  "phonetic_us": "/ɑːrˈtɪkjuleɪt/",
  "senses": [
    {
      "pos": "v.",
      "chinese_meaning": "清晰表达",
      "eid": "01",
      "example": "She was able to articulate her concerns effectively during the meeting."
    },
    {
      "pos": "adj.",
      "chinese_meaning": "口才好的；表达清晰的",
      "eid": "02",
      "example": "He is a highly articulate speaker."
    }
  ]
}
```

主要规则：

- `word` 非空，按 `strip().casefold()` 比较后在单词本内唯一；
- 必须有 `phonetic_uk`、`phonetic_us`，允许为空字符串；
- `senses` 必须非空；每个 sense 必须有非空 `pos`、`chinese_meaning`；
- `eid` 可省略；存在时必须是 `01` 到 `99` 的两位 ASCII 数字；
- `eid` 只在当前单词内使用，并对应该单词按 `senses` 顺序出现的实际非空英文例句序号；
- 有 `eid` 时必须同时有非空 `example`；
- 没有 `eid` 的例句仍是合法数据，但本工具不会为它生成例句音频。

## 文件名规则

单词或词组只在计算音频文件名时转换为 `word_stem`：

1. 对 `word` 执行 `strip()`；
2. 每一个 `[^0-9a-zA-Z]` 字符替换为英文下划线 `_`；
3. 不合并连续下划线；
4. 不删除首尾下划线；
5. 不改变 ASCII 字母大小写。

例如：

```text
take care of -> take_care_of
one's own    -> one_s_own
well-being   -> well_being
a / b        -> a___b
café         -> caf_
```

转换只用于文件路径，JSON 中的原始 `word` 不修改。

## 输出目录

以 `IELTS_Band7_WordList.json` 为例：

```text
vocabulary/
│
├── IELTS_Band7_WordList.json
│
└── IELTS_Band7_WordList/
    │
    ├── progress.json              # 由 ReciteWords 管理，本工具不创建
    │
    ├── audio/
    │   ├── articulate_uk.mp3
    │   ├── articulate_us.mp3
    │   ├── take_care_of_uk.mp3
    │   └── take_care_of_us.mp3
    │
    └── examples/
        ├── articulate_e01_uk.mp3
        ├── articulate_e01_us.mp3
        ├── articulate_e02_uk.mp3
        └── articulate_e02_us.mp3
```

资源目录固定为：

```python
resource_dir = wordlist_path.parent / wordlist_path.stem
```

### 单词音频

```text
audio/{word_stem}_uk.mp3
audio/{word_stem}_us.mp3
```

MDX 解析出的某个口音 IPA 非空时，会覆盖原单词本对应的 `phonetic_uk` 或 `phonetic_us`；没有返回的口音保留原值。

### 例句音频

程序直接读取 sense 中已有的 `eid`，不自行计算例句 ID：

```text
examples/{word_stem}_e{eid}_uk.mp3
examples/{word_stem}_e{eid}_us.mp3
```

例如：

```text
articulate + eid "01" -> articulate_e01_uk.mp3
                         articulate_e01_us.mp3

articulate + eid "02" -> articulate_e02_uk.mp3
                         articulate_e02_us.mp3
```

没有 `eid` 的非空例句会提示并跳过，不自动补 ID。

已有同名例句 MP3 时直接复用。若修改了例句文本但保留相同 `eid`，请删除对应旧 MP3 后重新运行，以便重新合成。

## word_stem 冲突

`words` 数组顺序决定 `word_stem` 的首次拥有者，比较时不区分大小写。

例如：

```text
well-being -> well_being
well being -> well_being
```

第一个词获得 `well_being` 的音频资格。后一个词：

- 保留在单词本中；
- 输出冲突提示；
- 跳过该词的 UK / US 单词音频；
- 跳过该词的全部 UK / US 例句音频；
- 继续处理后面的词。

首次拥有者即使查词失败、TTS 失败或没有生成任何文件，也不会把这个 `word_stem` 让给后面的词。

## 安装

推荐使用 `uv`：

```bash
uv sync
```

## 直接运行 main.py

编辑 `main.py` 中的路径后直接运行：

```python
mdict_audio_extractor(
    WORDLIST_PATH,
    MDX_PATH,
    MDD_PATH,
)

example_audio_synthesis(
    WORDLIST_PATH,
    # uk_voice="en-GB-SoniaNeural",
    # us_voice="en-US-JennyNeural",
    # wait_seconds=2,
)
```

`wait_seconds` 只在 TTS 第一次失败后、第二次重试前等待。正常成功时不会固定等待。

## CLI

CLI 只负责 MDX/MDD 单词发音提取：

```bash
uv run mdict-audio-extractor \
  --wordlist "E:\\path\\IELTS_Band7_WordList.json" \
  --mdx "D:\\path\\Oxford.mdx" \
  --mdd "D:\\path\\Oxford.mdd"
```

可选参数：

```text
--overwrite      覆盖已有单词音频
--limit N        只处理前 N 个目标词
--words ...      只处理指定单词
```

如果主 MDD 后还有连续编号分卷，例如 `.1.mdd`、`.2.mdd`，程序会自动一并加载。

## 测试

```bash
uv run pytest
```

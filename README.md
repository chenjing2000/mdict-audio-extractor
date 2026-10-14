# audio_extractor

统一为 ReciteWords 和 ReadArticles 准备 UK/US 音频。单词/词组仅从牛津高阶 MDX/MDD 提取；ReciteWords 例句和 ReadArticles passage 片段用 Edge TTS 合成。

## 使用

```python
from audio_extractor.app import audio_extractor

report = audio_extractor(
    r"C:\pywork\ielts\雅思词以类记",  # 文件夹或单个 JSON
    r"D:\Dictionaries\Oxford.mdx",
    r"D:\Dictionaries\Oxford.mdd",
    # uk_voice="en-GB-SoniaNeural",
    # us_voice="en-US-JennyNeural",
    # wait_seconds=2,
)
```

ReadArticles 输入文章目录。只扫描直属 JSON，不递归；无关文件跳过，格式错误报告。仅合成句子或所有单词音频都已有时，无须词典。main.py 只调用一次统一入口，保留原路径配置，修改输入路径即可。

```powershell
uv sync
uv run audio_extractor --wordlist "C:\path\folder" --mdx "D:\dict\Oxford.mdx"
uv run audio_extractor --wordlist "C:\path\Article.json"
```

省略 --mdd 时使用 MDX 同名主 MDD，并发现连续的 .1.mdd、.2.mdd 分卷。

- --limit N：每本前 N 个单词及其例句；passage 为前 N 个片段。
- --words ...：只处理指定单词及其例句，不过滤 passage。
- --uk-voice / --us-voice：默认 en-GB-SoniaNeural / en-US-JennyNeural。
- --wait-seconds：TTS 首次失败后重试前等待，默认 2 秒；成功不等待。

不覆盖已有音频，API 和 CLI 均不提供覆盖选项。

## 数据分流

| 文件 | 内容 | 来源 |
| --- | --- | --- |
| ReciteWords 单词本 | words[].word | MDX/MDD |
| 同一本中的例句 | senses[].example，有有效 eid | Edge TTS |
| ReadArticles vocabulary | filetype=vocabulary 的 words[].word | MDX/MDD |
| ReadArticles passage | filetype=passage，paragraphs[].paragraph[] 的 sid/text | Edge TTS |

使用明确字段，不按名称包含 sid/eid 猜测类型。next_sid 不是片段。单词缺失绝不转入 TTS。

ReciteWords 保留现有校验：非空 words/senses，字符串 phonetic_uk/us，非空 word/pos/chinese_meaning；eid 可省略，提供时为 01–99 两位 ASCII 数字，对应当前词按 senses 顺序出现的非空例句编号。无 eid 的例句不合成。

vocabulary 使用 words/meanings，允许空词表、空 meanings 和省略音标；已有音标不能为 null。词条不能为空或重复。保存词表时删除旧词条 audio 字段，保留其他字段。

passage 使用唯一 s001–s999，text 非空且无首尾空白，next_sid 大于现有编号且不超过 1000。程序不修改 passage JSON，不生成整篇文章音频。

## 命名与目录

stem：去首尾空白、转小写，将连续非 ASCII a-z/0-9 字符换成一个下划线，再去首尾下划线。不改变原始 word。

```text
One's Own -> one_s_own
A / B     -> a_b
café      -> caf
!!!       -> 空 stem

ReciteWords:
  Plant.json
  Plant/audio/shrub_uk.mp3 或 .wav
  Plant/audio/shrub_us.mp3 或 .wav
  Plant/audio_sentences/shrub_e01_uk.mp3
  Plant/audio_sentences/shrub_e01_us.mp3

ReadArticles:
  Article.json
  Article.vocabulary.json
  audio/loyalty_uk.mp3 或 .wav
  audio/loyalty_us.mp3 或 .wav
  audio_sentences/s001_uk.mp3
  audio_sentences/s001_us.mp3
```

目标口音有 MP3 或 WAV 就跳过，不验证来源、大小或解码，不覆盖、不更新对应 IPA，也不计为新提取成功。按 MP3、WAV 顺序检查。旧 examples/、audio_vocabulary/、audio_segments/、命名和索引不参与查找，不迁移、不删除。

每本按 words 顺序立即为首个非空 stem 保留资格，后续冲突词保留正文但跳过单词和例句音频。首词失败也不让出资格；空 stem 不生成音频。

## 词典录音和 IPA

解析器针对现有 OALD HTML，不保证任意 MDX 词典适用。

- 每个口音严格取词头区域第一个录音及对应 IPA，不按资源名 _1/_2 排序。
- 首录音缺失不改选后续变体，不用 TTS 补单词或拼接词组。
- 音频成功写入后，用对应非空 IPA 更新该口音，即使音标已有或新旧相同。
- 没有对应 IPA 时保留原值并报告 ipa_missing，不猜音标。
- 保留资源实际 MP3/WAV 格式，不仅改扩展名。

一次运行共用延迟加载的词典索引和查词缓存。音频、JSON、TTS 先完整写临时文件再替换；JSON 保存失败回滚该词表本次新增词典音频，不改已有文件。

## 报告与验证

单文件返回词典 summary、逐词逐口音详情和 tts 统计；目录返回 files、skipped_files、errors。局部文件错误后继续后续文件；CLI 有文件错误、词典音频写入失败或 TTS 合成失败时退出状态非零。TTS 失败重试一次，不留不完整目标文件。

```powershell
uv run pytest
```

单元测试替换词典读盘和网络 TTS 边界，不代替真实词典录音及在线合成验证。

## 模块设计

程序使用直接函数调用和少量具体类，不使用插件框架、依赖注入容器或事件总线。

| 模块 | 职责 |
| --- | --- |
| app.py | 扫描输入、判断文件类型、协调词典提取和句子合成 |
| wordlist.py | JSON 读取、校验和保存，命名、词条筛选、SID 任务准备 |
| extractor.py | 词典提取流程、共享词典缓存、IPA 更新及新增音频回滚 |
| adapter_oald.py | 将 OALD HTML 解析为对应的口音、录音和 IPA |
| mdict_index.py | MDX/MDD 索引、分卷发现、完整记录读取 |
| example_audio.py | EID/SID 句子任务的 TTS 合成、重试和跳过 |
| audio_files.py | 已有 MP3/WAV 查找和临时文件完整写入 |
| reporting.py | 控制台安全输出、结果计数和失败判断 |
| cli.py / main.py | 命令行参数与直接运行配置 |

数据校验与保存集中在数据模块；音频模块不负责改写 passage。统计使用普通循环。记录类用于明确字段，生成器用于按需遍历词典块；没有为未来需求添加抽象接口或配置层。

当前模块审查和清理说明见 [模块设计审查](docs/Module-Design.md)。

## 生成文件

`.pytest_cache/`、`.pytest_tmp/`、`__pycache__/` 和 `build/` 中的验证资源、临时缓存可删除并重新生成。`.venv/` 是运行环境，`uv.lock` 是依赖锁文件；清理时保留它们，也保留源码、测试、示例及用户原始词库/音频。

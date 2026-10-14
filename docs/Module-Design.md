# 模块设计与整理

日期：2026-10-14。本记录反映当前源码、入口、测试、依赖、示例与生成文件的审查结果；早期词典兼容性整改见 [历史审查记录](Code-Review-2026-10-14.md)。

## 设计结论

当前规模适合直接函数调用和少量具体类。模块依赖没有循环，各自负责数据、词典、合成、文件工具或报告；无需通用提取框架、提供器接口、继承层次、插件、依赖注入容器或事件总线。本轮不改变用户数据格式和音频命名。

| 模块 | 职责 | 项目内依赖 |
| --- | --- | --- |
| app | 扫描输入，协调词典提取与可选句子合成 | extractor、example_audio、wordlist、reporting |
| wordlist | JSON 读取/校验/保存、stem、筛选、SID 任务 | audio_files |
| extractor | 单词录音提取、IPA 更新、共享缓存和回滚 | wordlist、adapter_oald、mdict_index、audio_files、reporting |
| example_audio | EID/SID 合成、重试、已有文件跳过 | wordlist、audio_files、reporting |
| mdict_index | 词典索引、分卷、完整记录解码 | 无 |
| adapter_oald | HTML 中的口音、录音和 IPA 配对 | 无 |
| audio_files | 文件查找和完整写入 | 无 |
| reporting | 安全日志、统计、显示和失败判断 | 无 |
| cli / main | 命令行参数或直接运行配置 | app；cli 另用 reporting |

函数按实际数据流分配。词典私有读取接口集中在 mdict_index，其他模块不接触依赖的内部字段。JSON 保存属于 wordlist，文件工具不理解业务格式，报告模块不执行提取或合成。

保留 ResourceLocation、PronunciationCandidate 两个简单不可变记录，避免含义不清的元组；保留 DictionaryResources 的延迟索引和本次运行缓存，避免重复加载大词典。生成器仅用于按需遍历词典块；它是减少读取和内存的实际需求。类型标注、普通列表/集合推导保留，不引入装饰器框架、泛型层或高阶函数。

两种词表校验规则存在合理差异，少量相似检查保持直接代码。单词提取与句子合成的异常边界不同，不能为了减少文本重复强行合成通用执行器。

## 本轮整改

1. 原先控制台计入“不支持的音频格式”失败，CLI 却只检查写入失败，可能以成功状态退出。现在缺失和失败均在 summarize_words 的一次循环中计算，print_report 和 has_failures 直接使用结果。新增 summary.audio_missing 和 summary.audio_failed，保留原报告字段和逐口音错误详情。词典缺失仍不属于执行失败。
2. 不支持的词典音频格式现在输出具体错误，并让 CLI 非零退出；失败录音不写入文件、不更新 IPA。
3. TTS 创建目录和临时文件原先在错误处理之外，会中断整个文件。现在与写入放在同一边界内，记录该口音失败后继续其他口音和任务；临时文件只在实际创建后清理。
4. 文档使用当前结论和验证结果，历史词典整改独立保留，避免混淆不同测试轮次。

## 保留的行为与限制

- 单词仅从 MDX/MDD 提取；每个口音选择词头第一个录音和对应 IPA，新录音成功写入后才更新 IPA。
- 已有 MP3/WAV 按现有规则跳过，不核实来源、大小或解码，也不计为提取成功。
- TTS 默认关闭，由 tts_enabled / --tts 显式开启；关闭时不进入合成流程。具体实现仅调用 edge_tts.Communicate(text, voice)。
- 原 words_with_any_audio、words_with_uk_and_us 和 partial_words 仍反映本轮新提取状态，不是磁盘上全部已有音频的库存统计。
- ReadArticles 同目录共享音频命名空间：多个 passage 文件中相同 sid 指向同一音频文件；多个 vocabulary 文件相同 stem 也共享单词音频。应把不同文章放在各自目录，避免后来文件跳过先前音频。保留消费者约定的目录布局，不自动迁移。
- 整体提取或 JSON 保存失败时回滚该词表本次新增录音；既有文件和用户数据保留。

## 本轮验证与清理

完整测试 75 项通过，包括双格式分流、首录音及 IPA、MP3/WAV 跳过、stem 资格、TTS 开关/重试/临时文件清理、CLI 状态和新增错误边界回归。真实小型 MDX/MDD 测试覆盖 Unicode/UTF-16、空资源、大小写扩展名、v1/v2 跨块读取和按格式构造的 v3 记录段。独立只读复核检查模块职责和修改差异。

本轮未重新执行大型牛津词典提取或在线 TTS 合成；早期真实 zoology 验证属于历史证据。用户已确认升级 edge-tts 后可下载，本轮测试使用替代网络边界。

清理测试临时目录、pytest 缓存和字节码缓存。保留 .venv、uv.lock、源码、测试、示例、历史审查文档及 main.py 中用户选择的路径/TTS 配置，不删除外部词库或已有音频。

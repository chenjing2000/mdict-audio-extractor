# 模块设计与整理

日期：2026-10-14。范围：全部源码、入口、测试、依赖配置、示例与生成文件。

## 结论

程序规模适合直接的模块函数调用。数据记录、词典索引和一次运行的缓存有明确用途；没有必要改成通用提取框架，也不需要继承层次、插件、依赖注入容器或事件总线。少量分支和相似代码保留在各自业务流程内，避免为短小代码增加抽象。

## 职责与依赖

| 模块 | 内容 | 主要项目内依赖 |
| --- | --- | --- |
| app | 输入扫描与流程协调 | extractor、example_audio、wordlist、reporting |
| wordlist | JSON 格式校验/保存、stem、筛选、passage 任务 | audio_files |
| extractor | 单词提取、IPA、缓存、回滚 | wordlist、adapter_oald、mdict_index、audio_files、reporting |
| example_audio | 句子 TTS、重试、已有文件跳过 | wordlist、audio_files、reporting |
| mdict_index | 词典索引、分卷、记录区间解码 | 无其他项目模块 |
| adapter_oald | HTML 发音与 IPA 配对 | 无其他项目模块 |
| audio_files | 文件查找与完整写入 | 无其他项目模块 |
| reporting | 安全日志、计数、失败判断 | 无其他项目模块 |
| cli / main | 参数或路径配置 | app；cli 另使用 reporting |

依赖没有循环。文件格式规则不依赖音频执行模块；报告模块不调用提取或合成。新增 reporting 只包含直接函数，没有报告对象、渲染接口或回调机制。

## 必要整改

- 合并 extract 和 _extract，删除重复参数转发。一次 try 覆盖提取至 JSON 保存，异常时删除本次新增音频并继续抛出异常。
- JSON 保存从 audio_files 移至 wordlist，使文件工具不承担数据格式清理。
- passage 校验和任务准备从 TTS 模块移至 wordlist，使 TTS 主要负责句子合成。
- 多次嵌套生成器统计改为一次普通循环；CLI 也使用明确的循环检查失败。
- 单词筛选函数不再打印日志；调用方解释自己跳过的词。TTS 直接遍历筛选结果，不再建立索引集合后遍历整本词表。
- 所有业务日志统一处理控制台字符编码。GBK 下文件名、单词、句子和 IPA 中无法编码的字符仅在日志中转义，JSON 和音频文本保持完整 Unicode。
- 修复 UTF-16 MDX 的解码顺序：先解码文本，再去除文本空白。原先先 strip 原始字节可能删除半个字符，误报合法词条损坏。MDD 二进制保持原样。

ResourceLocation 和 PronunciationCandidate 两个小型不可变记录保留，字段名比匿名元组清楚。DictionaryResources 保留一次运行的索引和查词缓存，避免多本词表重复加载大词典。词典块生成器保留，以便按需读取记录；普通列表替代会增加内存和读取成本。

## 验证与清理

- 完整测试 61 项通过，包含新增的真实 UTF-16 MDX 和 GBK 文件名/单词/例句回归。
- 原有双格式、SID/EID 分流、首个发音及配对 IPA、MP3/WAV 跳过、首次 stem 资格、失败回滚与 CLI 状态测试通过。
- 本轮真实牛津词典重新验证 zoology：两种格式各提取 UK/US 首录音并更新 IPA；再次运行不提供词典时全部跳过，录音 SHA-256 未改变。
- 独立只读复核未发现新增的必须修复问题。
- 清理测试临时目录、pytest 缓存、源码/测试字节码缓存，以及旧 build 验证资源和本地 uv 临时缓存。保留运行环境、锁文件、源码、测试、示例和文档；不清理用户原始词库及音频。

没有承诺任意 MDX 的 HTML 兼容性。在线 TTS 成功合成本轮没有重新验证；合成边界、跳过、重试及失败清理由测试验证。项目根目录与 main.py 中用户选择的词库路径保持原状。

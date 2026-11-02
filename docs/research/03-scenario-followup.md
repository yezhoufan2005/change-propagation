# 场景跟进：修好一个对象后，找回没修的近似对象

日期 2026-10-30。读者是正在构建 change-propagation 的你。本文只依据四个调研方向的结论语料（variant analysis、上下文与预算、契约与 Vue/Go/Python、评测构建），数字已按核验更正改写。

标注约定：
- **本机实测**：调研 agent 在本机跑出的测量，来源文件列在文末。
- **（未核验）**：核验结论为 unchecked 或无法核验，或是调研补充、尚未核验的线索。
- **估算**：由实测值或定价推算，没有实际跑过。

数据局限：
- 本机实测用到的应用代码只有 ThingsPanel（Go 后端加一个 Vue 前端，共 2,522 个文件）、它的 43 份拷贝（99,330 个文件）和一个 10 文件的三栈 fixture。Python 和 JS 只在两棵系统库目录（2,634 个文件）上测过名字折叠，没有测过应用代码。
- Go 历史重放用的仓库是违反"不克隆"规则克隆到 `/tmp/va-repos` 的（约 788 MB），调研 agent 建议删除，删不删由你决定。
- 一个 pydantic 文档页面里嵌着"给链接加 goal/organization 参数"的指令，调研 agent 没有照做。

后续实测更正（本文写完后用户运行了补测，详见 [04-scale-measurements.md](04-scale-measurements.md) 的"补测"各节）：
- ast-grep 的 Go 模式 `$A.Subscribe($$$B)` 返回 0 是写法问题。写成 `func t() { $A.Subscribe($$$B) }` 并加 `--selector call_expression` 后，Subscribe 找到 20 处、Publish 找到 51 处，和 rg 逐行一致。"0 命中只能算未知"仍然成立（第 2.6、3 节）。
- ast-grep 能搜 `.vue` 里 `lang="ts"` 和 `lang="tsx"` 的 script 块：用 `languageGlobs` 把 `*.vue` 映射到 html，`--lang ts` 和 `--lang tsx` 各跑一次，找到全部 152 处 `watch(`。第 3 节表格、4.3 节和第 8 节第 5 问里 ast-grep 的那一半已经有答案。
- jscpd 5.4.2 的 `--similarity=0.8` 在 ThingsPanel 前端连上了 75 对 shingle raw 函数对中的 74 对，包括跨 ts/tsx 块的副本和已分叉的 `handleCopy`；`--ignore-identifiers` 只增加噪声。

## 1 场景定义：近似对象召回

**定义。** 输入是一次修复（已写好的 diff，或准备做的改动）。它修正对象 A 的一段逻辑，起因是起栈验收发现的细节问题或代码审查发现的 bug，验收说明只提到 A。任务是在修复合入前，列出仓库里仍带着同一缺陷、却不在这次修复里的位置 B1…Bn，并给每个位置一个范围标签：

| 标签 | 含义 | 例子 |
|---|---|---|
| required | 与 A 是同一缺陷，必须一起改 | 另一个前端里复制来的同一张状态颜色表 |
| ask | 与 A 共享一条耦合规则，改不改属于范围决策，要先问你 | 试点 T1 中被擅自改动的那条耦合规则 |
| forbidden | 名字或结构相似，但不该改 | 试点里的诱饵位置 |

"仍带着同一缺陷"可以机械检查：候选含有修复删掉的那类代码，不含修复加上的代码，文件历史里也没有同样的改动 [1][2]。

**近似对象与 A 的关系**，按靠什么才能找到来分：
1. 复制后分叉的代码，包括改过名的克隆和复制来的分支。签名匹配（抽象化的修复行、函数指纹）能找到其中一部分。
2. 同一契约的两端：同一个 JSON 字段、MQTT topic、WebSocket 事件、i18n key 或 store action 的生产者和消费者。它们分布在 Go/Python/Node/Vue 里，只共享字符串，没有符号引用。
3. 同一枚举的多份映射，例如 status 到颜色、status 到文案的表，散在后端、标签文件和多个 SFC 里。
4. 非代码位置：菜单 SQL seed、网关和代理路由、locale 文件、文档。
5. 重写过的同功能实现。它和 A 没有共同 token，也没有调用关系，词法和指纹都难以找到。

**约束（来自你的描述和回答）：**
- 约 10 万个文件，含生成代码和静态资源。后端是 Go、Python、Node，前端是多套 Vue，前后端经 WebSocket 实时推送和 MQTT/消息队列通信。
- 上下文几轮就满，要求通读一端也会漏；token 成本要控制。
- 默认只跑便宜的检查：脚本在 agent 上下文之外搜索，只返回紧凑的候选清单。只有你要求或改动高风险时，才用 subagent 验证。
- 首先支持和评测的栈是 Vue + Go/Python/Node，契约走 MQTT/WebSocket。

**与试点的关系。** 在 40 个文件的 fixture 上，Opus subagent 9/9 次找全了位置：它组合多种词法、结构和 API 特征，并读了大部分文件。能复现的失败是在耦合规则上擅自做范围决定。所以召回问题出现在仓库大、受上下文和成本限制、近似对象之间没有共同词汇的时候；范围决策问题在小仓库里就有。

## 2 为什么 grep 和通读都不够

试点的 40 个文件里，grep 加通读够用（9/9）。到 10 万个文件，下面这些机制让两种做法都失效。

### 2.1 结果进不了上下文

- 本机实测，ThingsPanel 2,522 个文件：rg 每次 31–97 ms；一个字段的变体正则 `-i device[-_]?config[-_]?id` 命中 930 行，约 34k token [3]。
- 本机实测，43 份拷贝共 99,330 个文件（724 MB，热缓存）：rg 每次 2.1–3.9 s；同一正则输出约 1.51M token，只列文件名（`-l`）也有 152k token [4]。拷贝之间高度重复，查询时间偏悲观。
- 本机实测，同一个 key 在契约图里的切片只有 30–280 token（2.5k 文件）[3]，在 99k 文件上是 1 行 [4]。

搜索本身几秒就完成，瓶颈是结果进入主上下文的 token 数。通读更不可行：99k 文件上，一个字段的命中文件名列表就有 152k token。

### 2.2 修复里的名字不是近似对象用的名字

- 本机实测，10 文件三栈 fixture（Go、pydantic、Node bridge、3 个 Vue app）标注了 13 个 battery_level 位置。精确 grep 找到 6/13；忽略大小写、`-` 和 `_` 后 10/13；跟一次改名（`battery: s.battery_level`）后 12/13；再跟一次 Vue filter 到 13/13，另有 1 个非目标命中（一个 CSS class）[5]。标注由写脚本的 agent 自己完成，可能偏向脚本。
- 本机实测，两棵系统库目录（2,634 个 Python/JS 文件，28.5 MB，不是 Vue 或 Go 应用代码）：作为完整标识符的 `status_code` 精确匹配 45 行，折叠后 196 行（149 行 `statusCode`、45 行 `status_code`、2 行 `Status-Code`），是 4.4 倍；`socket_path` 从 0 行变成 8 行 [6]。
- 本机实测，ThingsPanel 的 1,622 个 Go json tag 中，52.9% 在前端原样出现，3.5% 只以大小写变体出现。抽查 12 个只有变体的 tag：1 个是漂移 bug（`last_visit_time` 被读成 `lastVisitTime`），4 个是近似对象，7 个是误报 [3]。

名字的变化来自框架规则：Go tag、pydantic alias、Vue 的 kebab/Pascal 互换（见第 4 节）。只按修复里出现的名字搜，会系统性地漏掉契约的另一端。

### 2.3 近似对象大多不是克隆

- Park 等人（MSR 2012）统计 Eclipse JDT、SWT 和 Mozilla：22–33% 的 bug 需要不止一次修复。按 Figure 7，和第一次补丁相似的补充补丁只占 JDT 11.92%、SWT 25.35%、Mozilla 8.91%。JDT 15.08%、SWT 13.82% 的补充补丁文件与第一次补丁既不重叠，也没有直接的调用、访问或子类型关系（Mozilla 没做这项分析）[7]。
- 这几篇研究还给出：clone、依赖和 co-change 分析合起来只能预测 39–53% 的补充补丁文件；100 个不完整修复中，28 个漏了 porting updates，15 个漏了引用被改代码的位置；重复修复占 bug 的 15–20%，其中 73–92% 是克隆，70–94% 在同一个文件里 [7][8][9]。它们给出的总体相似比例是 7–17%，和 Figure 7 的分项目数字对不上，原因没有核对。
- 多补丁 CVE：20.6% 的已修 CVE 有多个补丁，其中一半（2,099/4,208）是跨分支或跨仓库的复制，同分支的不完整修复约占 24%（1,006 个 CVE，例如三个参数里只给两个加了 `escapeshellarg`）。在多位置修复上，ReDeBug 的 TPR 只有 16.75%，FIRE 是 52.46% [10][11]。

### 2.4 签名匹配的召回上限在一半左右

本机实测，ThingsPanel Go 历史重放 [12]：
- 种子是 94 处修复，它们抽象后的改动在 180 天内被后来的提交重复过。后来的 215 个位置中，177 个在种子提交时已经存在，其中 56 个就在种子文件里。
- 用修复删掉的行做查询（纯插入的修复用上下文行），召回为：精确匹配 36%；L1（标识符抽象化，保留 `.member` 名）50%；L2（全部抽象化）54%。
- 不设候选上限时，L1 找到 89 个，候选 3,175 个（精度 2.8%）；L2 找到 96 个，候选 7,544 个（1.3%）。
- L1 加回退、每个种子最多 20 个候选：召回 45%，平均每个种子 2.4 个候选，精度至少 35%。上限提到 50 只多找到 1 个位置，候选多 400 个。超过上限的种子有 23/94 个，应报"太泛"。
- 纯插入的修复召回 19%，有删改的 57%。加载 238 个文件 0.23 s，之后每个种子 5 ms。
- 局限：抽象器 abs2 用的是 v1，之后改过；精度是下限；只有一个项目。

本机实测，一个 Vue 前端仓库的历史（与 Go 重放同批克隆）[13]：740 个修复提交中，101 个的抽象改动在 180 天内又出现，共 182 组，其中 137 组起于 `.vue` 文件。109 组的后续 hunk 落在种子提交从没碰过的文件里，这是"修了一处，同样的问题在别的文件再修一次"。另有 52 组是同一位置的再次修复，例如 `device-analysis.vue` 里 `$t('common.action')` 改成 `'common.actions'`，156 天后又改了一次，那是种子提交已经修过的那一行回退了，不是漏掉的兄弟视图。Vue 上没有做检测重放。

### 2.5 Agent 自己检索，召回停在一半到三分之二

- Claude Code 在 50 个 ContextBench 任务上的文件召回是 49%（精度 65%）；限制读取量并加语义搜索后是 39%（精度 87%）[14]。
- 一项 LSP 研究中，各组的召回都在 0.66–0.67 [15][16]。
- SWE-QA 上，带索引的 agent 是 65.2%，把 grep 委托出去是 46.2%；Qwen3 分别用了 34k 和 761k token [15][16]。
- CodeGrep 上，BM25 取前 2 个结果（精度 0.375）会把 SWE-bench 解决率从 25.8% 拉低到 25.2%，精度提到 0.677 时是 27.0% [15][16]。上下文里的候选不够准，结果反而更差。

### 2.6 符号工具跨不过字符串契约，Vue 支持也薄

- topic、WebSocket 事件名、payload key 和枚举值把 Go、Python、Node、Vue 连在一起，没有哪个 LSP 能跨语言跟这些字符串。
- Claude Code 官方 LSP 插件有 gopls 和 pyright，没有 Vue。Vue 的需求 #232 从 2026 年 1 月开着；#38929（转发 Volar 的 tsserver 请求）以 not planned 关闭。gopls 的 references 只覆盖一种 build configuration [17][18][19]。
- Semgrep 已移除 Vue 支持（2024 年 10 月的提交）[20]。ast-grep 只能经 `languageGlobs` 把 `.vue` 当 HTML 解析，框架语法可能解析失败，属性里的表达式只是普通字符串 [21]。CodeQL 能抽取 `.vue`，但免费许可不允许用于非开源代码，你的私有仓库在免费许可下不能用；MRVA 只能跑在有 CodeQL 数据库的 GitHub 仓库上 [22]。scip-typescript 没有文档说明支持 `.vue`（推测它按 tsconfig 建索引）[24]。
- 本机实测：ast-grep 的 Go 模式 `$A.Subscribe($$$B)` 命中 0 处，rg 找到 14 个文件里的 20 处 Subscribe 调用（13 行不在测试里）[23]。所以 ast-grep 返回 0 只能当"未知"。

**小结。** grep 败在输出量和名字变体，通读败在上下文，克隆检测只能找回大约一半，agent 自己搜也停在一半到三分之二。剩下的近似对象要靠字符串契约、枚举共现和非代码文件这些与名字无关的线索。

## 3 技术手段

从 rg 到 ast-grep 这几行可以在 tier 0 用脚本跑；LSP 只用于验证档；repo map 和向量索引默认不建；最后两行要用 LLM。"本机实测"的数字来自 ThingsPanel（2.5k 文件）、它的 43 份拷贝（99k 文件）或 10 文件 fixture。

| 手段 | 怎样从修复构造查询 | Go / Python / Node / Vue | 成本 | 最适合 |
|---|---|---|---|---|
| rg 精确 + 名字折叠 | 取 diff 里的标识符和字符串，按大小写、缩写、数字边界拆词（`AGVTaskID`），忽略大小写、`-`、`_`；只列完整标识符命中，更长的名字标成近似，注释和文档只计数 [6] | 四种都可（纯文本）；Vue 扫整个 SFC | 本机实测 31–97 ms/次（2.5k 文件），2.1–3.9 s/次（99k）；输出 34k token 到 1.51M [3][4] | 精确 key 做种子；单词种子只在同一 topic 或 struct 内、外加一跳 import 的范围里用 |
| 抽象化修复行（ReDeBug/VUDDY 式，L0/L1/L2） | 修复删掉的行（纯插入用上下文行）归一化后匹配。ReDeBug 用去空白、小写的 4-token 窗口 [25]；VUDDY 按函数抽象参数、局部变量、类型和调用 [26] | 只在 Go 上重放过；Python、Node、Vue 未测 | 本机实测每个种子 5 ms [12]；约 1 ms/文件建索引，10 万文件冷启动约 100 s（估算），按 blob SHA 缓存，跳过生成代码和静态资源 | tier 0 默认 L1，回退 L2/L0，上限 20；保留 member 名和字面量 |
| 补丁存在性 + 历史过滤（MOVERY、FVF） | 候选必须含修复删掉的核心行，且不含任何新增行；文件历史里已有同样改动的剔除 | 与语言无关（文本 + git） | 每个候选一次有界 git log；FVF 最多查 50 次，用 BLEU-2 比对 [2] | tier 0 去误报 |
| 函数指纹（shingle Jaccard，raw/norm） | diff 里每个函数取前 10 个相似函数；加上 Vue/TS 中 norm J ≥ 0.8 的函数对；Go 不用 norm（gin 样板里 149 个函数聚成一团） | Go 和 Vue/TS 上测过 | 本机实测 15,476 个函数：建 2.8 s、212 MB，查询 0.1–19 ms；99k 文件：建 50–53 s（8 进程）、1.36 GB RSS、598 MB 索引，新进程单次查询约 2.5–3 s（含约 1 s 加载）[3][4][23] | 复制后分叉的代码；0 模型 token 的清单种子 |
| 契约图（json tag/alias、MQTT topic、WS 事件、i18n key、store action） | 从 diff 取 wire key、topic 模板、事件名，切出每个 key 的生产者和消费者 | Go tag、Python stdlib ast（pydantic alias）、MQTT.js、SFC 文本，正则即可 | 本机实测 2.5k 文件 1.2 s，一个 key 的切片 30–280 token；99k 文件 51–53 s、1.08 GB RSS，tag 切片 1 行 [3][4]；fixture 13/13，图约 625 token [5] | 没有共同符号的跨栈位置（第 4 节） |
| 枚举共现窗口 | 改动新增或改名一个状态值时，用它的兄弟值做种子，找 3 行内出现同一枚举 2 个以上值的窗口，标出缺新值的映射 | 与语言无关 | 本机实测：语料中 454 行含 `error`，同时含 debug/info/warn/error 中 2 个以上的窗口只有 22 个，在 14 个文件里，4.4 s；fixture 找到 Go、Python、Node、标签文件和 2 个 SFC 里共 6 张 idle/charging/error 映射 [5] | 状态到颜色、状态到文案的映射表，即场景里最主要的漏改 |
| ast-grep（可选） | 结构模式，例如 `$A.Subscribe($$$B)` | Go/Python/TS 有语法；`.vue` 只能按 HTML 解析，`<script lang=ts>` 能否解析未核验 [21] | 本机实测：Go 模式命中 0 处，rg 命中 20 处 [23] | 只做 `<script>` 内的结构确认；0 命中算"未知" |
| LSP（gopls、pyright） | 对 diff 里改到的符号查 references | Go、Python 有官方插件，Vue 没有 [17][18][19] | 未测 | 只放在 opt-in 的验证档，核对同一语言内的符号引用 |
| repo map / Zoekt / 向量索引 | Aider 按 diff 涉及的定义和引用排序，填进 `--map-tokens`（默认 1k）[29]，用 tree-sitter 提取（出自 Aider 2023 年的博客，语料未给链接） | scip-typescript 没有文档说明支持 `.vue` [24] | Zoekt 索引约占语料 3–3.5 倍的磁盘、1.2 倍的内存 [30]；向量化 3–5 万个文件 × 2k token，按 $0.02/MTok 约 $1–2，0.5–1.5 GB，要几个小时（估算） | 默认不建。按 Aider 的方式给契约图条目排序；语义检索作为 tier 0b，先在 40 文件 fixture 上试 |
| LLM 逐个判定候选（BugStone、SPectre、InfraScope） | 先从修复写一张不超过 10 行的规则卡，每次只给一个候选和它所在的函数，回答 YES/NO | 与语言无关 | BugStone 每次 0.87K 输入 + 0.65K 输出 token，精度 92.2%、召回 85.8%；直接喂原始 patch 时 88.0%/72.5%，输入 2.25K [27][10][28]。估算每个候选约 1.5K token，20 个约 30K | tier 1/2 的判定和排序；不让 LLM 合成查询 |
| 给 agent 修复提交，让它审 HEAD（Big Sleep）（未核验） | 把修复提交和 diff 交给 agent，让它在 HEAD 上找相关问题 | 与语言无关 | 语料未给成本 | 高风险档的参考做法；它在 SQLite 里找到过一个可利用的 bug [31] |

表格的补充说明：
- **签名类的精度。** MOVERY 只标记"含核心删除行、不含任何新增行"的代码：415 个克隆上精度 96%、召回 96%，其中 91% 在语法上和公开的漏洞函数不像 [1]。4 个克隆检测器的告警里 76.2% 是误报；FVF 在 git 历史里找到修复，判定其中 65.1% 已修过，没有错删 [2]。VUDDY 在 Apache 上报 9 个、9 个都对，耗时 22 s。DECKARD 和 CCFinderX 的精度在 0.009–0.147。SourcererCC 只报了 1 个，精度 1.000。CCFinderX 找到 11 个真阳性，比 VUDDY 多，但报了 74 个，耗时 1,201 s [26]。ReDeBug 以每分钟 700k LoC 的速度索引了 2.1B LoC，376 个 patch 的查询用了 8 分钟 [25]。
- **抽象层级要保留 member 名和字面量。** 本机实测的重放中，从 L1 换到 L2 后，不设上限的精度从 2.8% 降到 1.3%（89/3,175 降到 96/7,544）。这是重放的数字，不是论文给的 [12]。
- **指纹的命中和漏网（本机实测）。** 每个复制查询中，拷贝都排第 1（raw J 0.32–0.81）。WebSocket 连接代码的相似实现排在第 2–9 位，J 低到 0.07。指纹漏掉了一个重写过的 WS 连接（排第 155 位）和一个只有 31 个 token 的 `formatDateTime`。抽查 6 对只有 norm 相似的前端函数（norm J ≥ 0.8，raw J 0.06–0.79）：4 对是拷贝，其中 2 对已经分叉（一个 `actionValueChange` 只校验 4 种 JSON 类型中的 1 种）；1 对是样板代码；1 对是误报。短函数、重写过的实现、`<script setup>` 顶层代码要靠契约切片或 rg：`status/ws` 命中了全部 5 个前端文件 [3][23]。
- **LLM 阶段的规模。** BugStone 抽查 400 个 Linux 告警，246 个成立。SPectre 先用脚本过滤，LLM 调用次数是纯 LLM 方案的 1/67.5。InfraScope 按模块排序、跑 3 轮，召回相近时精度 0.774，Claude Code 是 0.391，输入 token 是 51M 对 381M。QLCoder 给每个 CVE 合成 CodeQL 查询，成功率 53.4%，每个耗时 3,712 s、花费 $2.90 [27][10][28]。LLM 过滤会丢真阳性，见第 5 节。
- **按多位置修复设计查询。** 默认第一次修复只修了一部分：先查它自己的文件和函数，再查全仓；不能把克隆搜索的结果说成已经完整 [10][11]。
- **抽象阶梯（未核验）。** Trail of Bits 每一步只泛化一个元素。匹配数大致是：精确约 1 个，泛化变量 3–5 个，泛化结构 10–30 个，taint 50–100 个以上。约一半是噪声时就停。误报预算是 CI 低于 5%，审计低于 50%。他们说范围太窄是"一次搜索什么都找不到最常见的原因"[32]。对 skill 的意义：输出里写明用了哪一级、命中几个；搜索覆盖所有前后端根目录，不只是改动所在的 app。
- **补充线索（未核验）。** VMud（CCS 2024）处理有多个修复函数的重复漏洞 [33]。FIRE（USENIX Security 2024）是 Bloom、token、AST、taint 四级过滤，各级召回 92.0–99.99%；它在自己的基准上精度 90.0%、召回 77.4%，这两个数经过了核验 [34]。

## 4 契约锚点：MQTT/WebSocket 与多前端

跨栈的近似对象之间往往只共享字符串：topic、WebSocket 事件名、payload key、枚举值。没有哪个 LSP 能跨语言跟踪这些字符串。只用标准库的脚本可以在 agent 上下文之外把它们整理成一张契约图，每次改动只把相关切片交给 agent。本机实测，在 fixture 上一个字段的召回从精确 grep 的 6/13 提到 13/13，整张图约 625 token [5]。AsyncAPI 3.0 适合当输出格式，不必要求项目先写好 spec。

### 4.1 契约图的做法

1. **收集 wire key。**
   - Go：json tag 第一个逗号前的文本就是 key；没有 tag 的导出字段沿用 Go 字段名，如 `Mode` [35]。
   - Go json v1 的 Unmarshal 也接受只差大小写的匹配；v2（Go 1.27）区分大小写，除非设了 `case:ignore` 或 `MatchCaseInsensitiveNames` [35][36]。没有 tag 的导出字段和从 v1 迁到 v2 的位置要标出来，在那里只差大小写的匹配会失效。
   - pydantic：`alias_generator`（如 `to_camel`）给每个字段都加上别名；`validate_by_name` 默认关闭；dump 时用字段名，除非设了 `by_alias` 或 `serialize_by_alias` [37]。脚本要解析 tag、套用 alias_generator、在 dump 处读出 by_alias，再用得到的 wire key 去搜前端。
2. **收集 topic 和事件。** publish 和 subscribe 调用里的 topic 模板中，`%s`、`{x}`、`${x}` 都算一个动态层级。Socket.IO 的 emit/on 按事件名配对，名字折叠后才对上的单独标出。
3. **按 MQTT 规则配对。**
   - MQTT 3.1.1 第 4.7 节规定：`+` 匹配恰好一整层；`#` 只能放在最后，也匹配父层级；以通配符开头的 filter 不匹配 `$` 开头的 topic；匹配区分大小写 [38]。
   - 本机实测，调研 agent 写的匹配器通过了 14/14 项规范和模板检查。朴素的 `[^/]+` 正则会误判 `agv//status` 不匹配 `agv/+/status` [38]。
   - publish 模板与 subscribe filter 配对；互相重叠的 filter 列为共同订阅者；去掉 `$share/<group>/` 前缀（这条语法来自搜索结果，MQTT 5.0 第 4.8.2 节没有读到，（未核验））；没有订阅者的 topic 列出来问你。
   - MQTT.js 把所有消息交给同一个 handler，应用自己按 topic 分发，例如 `topic.split` [39]。这些分发行也要放进切片。
   - WebSocket 消息如果按 JSON 的 `type` 字段分发，目前还没有配对方法（见第 8 节）。
   - 这一步不额外读文件。
4. **输出格式。** AsyncAPI 3.0 的 channel address 可以是 null，也可以带 `{param}`；operation 通过 channel 的 `$ref` 做 send 或 receive [40]。code-first 生成器只认用它们自己 API 注册的 handler，即 go-asyncapi 的调用和 FastStream 的装饰器；直接用 paho 或 MQTT.js 写的代码，生成结果为空 [41][42]。所以不要求项目先有 spec。脚本写一个仿 AsyncAPI 的 `contracts.json`，记录地址模板、send/receive 的 file:line 和字段变体，按文件 hash 缓存在 `${CLAUDE_PLUGIN_DATA}`。项目已有 spec 时，把它的 channels 和 properties 导入作种子。
5. **本机实测规模。**
   - fixture：1 个 publish 配上 3 个 subscriber，标出 1 个没有订阅者的 topic；图 27 行，约 625 token [5]。
   - ThingsPanel 2.5k 文件：1.2 s，得到 1,622 个 json tag、50 组 MQTT topic、4 个 WS endpoint [3]。
   - 99k 文件：51–53 s，1.08 GB RSS。全量汇总约 96k token，其中 MQTT 调用点占 63k，所以要按 topic 分组，只交切片 [4]。
6. **改名后复查。** 用旧名和新名各跑一次，旧名还有命中的地方就是漏改 [5]。图放进范围文件，上限约 2k token，超出部分只给计数。

### 4.2 名字变体扩展

- **拆词。** 种子按大小写、缩写和数字边界拆开，例如 `AGVTaskID` 拆成 AGV、Task、ID。再生成 snake、camel、Pascal、kebab 写法，匹配时忽略大小写、`-` 和 `_` [6]。
- **分级列出。** 完整标识符命中直接列出；包含种子的更长名字标为近似；注释和文档里的命中只给计数。把空格和 `.` 也当分隔符时，本机实测多出 75 行说明文字和 1 个误报（`_thread.TIMEOUT_MAX`），所以代码匹配不用这两种分隔符 [6]。
- **只有大小写变体的命中要单独标出。** 本机实测抽查 12 个只以变体出现的 tag：1 个漂移 bug，4 个近似对象，7 个误报 [3]。这类命中排在精确命中之后，交给 tier 1 判定或由你确认。
- **单词种子限范围。** 像 `status` 这样的单词种子，只在同一 topic 或 struct 内，外加一跳 import 的范围里搜。单词模式全仓 2,046 行、经 payload 访问过滤后 315 行，这组数字（未核验）[6]。
- **跟一跳。** 改名（`battery: s.battery_level`）和 Vue filter（`batteryText`）各跟一跳，fixture 的召回从 10/13 提到 13/13 [5]。
- **调用方式。** 在 Claude Code 的 Bash 里，rg 只是一个 shell function，Python 脚本没法直接调用它。所以先跑 `rg -l`，把文件列表经管道交给脚本 [6]。

### 4.3 Vue 的特殊之处

- **名字互换。** `<MyComponent>` 和 `<my-component>` 解析为同一个组件；camelCase 的 prop 在模板里写成 kebab-case（`:battery-level`）；camelCase 的 emit 用 `@some-event` 监听 [43][44][45]。脚本要给每个种子补上 kebab 和 Pascal 写法。
- **逻辑离开调用点。** Vue 2 filter、mixin、Vuex mutation 常量、Pinia store 和 composable 都会把逻辑移到别处。fixture 里只有 filter 这一跳到达了 `batteryText` [5]。从 filter、mixin、store 和 composable 的名字各跟一跳，找到定义。
- **按 SFC 块和类型打标签。** 命中分为 binding、filter、props/emits、style。改动不涉及外观时，跳过 style 命中。
- **索引整个 SFC。** template 属性和 `$t` key 都要索引，字符串字面量要保留。i18n key、topic 和 JSON 字段是不依赖名字的锚点 [13]。
- **解析器。** tier 0 用正则切分 SFC 就够了。需要 `.vue` 的 AST 位置时，可以对命中文件调用项目 `node_modules` 里的 `vue/compiler-sfc`，这是可选步骤 [17]。ast-grep 处理 `.vue` 要配 `languageGlobs`，0 命中只能算未知 [21][23]。popov-do/vue-lsp 能不能返回 template 里的 references，还没有核实。

### 4.4 多前端

- **搜所有根目录。** 每次都搜全部前端和后端根目录，不只搜改动所在的 app。tier 0 的前 30 个文件里，每个栈至少留 1 个 [3]。
- **前端之间的拷贝。** Vue/TS 中 norm J ≥ 0.8 的函数对，本机实测多数是拷贝或已分叉的拷贝（见第 3 节说明）[3]。按 diff 函数取的前 10 个相似函数和这些函数对一起写进清单，不花模型 token。
- **映射表。** 每个前端都可能有自己的一张状态映射表。枚举共现会把它们都列出来，并标出哪张缺新值 [5]。
- **历史证据。** 本机实测，Vue 历史中 109/182 组重复修复落在种子提交没碰过的文件里 [13]。这和"修了一个视图，兄弟视图还是坏的"的情况一致。
- **相近的已有研究（未核验）。** ROSDiscover（ICSA 2022）不运行系统，从 ROS 源码和 launch 文件静态恢复节点及其 topic/service 连接，再检查配置错误。它来自机器人领域，是离 publish/subscribe 配对最近的已有工作 [46]。Wittern 等人（ICSE 2017）用过程间字符串分析，从 JS 客户端代码里取出 URL、method 和 payload，再和 API spec 比对：6,575 个请求上 URL/method 的精度为 96.0%，payload 为 87.9% [47]。Mayer 等人（JSERD 2017）调查专业开发者：平均每个项目用 7 种语言、3 对互相链接的语言，超过 90% 的人遇到过跨语言链接的问题 [48]。

## 5 成本与分档

### 5.1 价格和固定开销

- 每 MTok 的输入 / cache 写 / cache 读 / 输出价格：Opus 5.5 是 $4 / $5 / $0.20 / $20；Sonnet 5.5 是 $2 / $2.50 / $0.10 / $10；Haiku 5.5 是 $0.10 / $0.125 / $0.01 / $0.50，prompt 超过 100k token 时按 5 倍计 [49]。
- Claude Code 每个开发者每个活跃日约花 $13 [50]。
- 启动一个空 subagent 要写入 54,154 个 cache token [51]。按 cache 写入价折算：Opus 约 $0.27，Sonnet 约 $0.14，Haiku 约 $0.007（估算）。
- `context: fork` 的 skill 看不到对话历史，一次 $0.115，同样内容 inline 是 $0.021 [50][51]。
- 内置的 Explore 用主模型，除非项目里有一个名为 Explore 的 agent 设了 `model: haiku`。skill 用 `model:` 覆盖模型会用不上 cache [50][51]。
- 内容在上下文里留得越久越贵：10k token 跨 40 次 Opus 5.5 请求约 $0.13（1 次 cache 写加 39 次 cache 读）[3]。读取量超过约 40k token 时，交给 subagent 才划算（估算）。

### 5.2 三档

| 档 | 何时运行 | 做什么 | 进入主上下文的内容 | 成本 |
|---|---|---|---|---|
| tier 0 | 默认，每次改动都跑 | 脚本在上下文外运行：名字折叠 rg、契约切片、抽象行匹配（L1，上限 20，超过报"太泛"）、按 diff 函数取前 10 个相似函数、枚举窗口、补丁存在性和历史过滤。完整清单写进磁盘上的 ledger | diff 涉及的 key 的切片加排名前 30 的文件，约 1k token，每个栈至少 1 个 [3]；或约 30 个位置（path:line 加理由），1–2k token | 0 模型 token。本机实测：2.5k 文件时 rg 31–97 ms、契约图 1.2 s [3]；99k 文件的索引交给异步 hook 建（契约图 51–53 s，指纹 50–53 s），查询时 norm 查找 0.23–1.46 s，raw 不超过 78 ms [4]。1–2k token 留 40 次请求约 $0.013–0.026（估算），语料汇总为每个会话约 $0.03 |
| tier 1 | 你要求，或改动高风险时的第一步 | `cp-triage`：fork 的 skill 加 Haiku agent，读取 `!scan.py --packet` 生成的候选包，给每个候选一行标签 needs-change / related-ok / unrelated / uncertain。只调整顺序，不删除候选；精确链接不经过 LLM | 每个候选一行判定 | 每次约 $0.02；30 个候选 × 400 token 加启动约 $0.01（Haiku 5.5）；候选包加读取的内容控制在约 45k 以内，不超过 100k，避免 5 倍价（估算）[49][50][51] |
| tier 2 | 高风险，或你明确要求；tier 1 留下 uncertain 项或耦合规则项时 | 验证 subagent 先写一张不超过 10 行的规则卡，每个候选只看它所在的函数。高风险时最多跑 3 轮，按排序推进，记录被否掉的假设。可以用 gopls 和 pyright | 每个 subagent 返回 1–2k token [52] | 每个候选约 1.5K token，20 个约 30K [27][10][28]。每个 Opus verifier 约 $0.8，Sonnet 约 $0.4。按 Go、Py+Node、Vue 开 1–3 个，约占一天 $13 的 6–18%（估算）[49][50][51] |

两个调研方向对 tier 1 和 tier 2 的切分不同。variant-analysis 方向把"规则卡加逐个判定"放在 tier 1，高风险时再跑多轮；上下文预算方向把 Haiku 分诊放在 tier 1，把 Opus/Sonnet 验证放在 tier 2。上表合并了两者，是供讨论的方案。按你的成本策略，两档都用到 subagent，所以都只在你要求或改动高风险时运行。"高风险"怎样判定，tier 0 报"太泛"时要不要自动提议升档，都还没定（第 8 节）。

### 5.3 什么进入主上下文

- **默认只进切片和短清单。** skill 里用 !`scan.py --from-diff || true` 注入 diff 涉及的 key 的切片和前 30 个文件，约 1k token，完整清单只写进 ledger [3]。99k 文件的索引在异步 SessionStart hook 里建，按 mtime 刷新；限时约 2 分钟的 !`scan.py` 只做切片和查询 [4]。
- **候选要准。** LSP/SCIP 跟不了 tag、topic、WS 事件这类字符串链接，所以由脚本列进 ledger。上下文里只放精确 key 命中和高相似度的条目，约前 30–40 个 [14][15][16]。CodeGrep 的结果说明，低精度的候选会让解决率下降（第 2.5 节）。
- **LLM 过滤会丢真阳性，所以 tier 1 只排序、不删除。** 腾讯的研究用 433 条告警测了 24 种配置，真阳性丢失 6–46%；其中有成本数据的 16 种丢失 12–41%，每条告警花 $0.0011–0.12，最好的配置去掉了 94–98% 的误报 [56][57]。OWASP 基准上，Sonnet 4 加 SWE-agent 把误报降到 6.3%，保留了 77.7% 的真实漏洞 [56][57]。FrugalGPT 的"成本最多降 98%"是 headline 分类任务上的数字，CoQA 上是 59.2% [55]。精确链接不经过 LLM；uncertain 和耦合规则项交给你或 tier 2。
- **补充线索（未核验）。** Chroma 的 Context Rot 研究发现，18 个 LLM 的表现都随输入变长而下降，这支持只给小的上下文包 [58]。Anthropic 的多 agent 研究系统中，单 agent 约用聊天的 4 倍 token，多 agent 约 15 倍，token 用量解释了 80% 的表现差异，可以用来定 tier 2 的预算 [59]。LocAgent 用代码图索引，文件级定位达到 92.7%，成本约低 86% [60]。

### 5.4 范围清单怎样撑过上下文压缩

压缩后会发生的事 [53][54]：
- CLAUDE.md 和 plan 会重新加载，最近的文件最多重读 5 个。
- 每个 skill 保留 5k token，总计 25k。
- hook 和工具的输出只能通过摘要保留。
- SessionStart（matcher 为 `compact`）会重新运行。hook 输出的文本上限是 10,000 字符。
- Stop/SubagentStop hook 可以带理由阻止结束，最多连续 8 次。command hook 超时是 600 s，也可以异步运行。

Anthropic 的建议是把笔记写在上下文窗口之外，subagent 只返回 1–2k token [52]。

据此的设计：
- 范围清单写成磁盘上的 ledger 文件，每个位置有 ID、标签、状态和判定。
- SessionStart(compact) 把还没关闭的条目打印出来，控制在 8,000 字符以内。
- Stop hook 在还有条目没有判定，或者耦合规则还没得到你签字时阻止结束。这正对应试点里擅自做范围决定的失败。SubagentStop 要等分给它的每个 ID 都有判定。
- 每次阻止约花 100–300 token。
- skill 里用 `!` 注入的输出能不能撑过压缩，还没测（第 8 节）。

## 6 评测构建

### 6.1 候选仓库

已找到的栈匹配候选都不到 10 万个文件，评测用的规模要拼接出来。下表的文件数和许可来自调研时的统计；标"核验补充"的行是核验阶段加进来的，语料没有附链接。原列表中的仓库在调研时 7 天内都有更新。

| 仓库 | 栈 | 文件数 | 许可 | 用途 |
|---|---|---|---|---|
| n8n（核验补充） | Node + Vue | 32,877 | Sustainable Use License，`.ee.` 文件另有企业许可 | 已找到的最大栈匹配候选，偏 Node |
| baserow（核验补充） | Python + Vue | 11,215 | 核心 MIT，premium/enterprise 另有许可 | Python 后端 |
| rotki（核验补充） | Python + Vue | 7,459 | AGPL-3.0 | Python 后端 |
| rancher + dashboard（核验补充） | Go + Vue，两个仓库 | 3,349 + 4,471 | Apache-2.0 | Go+Vue 跨仓库场景 |
| ThingsPanel [61] | Go 后端 + Vue 前端 + uniapp | 1,599 + 923 + 444 | Apache-2.0 | 主选：Go + Vue + MQTT；本机实测都在它上面 |
| JumpServer [62] | Django + lina（Vue）+ luna（TS/Vue）+ koko（Go） | 2,173 + 1,452 + 1,464 + 307 | GPL-3.0 | 主选：两个 Vue 前端、一个 API、一个 Go WebSocket connector，天然跨仓库 |
| 1Panel | Go + Vue | 1,969 | GPL-3.0 | 提交对来源 |
| Gitea | Go + Vue | 6,398 | MIT | 提交对来源 |
| EMQX + dashboard | MQTT broker + dashboard（语料未注明语言） | 5,298 + 920 | NOASSERTION | MQTT 一侧的参照 |
| rmf-web | 语料未注明 | 880 | Apache-2.0 | 备选 |
| ThingsBoard | Java + Angular | 13,921 | NOASSERTION | 栈不匹配 |
| GitLab | Ruby + Vue | 54,391+ | NOASSERTION | 规模大，栈只部分匹配 |

拼接的做法是在本地镜像里放约 10 万个文件，把生成代码和 `node_modules` 当干扰项。GPL 代码不要进插件仓库。

### 6.2 提交对样例与挖掘规则

已核实的开源案例。重建方法：回到第一次修复的父提交，prompt 只给第一个症状，后续修复的 hunk 当 gold。

| 案例 | 漏掉的近似对象 | 陷阱类型 |
|---|---|---|
| Gitea #13025 → #13069（隔 3 天）[63][64] | CONN_STR 的修复要在 `indexer.go` 里再做一次 | 词法相同 |
| Gitea #26469 → #26581 [63][64] | #26469 修了 box-shadow，漏了浮动 dropdown | CSS 变体 |
| 1Panel cecfecf → c556aff（约 3 个月）[65] | 用户密码那个分支仍在读 `Password` | 复制来的分支 |
| ThingsPanel f7f3914 | 这是一份交接文档。文档里写：alarm 改成 alarm-native 后返回 `{data,error}`，`if (res)` 要改判 `res.data`；还要加一行规则编辑菜单和 `/automation-core` 代理。gold hunk 要从前端 `alarm-api.ts` 调用处、菜单 SQL 和网关配置的实际提交里重建 | 契约加非代码 |

另加 2 个没有兄弟位置的对照用例。每个用例约需 1 小时人工。

挖掘规则：
- **Quick remedy commits。** Wen 等人的规则是同一作者、间隔不超过 5 分钟、提交信息匹配 (former|last|prev|previous) commit。在 1,497 个 Java 仓库的 1,041,397 对提交中匹配到 1,577 对，人工标注 500 对，其中 42 对是误报。69 类 remedy 中只有 20 类是补上一次提交漏掉的改动。这个规则刻意"maximize precision at the expense of recall" [66]。
- **你的 AGV 仓库。** 你是唯一作者，可以用脚本扫 git log：找 24 小时内、提交信息匹配 `漏改|遗漏|也要|forgot|missed|previous commit`、且排除 `漏洞` 的提交对，人工标 20–30 对作为私有评测集。只花几秒 CPU，不花 token。放宽到 24 小时并加中文关键词后，精度未知，需要人工复核 [66]。
- **显式线索优先（未核验）。** 优先找"missed in #N""introduced by <sha>"这类显式线索。blame 只用来分类：改的是第一次修复加上的行，算修复的修复；改的是另一个没动过的相似位置，算近似对象。预计约一半要丢掉。Rosa 等人人工复核引用了引入提交 hash 的 3,585 个提交，保留了 1,930 个；最好的 SZZ（R-SZZ）精度 0.66、召回 0.57 [67]。Barbour 等人发现，late propagation 占有变化的克隆谱系的 8–21%，但 Ant 上的数量从 CCFinder 的 6,455 到 Simian 的 103 不等 [68]。
- **本机历史数据（推断）。** Go 重放的 94 个种子和 Vue 历史里 109 组跨文件重复修复也是现成的候选对，要人工复核后才能用 [12][13]。
- **防记忆污染（未核验）。** 只给 issue 文本，模型在 SWE-Bench Verified 上定位出错文件最高 76%，在库外仓库上是 53%。2020 年、2023 年的公开修复对可能因为模型记得答案而抬高 site recall [69]。SWE-rebench 持续抓取新任务做去污染评测，可以借鉴它挑模型训练截止日期之后的修复对 [70]。

### 6.3 指标

- **按位置算召回和精度。** 每个 gold 位置配一个 regex grader，用 `{source: file}` 检查旧片段已经消失（`not_contains`）；每个诱饵也配一个，检查原样保留 [71]。按陷阱类型和分散程度分别报告 site recall、site precision、file recall，以及每找到一个位置花的 token 和美元 [72][73][74]。
- **评范围决策，不只评找没找到。** 每个位置标 required、ask 或 forbidden。通过条件：
  - required 位置已经改了；
  - ask 位置必须在 last_message 里提出，而且文件没改（用 regex 检查原值还在），没经确认就改了算失败；
  - forbidden 位置没动。
  用 regex 加一条简短的 llm rubric 判定。grader 不能要求 skill 的报告格式，否则 without 组注定失败 [71][73]。
- **Drop 指标。** ContextBench 的 Drop 指运行中看到过 gold 证据、它却没出现在最终上下文里的情况。它衡量"看过但没留下"，适合大仓库里打开过近似文件却没改的情况，不衡量擅自扩大范围 [73]。
- **不要只看 file recall。** Recall Trap 的结果：gold 文件召回更高（0.878 对 0.806）的 12-chunk 上下文包，解决率反而更低（39.2% 对 46.8%）；允许自由读文件时没有这个效应。但这个效应在 BM25 上反过来（−3.2pp），集中在单文件修复，跨语言不显著（p=0.056），数字来自 qwen3.6-flash 和 gpt-5.6-sol，不是 Claude [75]。tier 0 是词法脚本，任务多为多文件，所以这条只能用来支持"别只看 file recall"。
- **现有基准只能借用指标定义。** 它们标注的是已解决的 issue，不是漏掉的近似对象 [72][73][74]。
  - SWE-PolyBench 报告文件级和 CST 节点级的召回与精度。Aider-PB 通过 17.7% 的单文件任务，4–5 个及以上文件的任务只通过 6.9–7.9%。TS 节点级上，Aider-PB + Sonnet 3.5 是 20.2/26.7，表中最好的是 Aider-PB + DeepSeek R1 的 23.6/29.4 [72]。
  - ContextBench 上，Sonnet 4.5 的 block 召回 0.631，精度 0.449，每个任务 $0.76 [73]。
  - SiblingRepair 发现，在 Defects4J 的 sibling bug 里，失败测试最多会漏掉 61% 的兄弟位置。Hunk4J 上，o4-mini 单独修复时，同一方法内的多 hunk bug 修好 49%，跨 package 的修好 0%；加上反馈循环后，o4-mini 修好 27.27% 的 Fragment bug [74]。
  所以要按位置用 regex 打分，不能靠测试。

### 6.4 协议

- **工具。** 用 `claude plugin eval`。每组默认跑 3 次，delta 是 with 组减 without 组；一次运行的分数是通过的 grader 所占比例。grader 有 regex、tool_used、tool_order、file_exists、llm、baseline 几种，不能写自定义代码；两组对比时 `tool_used:Skill` 不计分。默认 max_turns 10、timeout 300 s，scaffold 上限 120 s。JSON 结果里有 costUsd 和 durationSeconds [71]。
- **site recall 用 run score。** case 默认 `--threshold 1.0`，全部 grader 通过才算 pass，所以 site recall 要取 run score [71]。
- **运行设置。** scaffold（`--scaffold`）用 git worktree 准备仓库；max_turns 设 40，timeout 设 900 s；长会话档用 `history_file` 加 `--ablation with-without`。14 个用例 × 3 次 × 2 组 = 84 次运行，估计 $35–100 [71]。
- **沙箱约束。** scaffold "runs as you, outside the agent's sandbox"，HOME 是临时目录，可以按绝对路径读工作区外的镜像。agent 的 Bash 在沙箱里，只能写工作区，读不到真实的 home；`add_dirs` 只能是 case 目录里的只读目录 [71]。以下是推断（未实测）：镜像放在 home 下时，git worktree 的 `.git` 会指回镜像，agent 里的 `git log` 会失败。应该由 scaffold 用 `git clone --local` 把仓库放进工作区，或者把镜像放到 home 之外。10 万个文件能否在 120 s 内准备好，还要实测。
- **用例组合。** 陷阱类型：词法相同、CSS 变体、复制来的分支、契约加非代码，再加长会话档和 2 个没有兄弟位置的对照。JDT 和 SWT 有 14–15% 的补充补丁文件与第一次补丁没有重叠，也没有直接的结构关系 [7]，光靠邻近搜索会漏掉这些。所以有些档的漏改位置要和修复既不共享 token、也没有依赖边，例如菜单 seed、网关路由、i18n key、MQTT topic；tier 0 也要扫 SQL seed、proxy、locale 和 route 文件。另加一个跨仓库场景（JumpServer，或 rancher 加 dashboard）。
- **和 subagent 版本对比。** RefactorPlatform 的设置是 100 个任务、一个模型、每个任务跑一次。结果是检索式单 agent 86%，委托给 subagent 66%，基线 73%；检索让每个任务的成本增加 18% [76]。所以默认版本由脚本交给主 agent 一份有上限的清单（约 30 个位置，path:line 加理由，1–2k token）。subagent 版本作为第二套评测，比较两者每花一美元带来的 delta。
- **审查 grader（未核验）。** 任务设置或打分上的缺陷，最多可让结果被高估或低估 100%（相对值）。可以用该文的 Agentic Benchmark Checklist 审查逐个位置的 regex grader [77]。

## 7 对 skill 架构的启示（供讨论，不是定稿）

**组件草图。**

| 组件 | 职责 | 依据 |
|---|---|---|
| `bin/scan.py`（只用标准库） | 建索引（抽象行、函数指纹、契约图、枚举窗口），`--from-diff` 输出切片和前 30 个文件，`--packet` 生成 tier 1 的候选包；不依赖 ast-grep、CodeQL、Semgrep | 第 2.6、3、4 节 |
| ledger 文件 | 范围清单：位置 ID、required/ask/forbidden、状态、判定、证据；完整候选只放这里 | 第 5.4 节 |
| SessionStart hook | 异步建索引、按 mtime 刷新；`compact` 时重新打印未关闭的条目 | [4][53][54] |
| Stop / SubagentStop hook | 有条目没有判定，或耦合规则没得到你签字时，阻止结束 | 试点失败模式，[54] |
| skill 正文 | 在三种工作方式里都走"列范围 → 写进 ledger → 改完复查"：直接下指令、先出 plan、长会话后期 | 试点结论 |
| `cp-triage`（Haiku，可选） | tier 1：给候选打标签、调整顺序，不删除 | 第 5.2 节 |
| verifier（Opus/Sonnet，可选） | tier 2：按 Go、Py+Node、Vue 分开，规则卡加逐个判定，最多 3 轮；可以用 gopls、pyright | 第 3、5.2 节 |

**tier 0 的查询通道。** 所有通道都先套用名字变体扩展（第 4.2 节）。
1. 签名通道：用修复删掉的行做 L1 匹配，回退到 L2/L0，每个种子最多 20 个候选，超过就报"太泛"；再按"已有新增行"和"历史里已有同样改动"过滤。
2. 引用通道：取修复碰到的 JSON 字段、MQTT topic、WS 事件、i18n key、store action，在契约图里列出 Go/Python/Node/Vue 中的生产者和消费者 [7][8][9]。
3. 枚举通道：状态值有改动时，列出所有映射表。
4. 指纹通道：每个 diff 函数取前 10 个相似函数，外加 Vue/TS 中 norm J ≥ 0.8 的函数对。
5. 非代码通道：SQL seed、proxy、locale、route 文件。

搜索顺序是先查修复自己的文件和函数，再查所有前后端根目录。输出写明用了哪一级抽象、命中多少，不把结果说成已经完整。

**主上下文的纪律。** 默认只放约 1–2k token：key 切片加约 30 个位置。其余都在 ledger 里，主 agent 需要时按 ID 去读。

**范围决策。** ask 项和耦合规则项要在改动前列出来问你，Stop hook 负责兜底。这对应试点里唯一能复现的失败：T1 有 2 次运行（T1-c2、T1-c3）没问你，就在耦合规则上做了范围决定。

**改完复查。** 用旧名和新名各跑一次 scan，旧名还有命中的地方就是漏改；再拿 diff 和 ledger 对账，没有判定的条目不能关。

**暂不做的事：**
- 默认的向量索引；
- CodeQL 和 Semgrep 依赖（许可和 Vue 支持都有问题）；
- 让 LLM 合成查询（QLCoder 每个 $2.90，成功率 53.4%）[27][10][28]；
- 默认把检索交给 subagent。RefactorPlatform 上，委托给 subagent 是 66%，检索式单 agent 是 86% [76]。

**要讨论的取舍：**
- tier 1 和 tier 2 怎么切分（第 5.2 节列了两种方案）。
- 99k 文件时，建索引要 1.08–1.36 GB RSS、约 50 s。异步建可以接受，但这组数字来自 43 份重复拷贝，真实仓库里源码的比例和重复程度都还不知道。
- ledger 放在仓库里，还是放在 `${CLAUDE_PLUGIN_DATA}`：放仓库里你能直接看、能纳入版本管理，放插件数据目录不会弄脏工作区。语料没有给出结论。
- 纯插入的修复召回只有 19%：要不要让 LLM 写一条 guard 查询来补。

## 8 未决问题

召回与方法：
1. 引用通道（MQTT topic、JSON 字段、i18n key）对 AGV 仓库里真实漏改的召回是多少？要用你仓库里挖出的提交对来量。
2. L1 抽象在 Python、Node 和 Vue template 上是否同样有效？目前只在 Go 上重放过。
3. 纯插入的修复召回只有 19%，值不值得花 token 让 LLM 写一条 guard 查询？
4. 按 JSON `type` 字段分发的 WebSocket 消息，怎样配对？
5. popov-do/vue-lsp 能否返回 template 里的引用？ast-grep 能否解析 `<script lang=ts>`？
6. `$share` 语法要对照 MQTT 5.0 第 4.8.2 节核实。
7. fixture 的标注是调研 agent 自己做的，要和后台 agent ab7530fab6901c680 的结果对齐。那个 agent 在克隆仓库上跑了 contract_map.py。

成本与运行：
8. 在这台机器上，用 fork skill 加 Haiku 跑 cp-triage 实际要多少开销？在 40 文件 fixture 上，Haiku 分诊和 Opus 分诊的召回差多少？
9. 真实仓库里源码占多大比例、重复多少？Python 和 Node 的应用代码还没测过。
10. skill 里用 `!` 注入的输出，压缩后还在不在？
11. 你用订阅还是 API 计费？这决定第 5 节的美元数怎么换算。
12. "高风险"怎样判定？tier 0 报"太泛"时（Go 重放中 94 个种子有 23 个），要不要自动提议 tier 1？

评测：
13. 10 万个文件的 git worktree 能否在 scaffold 的 120 s 上限内建好？scaffold 读工作区外的镜像后，agent 里的 `git log` 能否正常用？
14. 从你的 AGV 仓库挖出的提交对和你描述的真实案例里，有多少属于没有共同 token 的档（契约、非代码）？这决定用例怎么配比。

待你决定：`/tmp/va-repos`（约 788 MB）是违反"不克隆"规则留下的克隆，删不删由你决定。

## 参考来源

本机文件（本机实测的来源）：
- [3] /Users/yezhoufan/VScodeProjects/change-propagation/docs/research/04-scale-measurements.md
- [4] /tmp/cpf-measure/out/
- [5] /tmp/cp-contracts/cmap.py
- [6] /tmp/cp-contracts/tier.py
- [12] /tmp/va-scripts/detect.py，/tmp/va-out/backend_detect.json
- [13] /tmp/va-out/frontend_hunks_multi.json
- [23] /tmp/cpf-measure/external/results.jsonl

网络来源：
- [1] MOVERY（USENIX Security 2022）https://www.usenix.org/conference/usenixsecurity22/presentation/woo
- [2] FVF https://arxiv.org/html/2412.20740v1
- [7] Park 等，补充补丁（MSR 2012）https://web.cs.ucla.edu/~miryung/Publications/msr2012-supplementarypatch.pdf
- [8] 补充补丁扩展研究（EMSE 2016）http://web.cs.ucla.edu/~miryung/Publications/emse2016-supplementary.pdf
- [9] 重复修复研究（ICSME 2017）https://people.cs.vt.edu/nm8247/publications/ruru-icsme-2017-camera-ready.pdf
- [10] 多补丁 CVE 研究，也列在 LLM 判定阶段的来源里 https://arxiv.org/pdf/2609.07224.pdf
- [11] 多补丁 CVE 研究 https://arxiv.org/pdf/2607.13206
- [14] Benchmarking semantic code retrieval on Claude（演讲）https://ai.engineer/talks/zKk7sDMGDEQ-benchmarking-semantic-code-retrieval-on-claude
- [15] agent 检索召回研究 https://arxiv.org/html/2608.13568v1
- [16] agent 检索召回研究 https://arxiv.org/html/2608.01507
- [17] Claude Code code intelligence 插件文档 https://code.claude.com/docs/en/plugins/code-intelligence.md
- [18] Vue LSP 插件需求 #232 https://github.com/anthropics/claude-plugins-official/issues/232
- [19] Volar tsserver 转发 #38929 https://github.com/anthropics/claude-code/issues/38929
- [20] Semgrep Vue 支持 https://github.com/semgrep/semgrep/issues/1751
- [21] ast-grep HTML catalog https://ast-grep.github.io/catalog/html/
- [22] CodeQL CLI 许可 https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md
- [24] scip-typescript 发布文 https://sourcegraph.com/blog/announcing-scip-typescript
- [25] ReDeBug（Oakland 2012）http://users.ece.cmu.edu/~jiyongj/papers/oakland12.pdf
- [26] VUDDY（S&P 2017）http://www.ieee-security.org/TC/SP2017/papers/71.pdf
- [27] LLM 判定阶段（BugStone 等）https://arxiv.org/html/2510.14036v1
- [28] LLM 判定阶段（InfraScope 等）https://arxiv.org/html/2605.20051
- [29] Aider repo map 文档 https://aider.chat/docs/repomap.html
- [30] Zoekt 设计文档 https://github.com/sourcegraph/zoekt/blob/main/doc/design.md
- [31] From Naptime to Big Sleep（Project Zero，2024）https://projectzero.google/2024/10/from-naptime-to-big-sleep.html
- [32] Trail of Bits variant-analysis skill，searching.md https://raw.githubusercontent.com/trailofbits/skills/main/plugins/variant-analysis/skills/variant-analysis/references/searching.md
- [33] VMud（CCS 2024）https://dl.acm.org/doi/10.1145/3658644.3690372
- [34] FIRE（USENIX Security 2024）https://www.usenix.org/conference/usenixsecurity24/presentation/feng-siyue
- [35] Go encoding/json https://pkg.go.dev/encoding/json
- [36] Go json v2 迁移说明 https://tip.golang.org/doc/jsonv2-migration
- [37] pydantic alias https://pydantic.dev/docs/validation/latest/concepts/alias/
- [38] MQTT 3.1.1 规范 https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
- [39] MQTT.js https://github.com/mqttjs/MQTT.js
- [40] AsyncAPI 3.0.0 规范 https://www.asyncapi.com/docs/reference/specification/v3.0.0
- [41] go-asyncapi https://github.com/swaggest/go-asyncapi
- [42] FastStream https://github.com/ag2ai/faststream
- [43] Vue 组件注册 https://vuejs.org/guide/components/registration.html
- [44] Vue props https://vuejs.org/guide/components/props.html
- [45] Vue 组件事件 https://vuejs.org/guide/components/events.html
- [46] ROSDiscover（ICSA 2022）https://github.com/cmu-rss-lab/rosdiscover ；论文 https://par.nsf.gov/servlets/purl/10398745
- [47] Wittern 等，Statically Checking Web API Requests in JavaScript（ICSE 2017）https://arxiv.org/abs/1702.03906
- [48] Mayer、Kirsch、Le，多语言开发调查（JSERD 2017）https://link.springer.com/article/10.1186/s40411-017-0035-z
- [49] Claude 定价 https://platform.claude.com/docs/en/about-claude/pricing
- [50] Claude Code 成本文档 https://code.claude.com/docs/en/costs
- [51] subagent 启动开销测量 https://rulestack.hashnode.dev/we-said-a-claude-code-subagent-costs-436k-tokens-a-cleaner-measurement-says-54k-here-is-what-fooled-us
- [52] Anthropic，Effective context engineering for AI agents https://www.anthropic.com/research/effective-context-engineering-for-ai-agents
- [53] Claude Code context window 文档 https://code.claude.com/docs/en/context-window.md
- [54] Claude Code hooks 文档 https://code.claude.com/docs/en/hooks
- [55] FrugalGPT https://arxiv.org/html/2305.05176
- [56] LLM 告警过滤研究（腾讯、OWASP 两项之一）https://arxiv.org/html/2601.18844
- [57] LLM 告警过滤研究（腾讯、OWASP 两项之一）https://arxiv.org/html/2601.22952v2
- [58] Chroma，Context Rot（2025）https://www.trychroma.com/research/context-rot
- [59] Anthropic，How we built our multi-agent research system（2025）https://www.anthropic.com/engineering/multi-agent-research-system
- [60] LocAgent（2025）https://arxiv.org/abs/2503.09089
- [61] ThingsPanel 后端 https://github.com/ThingsPanel/thingspanel-backend-community
- [62] JumpServer lina https://github.com/jumpserver/lina
- [63] Gitea 提交 144fa5a https://github.com/go-gitea/gitea/commit/144fa5a53746387b1c124c10cd7d70cb5cebc26f
- [64] Gitea 提交 facdaee https://github.com/go-gitea/gitea/commit/facdaee47b49f163e6927cc021eace18940ad441
- [65] 1Panel 提交 c556aff https://github.com/1Panel-dev/1Panel/commit/c556affc919b24aca1a6d387f62c1a99df519930
- [66] Wen 等，quick remedy commits https://susi.usi.ch/documents/321185/files/Bavota_2021_Spri_ese.pdf?download
- [67] Rosa 等，SZZ 评估 https://arxiv.org/html/2102.03300v1
- [68] Barbour 等，克隆谱系中的 late propagation http://swat.polymtl.ca/~foutsekh/docs/Barbour-JSME.pdf
- [69] The SWE-Bench Illusion https://arxiv.org/abs/2506.12286
- [70] SWE-rebench https://arxiv.org/abs/2505.20411
- [71] Claude Code plugin evals 文档 https://code.claude.com/docs/en/plugin-evals.md
- [72] SWE-PolyBench https://arxiv.org/html/2504.08703v3
- [73] ContextBench https://arxiv.org/html/2602.05892v1
- [74] SiblingRepair、Hunk4J 相关基准 https://arxiv.org/html/2605.06209v1
- [75] Recall Trap https://arxiv.org/abs/2608.14838v1
- [76] RefactorPlatform https://arxiv.org/html/2609.04898v1
- [77] Establishing Best Practices for Building Rigorous Agentic Benchmarks https://arxiv.org/abs/2507.02825

Aider 用 tree-sitter 的说明出自 Aider 2023 年的博客，语料没有给链接。

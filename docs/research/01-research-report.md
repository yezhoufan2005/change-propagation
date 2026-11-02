# change-propagation 调研报告

- 日期：2026-10-30
- 读者：正在开发 change-propagation skill 的你
- 依据：本轮调研的 10 个维度（经典 systematic edits、LLM 时代的 edit propagation、impact analysis 与 co-change、克隆与重复合并、Agent 失败原因、工业工具、Claude Code 生态、skill 规范，以及补充调研 gap-1/2/3）和评审意见。正文只使用这些材料；核查阶段的更正已经替换进正文，被更正的原说法不再保留。
- 标注：
  - `[n]` 对应文末参考文献，`[Ln]` 是本地证据（本仓库文件、本机测试、临时脚本）。
  - （未核验）：核查阶段没有核对或无法核对的说法，主要来自核查员补充的"遗漏文献"和评审意见。
  - （自核）：来自补充调研 gap-1（触发方式）、gap-2（声明式耦合）、gap-3（权限模式），由调研 agent 自己对照一手页面或本地复现核对，没有经过独立核查。这几项调研时 WebSearch 额度已用完，证据以直接抓取的页面和本地测试为主。
- 代号：S1 需求耦合，S2 同类对象散落，S3 重复实现合并。T1/T2/T3 是基线试验 [L1] 的三个任务，依次对应 S1/S2/S3：注册密码最小长度 8→12；给所有弹窗类组件加淡入动画；抽取重复的日期格式化逻辑。

后续更正（2026-10-30，本报告写完之后）：
- 首个技术栈你已经确认：Vue 前端，Go、Python、Node 后端，契约走 MQTT 和 WebSocket。第 9.1 节第 2 问和第 8 问的前半已有答案。
- 运行时下载：默认档不下载任何工具，ast-grep、jscpd 只在本机已经安装时使用（第 9.1 节第 3 问）。
- ast-grep 可以搜 `.vue` 的 script 块：用 `languageGlobs` 把 `*.vue` 映射到 html，`--lang ts` 和 `--lang tsx` 各跑一次，在 ThingsPanel 前端找到了全部 152 处 `watch(`。Go 的方法调用要写成"上下文 + `--selector call_expression`"。详见 [04-scale-measurements.md](04-scale-measurements.md)。
- 开发计划见 [../plan.md](../plan.md)。

## 要点

1. **漏改的主要形式是遗漏，不是改错。** 人类开发者 23-34% 的已修 bug 需要补充补丁，只有 7-17% 的补充补丁与首个补丁相似，只有 10-20% 的补充位置离首个补丁一跳 [13][15]。Agent 也一样：SWE-Bench ProMax 上失败的运行改的文件比 gold 少，漏掉的是外围调用点、文档、配置和 fixture [51]。
2. **三个场景要用不同的召回信号，单一信号不够。** 单一信号的 precision 不超过 9% [15]。S1 靠规则载体（常量、配置键、校验器名、错误和 i18n key）、co-change 历史和"keep in sync"类注释，并且必须经用户确认；S2 靠别名扩展、结构属性和从已确认示例归纳的 pattern，不能只靠名字 grep；S3 靠克隆检测（Type-1/2 和相似度 0.7 以上的 Type-3）加行为特征，合并前逐项判断差异是否有意。
3. **基线试验里唯一复现的失败是 S1 的范围决策。** 在 40 个文件的样例仓库里，3 次 T1 有 2 次没问用户就改了推断出的关联项，还改写了 API 文档里写明重置密码与注册规则相同的那句话 [L1]。你实际遇到的漏召回发生在 1 万文件以上或跨仓库的项目，小仓库没有覆盖到（评审意见）。skill 的价值一半在检索，一半在分档和确认的纪律。
4. **Claude Code 目前没有检查范围完整性的功能，官方 marketplace 的 315 个插件里也没有** [L8]。搜索实际由 Bash 调 grep/find 完成；LSP 工具要另装插件和 server，没有官方 Dart 插件 [131][136]。只靠 description 自动触发，在"修一个对象"这类简单、间接的 prompt 上最弱：一项 Sonnet 4.5 测试中无 hook 的激活率为 50-55%，间接表述约 0%（自核）[167]。
5. **设计上证据最充分的部分：** 脚本管理的 site ledger（位置、证据、档位、处置），一次性的分档确认，改完后重跑检索做残留检查，以 ledger 而不是"测试通过"判断完成。hooks（被动注入候选、Stop 门、PreToolUse ask）能补足触发和纪律，但属于决定 (d) 的扩展，需要你批准。第 8.2 节比较了三个候选架构，建议（供讨论）v1 先做只有 skill 的版本，每个 hook 做成可开关的选项，用 plugin eval 测过再定默认值。
6. **评测可以用 `claude plugin eval` 做 with/without 对比** [137]，但评测子进程运行在 dontAsk 模式，AskUserQuestion 不可用，确认门要拆成"门前"和"门后"两类用例（自核）。指标至少包括 location recall/precision、未经确认就改了推断项的次数、残留数和成本。
7. **待你决定的问题**集中在：hooks 是否纳入 (d)；首个技术栈（评审提到 Vue 先行，而 Claude Code 没有 Vue LSP 插件、ast-grep 没有 Vue 语言，未核验）；运行时是否允许 npx/uvx 下载 jscpd、ast-grep；跨仓库工作区怎么声明。见第 9 节。

## 1 问题定义与分类

### 1.1 定义

本 skill 要解决的问题叫**变更范围召回（change-scope recall）**：给定一个开发意图（用户 prompt、plan 中的一步，或已经做出的第一处编辑），找出为了满足用户的真实期望、让系统保持一致，必须或应当一起处理的全部位置，并给每个位置一个处置：直接修改、确认后修改、列出不改、排除。位置包括代码，也包括文档、配置、测试、fixture、mock 和 i18n 文案。

漏召回指一个应处理的位置既没有被修改，也没有被提出来。过度扩展是反方向的错误：改了不该改的位置，或者未经确认就改了只是推断出来的位置。基线试验中 T1 的失败属于后者 [L1]。

### 1.2 与研究概念的对应

| 概念 | 含义 | 与 S1-S3 的关系 |
|---|---|---|
| systematic edits | 在多个位置做相似但不完全相同的修改，例如 Sydit/LASE、Refazer [1][2][3] | S2 中同形的成员、S3 中的副本 |
| edit / change propagation | 一处修改引出其他位置的必要修改，后者不一定相似；Rajlich 的传播模型、CodePlan 的 may-impact 分析 [94][41] | S1，以及签名、字段改动的连带修改 |
| collateral evolution | 库或 API 变化引起所有使用方跟着改，Coccinelle 针对的就是 Linux 的这类改动 [4] | "改了定义，用法跟着改" |
| change impact analysis | 估计一次改动的影响集。综述的说法是：feature location 找到起点，"the full extent of the change is then handled by impact analysis" [95] | 全部场景的扩展步骤 |
| feature / concept location | 按概念找到实现它的代码 [95] | S2 的类别成员 |
| co-change / evolutionary coupling | 历史上经常同一次提交修改的文件或实体，例如 ROSE、TARMAQ [18][86] | S1 的跨语言伙伴、S3 的平行实现 |
| code clones | 复制后各自演化的副本。不一致的修改会引入缺陷 [21] | S3 |
| supplementary patch / omission error | 首次修复不完整，事后要补充补丁 [13][14][15] | 人类的漏改基线 |
| multi-hunk / multi-location edits | 一个修复需要多处修改 [54][56] | 修改分散程度 |
| localization recall | 定位阶段是否找全全部要改的位置 [66] | 评测指标 |

### 1.3 分类：S1-S3 之外的范围类型

下表按"为什么这个位置要一起改"分类。S1 对应 B、C、D，S2 对应 E，S3 对应 F 和 I；G、H 在三个场景里都会出现。

| 类型 | 说明 | 例子 | 主要召回信号 |
|---|---|---|---|
| A 机械连带 | 签名、字段、类型、接口变化后，调用方、覆写、实现、构造器、父类和子类必须跟着改 | CodePlan 的变更类型→关系表 [41] | LSP 引用、类型检查报错 |
| B 同一规则的多处实现 | 同一条业务规则在前端、后端、文档、测试、文案里各写一份，写法不同 | T1：常量、字面量 `>= 8`、"至少 8 位"并存 [L1] | 规则载体、co-change、需求文档 |
| C 共享状态或契约 | 一处写状态另一处读：store key、API 字段、事件、配置或环境变量、feature flag、路由、DB schema | navigation.ts 改了而 LayoutsNav.tsx 没改 [84]；feature interaction 研究发现的耦合也是一个功能写、另一个功能读 [85] | 契约抽取器、co-change |
| D 孪生实现 | 同一逻辑在另一组件、平台或分支上的实现 | 补充补丁中 36% 漏了移植到另一组件或分支 [13]；Mozilla 的 Chimera/Camino 平行代码、gtk/xlib 克隆 [19] | co-change、相似度、多仓库检索 |
| E 同类成员 | 按概念定义的一类对象，名字各异、位置分散 | T2：两个弹层的名字里看不出是弹窗 [L1] | 别名扩展、结构属性、示例 pattern |
| F 重复与漂移副本 | 复制后各自修改的副本，从完全相同（Type-1）到只有行为相似（Type-4） | T3：6 处日期格式化，3 处已写偏 [L1] | 克隆检测、行为特征 |
| G 外围产物 | 文档、配置、测试、fixture、mock、i18n、迁移脚本 | ProMax 失败运行漏掉的类别 [51]；文档类 gold 文件 73% 被漏 [68] | 固定清单扫描、co-change |
| H 条件与兄弟分支 | else 和 null 分支、相邻的枚举值、重载、兄弟子类 | 补充补丁中 15% 是条件处理不当 [13] | 同文件扫描、结构检索 |
| I 旧模式残留 | 改完后仍然匹配旧写法的位置；S3 中保留旧逻辑、外面加一层 guard | 通过测试的补丁有 29.0% 用 guard 保留旧逻辑 [76] | 改后重跑检索、旧模板匹配 |
| J 跨仓库 | 耦合位置在另一个仓库，比如多个独立的前端仓库 | 评审指出你的漏召回发生在跨仓库场景 | 工作区声明、多仓检索 |

另有两个维度和类型正交，决定一个位置该进哪一档：

- **证据能否证明。** A 类可以由 LSP 或类型检查证明，B-F 类大多只能推断。agent-failure 维度的综合结论是：只有机械上必需的连带修改（例如改了签名之后的调用方）可以不问就扩展；只要纳入一个位置会改变别人能看到的行为，就要先问。
- **触发点。** 意图可以来自 prompt 点名的对象、plan 的一步，或者第一处编辑。第一处编辑提供的信息最多，可以直接拿来做查询（第 4 节的 patch-as-query）。

## 2 根因分析

下面每一条原因都能单独成立，对应的对策也不同。

### 2.1 需求没有说出来（S1 的主因）

- SWE-RPG：每个任务平均有 4.53 个需要澄清的点；在各类失败里需求类最多，占运行的 24.5-46.0%；Claude Code 生成的计划只覆盖了 41.6% 的约束 [69]。
- DevIntent：Sonnet 4.6 的意图违背率为 54.5%，按题目统计接近 0 或 1，即同一道题上要么几乎每次都违背、要么几乎从不违背 [70]。
- Yang 等：LLM 默认只有 41.1% 的情况会推断出没写明的需求；需求没说清的 prompt 在换模型或改 prompt 后退化的概率是说清楚的 2 倍（未核验）[81]。
- Opus 4.8 的提示指南写明模型"does not silently generalize an instruction from one item to another" [83]，所以 Agent 会按字面只改被点名的对象。
- 基线试验 T1：3 次都找到了全部关联位置，但有 2 次自己决定新增一个只给注册用的常量，把共用规则拆成两条，并把文档里的"重置与注册规则相同"改掉了 [L1]。问题出在决策，不在检索。

### 2.2 范围决策随模型变化，而且偏向动手

- FixedBench：在本来不需要改代码的任务里，Agent 有 35-65% 仍然改了代码；要让 Agent 不改，就得把"不改"明确算作成功 [71]。
- 加一条"保持原样"的指令后，多余的编辑距离从 0.195 降到 0.131，Pass@1 提高 2.3 pp [72]。
- 一个 Claude Code issue：Agent 在 navigation.ts 里移动了一个导航项，没改 LayoutsNav.tsx，随后修补了 4 次，还擅自重命名 [84]。同一件事里既有漏改，也有越界。

### 2.3 词汇不匹配（S2 的主因）

- Furnas：两个人给同一事物选同一个词的概率低于 0.20；只用一个词检索，80-90% 的情况找不到；不限数量地加别名，命中率能提高好几倍 [111]。
- 开发者给同一事物起同一个名字的中位概率是 6.9%（n=334）[112]。
- Critics 的用户研究里，关键词搜索的结果不稳定 [9]。
- 克隆检测替代不了按概念找：Hercules 用 AST 相似度、def-use 上下文和 co-change 历史定位了 154 个 bug 中的 84%，Deckard 克隆检测只有 26% [45]。

### 2.4 遗漏位置大多与首个改动没有结构联系

- 只有 10-20% 的补充修改位置与首个补丁有一跳关系（调用、克隆、同名、co-change）；单一信号的 precision 不超过 9%，几种信号组合后 F 值也不超过 10% [15][14][16]。
- 反过来，补充修改有 42-48% 距首个补丁不超过 25 行，70-94% 的重复修复组集中在同一个文件里 [15][14][16]。先扫同一文件、再扫同一 package，比顺着调用图走更划算。
- 补充补丁漏掉的东西：36% 是没有移植到另一个组件或分支，20% 是漏了改动所引用或引用改动的代码，15% 是条件处理不当，其余是配置、兄弟子类和 visitor 关联 [13]。

### 2.5 改动分散度和定位粒度

- Defects4J 中 44.6% 的 bug 是 multi-hunk。o4-mini 对改动最集中的一类（Nucleus）修好 49%，对最分散的一类（Sprawl）只修好 22% [56]。
- SWE-bench 的运行在文件级命中 59-97%，函数级只有 14-34% [66]。
- PolyHunk（404 个 bug）：Claude Code 修好 92.8%；只有 66.1% 的运行，其修改的文件集合覆盖了开发者补丁的全部文件（允许多改）。一个需要改 16 个文件的 bug，它只改了 3 个；失败的运行搜索更多、编辑更少 [54]。
- RepoRescue：14 个需要全代码库协同修改的修复，Claude Code 最多通过 2 个，Codex 的对应数字是 14 [55]。
- 在 SWE-bench 定位上，Claude Code 与专门的定位方法相差不大：函数级 Acc@5 在 Lite/Pro 上是 85.4/59.5，SWE-Adept 是 87.8/63.3 [49]。差距出在大范围协同修改，不在单点定位。

### 2.6 状态丢失，过早宣布完成

- RefactorBench：没有一个基线解决了超过 6 个文件的任务，人类是 87%；约 44% 的检查项里，目标文件从头到尾没被编辑过；给 Agent 加上编辑状态摘要后，相对提升 43.9% [52]。
- Anthropic 的工程文章描述了 Agent 看到一点进展就"declare the job done" [82]。
- ProMax（170 个任务，平均 11.4 个文件）：失败的运行比 gold 少改文件，漏的是外围调用点、文档、配置和 fixture [51]。RefactorPlatform：50.9% 的失败是漏了最后 1-2 个文件或者弄坏了 import [53]。
- MAST 的多 agent 失败分类里，过早终止占 6.2%，没有验证或验证不完整占 8.2%，验证错误占 9.1%（未核验）[80]。
- SKILL.md 在会话中不会被重读，上下文压缩后只回填前 5,000 token [129]。长会话后期，skill 正文里靠后的规则可能已经不在上下文里。

### 2.7 测试看不见漏改

- 22 个看似正确、实际错误的 SWE-bench 补丁中，一半通过了开发者的全部测试，27% 只修了一部分 [78]。
- "Incomplete Repair"（忽略了显式或语义依赖）是一类单独的失败；加一个专家评审回路后，108 个失败 issue 中解决了 24 个，没有这个回路是 7 个 [79]。
- CodePlan 用构建错误驱动下一轮修改，但只改行为的修改不会触发构建错误，所以会被漏掉 [41]。S1 的规则耦合正好属于这一类。

### 2.8 S3 特有：回避删除，复用随轮次衰减

- 通过测试的补丁跳过了开发者所做删除的 28.3-34.8%，有 29.0% 选择加 guard 保留旧逻辑；给出精确的删除范围后，成功率提高 6.5-31.5 pp [76]。
- 5 轮对话中，仓库级 recall 从 83.6% 降到 35.4%，含重复实现的调用链从 13.8% 升到 50.8%，而测试通过率没有变化 [77]。
- 只有 1.1% 的 Agent 重构以消除重复为动机，人类是 13.7% [39]。CodeTaste 中，让 Agent 自己发现重构机会时成功率不到 8%，先提方案再实现是 15.1% [40]。
- 本地复现：模拟合并之后，没被处理的漂移副本与新的共享代码相似度为 0.87，按规范字段名 grep 找不到它 [L6]。

### 2.9 有工具也不用

- JetBrains 的第一次实验里，Agent 一次也没调用 IDE 检索工具；2,700 次重跑中 GPT-5.5 仍是零调用，GPT-5.6 在 675 次中有 616-660 次用了，成本中位数增加 6-7% [122]。
- 一场 ContextBench 的演讲报告，Claude Code 不会稳定地选择语义检索工具 [125]。
- 基线试验第 2 轮共 9 次运行、283 次工具调用：Bash 88 次，Read 65 次，Grep、Glob、LSP、Agent 都是 0 次 [L2]。在 macOS/Linux 上 Grep 和 Glob 本来就不是默认工具，搜索走 Bash 里的 bfs/ugrep [131]；本机探测到的 language server 只有 sourcekit-lsp 和 clangd 在 PATH 上，gopls、pyright 都没有 [L10]。

### 2.10 skill 本身没被触发

- skill-creator 的说明：Claude 只在自己不容易完成的任务上才去查 skill，所以 skill 往往触发不足，"Simple, one-step queries... may not trigger a skill" [151]。S1-S3 的请求看起来都很常规。
- 一项用 Sonnet 4.5、22 个 prompt 的测量：无 hook 对照组激活率 55%/50%；prompt 里出现 skill 关键词时约 100%，泛化表述 20-40%，间接表述约 0%（自核）[167]。Vercel 的评测中 56% 的情况 skill 从未被调用，通过率 53%，与不装 skill 相同（自核）[168]。
- skill 列表总共只占 1% 的上下文，超出时最少被调用的 skill 先丢掉描述 [129]。一个新装的 skill 正好是最少被调用的。

### 2.11 规模和跨仓库

基线试验的样例仓库只有 40 个文件，Agent 能读完大部分，所以检索类漏召回没有复现 [L1]。评审指出你实际遇到的漏召回发生在 1 万文件以上或跨仓库的项目。规模一大，读不完就只能靠检索，检索又受 2.3、2.4 节的限制；hook 和脚本的时间预算也会收紧（第 6.5 节）。

## 3 已有研究与工具

### 3.1 经典 systematic edits 工具

| 工作 | 做法 | 关键结果 | 局限 |
|---|---|---|---|
| Sydit [2] | 从 1 个示例编辑推导变换，目标位置由用户指定 | 56 个编辑中 82% 应用上了编辑，只有 70%（39/56）与开发者的修改完全一致 | 不负责找位置 |
| LASE [1] | 从 2 个以上示例中只把彼此不同的名字抽象成变量，加上依赖上下文，扫描全部方法 | 24 组 Eclipse 修复上 P 99%、R 89%，找到 9 处开发者漏改的位置。只用 1 个具体示例时 R 60%，名字全部抽象时 P 75%。"示例从 2 个加到 5 个，recall 从 51% 升到 100%"只是 Table II 里的一个案例（Index 4），不是平均值；多加示例也可能降低 precision（Index 12 从 78% 降到 31%） | 结果取决于示例是否足够多样 |
| Refazer [3] | C# AST 上的 programming-by-example，排序偏好短上下文 | 59 个场景（中位 5 处）中 83% 学会了变换，平均用 2.8 个示例。11 个场景里多找出的位置是开发者漏改的（Roslyn：开发者改了 26 处，工具多找出 689 处，经确认）；10 个场景（17%）多找出的是错的 | 泛化后可能成倍扩大命中 |
| Coccinelle / spdiff / SPINFER [4][5][6] | SmPL 语义补丁（元变量、`...` 路径、同构规则）；spdiff 和 SPINFER 从示例推断语义补丁 | 62 次 Linux API 变化涉及 5,800 个文件，完整更新了 93% 以上，还修好了 150 多个维护者改错的文件，漏掉的都是数据流相关的情况。spdiff 从 3 个文件推断，也修好了别处被忽略的文件。SPINFER P 86%、R 69%，漏的是没见过的写法 | 只针对 C；规则要写或推断 |
| Getafix [7] | 用 anti-unification 从修复中生成由泛到专的模式，按普遍性、位置、具体程度排序，修复后由静态分析器复查 | Top-1 完全一致 12-91%（按类别）；1,268 个中 Top-5 命中 41%；约 250 条上线建议中 42% 被接受 | 要修的位置由分析器给出 |
| LSdiff / Critics [8][9] | LSdiff 推断"Y 的所有子类型中的 X 都改了，W 除外"这类规则（至少 3 个匹配，准确度≥0.75）；Critics 找仍然匹配旧模板、不匹配新模板的代码 | LSdiff 的规则覆盖了 75% 的结构性改动，规则的例外就是可能的漏改。Critics 的用户研究中 12 人有 11 人找全了漏改，只看 diff 的只有 4 人；用户细化 2-3 轮后就停手 | 都要人来判读 |
| LAPIS / Codelink / CloneTracker [10][11][12] | 用户选中多个副本，工具建立链接并同步编辑 | LAPIS 从 1 个示例推断出 84% 的选择，但 24 次中有 8 次留下了没改正的错误（纯手工是 5 次），原因是用户没发现差一点就匹配上的选择；要到 3.6-8.4 条记录才比手工划算。Codelink 建链接用 22 秒，手工抽象要 13 分钟。CloneTracker 用（文件、类、签名、块）锚点正确追踪了 96% 的区域 | 副本要人来指定 |
| Nguyen 等 [17] | 统计 2,841 个 Java 项目中重复出现的改动 | AST 高度 1-2 的改动有 60-100% 会重复出现，高度越大越少，6 以上很罕见。方法调用是最常见的改动类型，重复次数也最多，但重复率（40%）居中；数组（56-82%）、后缀/前缀/中缀表达式（53-92%）、super 构造调用（72%）重复率更高，if（10%）和循环（≤6%）最低。FixWizard 报告 17-45% 的修复会重复出现（转引自 Park 2016） | 只说明哪类改动容易重复 |

这些工具在基准上表现很好，也确实找到过开发者漏掉的位置，但有三个共同前提：要有 2 个以上、彼此有差异的示例；改动本身是同形的；只支持一种语言。补充补丁的研究说明，大部分遗漏不满足这些前提：23-34% 的已修 bug 需要补充补丁，只有 7-17% 的补充补丁与首个补丁相似 [13]。S1 这种没有结构联系的耦合，需要就近扫描和用户确认来补。

### 3.2 Impact analysis 与 co-change

| 工作 | 做法 | 关键结果 | 局限 |
|---|---|---|---|
| ROSE [18] | 从版本历史挖关联规则，用 support 和 confidence 设阈值 | 8 个仓库。宽松阈值（support 1、confidence 0.1）：66% 的查询有回答，precision 29%、recall 33%。严格阈值（support 3、confidence 0.9）：在只漏一项的测试中只有 3% 发出警告，警告的 recall 约 75%、precision 超过 66%，误报约 2% | 多文件查询只有约 25% 有回答 [86] |
| Ying 等 [19] | 基于 co-change 的修改推荐 | Mozilla precision 约 0.5、recall 0.2-0.3；Eclipse 约 0.3、0.1-0.2。Mozilla 上有用的推荐是 XUL/JS/XML-schema 配对、Chimera/Camino 的平行代码、gtk/xlib 克隆；Eclipse 上大多显而易见 | recall 低 |
| TARMAQ 与挖掘参数研究 [86][87][88] | 用查询集合中最大的重叠子集匹配规则 | 能回答所有多文件查询。39 种兴趣度量中有 11 种在统计上并列最好（最好 0.446，confidence 0.444）。只用改了 6-8 个文件的提交来学习效果最好（6 个为 0.464，8 个为 0.463，同在最好的一组）。历史取 5k/15k/35k 个提交时 MAP 为 0.285/0.312/0.322；规则过时 100 个提交后，MAP 从 0.376 降到 0.329 | 需要完整历史 |
| GitCF（预印本）[91] | co-change 加上提交信息和 diff 标识符的 TF-IDF | 17 个 OSS 项目中 543 个真实的不完整改动，Hit@10：TARMAQ 0.147，TAR 0.322，GitCF 0.403-0.416。参数是在测试数据上选的 | 真实遗漏比留一法难得多 |
| Hattori / Musco / Rajlich [92][93][94] | 静态影响分析该走多深 | Hattori（3 个 Java 系统）：深度 1 P 84%/R 81%，深度 2 为 76%/94%，不限深度 73%/100%，准确度最高的是不限深度。深度 1 用 19 个点的 recall 换了约 11 个点的 precision，所以传递闭包的代价是 precision，不是 recall。Musco（10 个 Java 项目）认为最简单的调用图权衡最好，但它全程用传递闭包，支持不了深度限制。有依据的停止规则是 Rajlich 的：只从真正改了的节点继续传播 | 只覆盖结构依赖 |
| Dit 综述 / Kagdi [95][96] | feature location 找起点，impact analysis 定范围 | 综述覆盖 89 篇文章。Kagdi（EMSE 2013）把文本耦合与演化耦合结合后，F-measure 比只用文本耦合最多高 14 个点，比只用 co-change 高 21 个点。常被引用的"recall 提高 20% 和 45%"可能出自 WCRE 2010 版本 [97]（未核验） | 需要文本和历史两种数据 |
| LiSSA（ICSE 2025）[99] | embedding 取 top-20，再由 GPT-4o 判断需求与代码的追踪关系 | F1 0.322，LSI 为 0.285。只做检索时 recall 最高（eTour 0.815，precision 0.216）；LLM 过滤提高了 precision，降低了 recall | LLM 过滤会丢真阳性 |
| 跨产物链接 [100][101][102] | schema、测试、API 规范与代码之间的链接 | Qiu（10 个数据库应用）：约 50% 的抽样 schema 修订在同一提交里就有包含真实改动的代码，约 22% 不需要改代码，其余约 27% 的 co-change 证据缺失或有误导（代码改动在另一个提交里，或同提交的代码与之无关）。TCTracer 按测试命名约定链接，类级 P 100%、R 80%，方法级 R 只有 11%。Wittern 对照 API 规范静态检查 JS 请求，precision 96% | 依赖命名约定和规范文件 |

核查员补充了几项没有核对的经典工作：Hassan & Holt 比较了历史、结构、开发者和文件布局几类传播启发式 [20]（未核验）；Gethers 等从变更请求文本出发，组合 IR、动态分析和 co-change，入口与 prompt 驱动的 skill 相同 [98]（未核验）；Rolfsnes 等发现聚合所有适用规则比每个文件只留最好的一条规则效果好 [89]，用随机森林预测推荐的相关性比直接用 support/confidence 好，与分档阈值直接相关 [90]（均未核验）。

本地复现（stdlib Python 写的 TARMAQ）[L5]：flask、vue、django 分别有 3.8k、7.2k、34k 个提交，加载 0.1-1.5 秒，单次查询不到 1 毫秒。对 300 个提交做留一法：hit@10 为 0.65/0.78/0.49；按档位的命中率，support≥3 且 confidence≥0.5 为 52-72%，support≥2 且 confidence≥0.2 为 13-19%，其余约 5%；严格警告 80-90% 的情况下确实包含被留出的文件，误报 2-6%。flask 不加提交大小过滤时，最高档命中率降到 16%，警告 precision 从 73% 降到 9%。git 方面：Git 2.54 的 blobless 克隆用 `--name-only --no-renames` 读完 flask 全部历史只要 0.09 秒，不下载 blob；开启改名检测会去取 blob（每 1,000 个提交 21 秒）；code-maat 用的 `--numstat` 每 200 个提交 262 秒 [104]。actions/checkout 默认 depth 1，`fetch --unshallow --filter=blob:none` 用了 6.4 秒 [103]。

### 3.3 克隆检测与重复合并

| 工作或工具 | 关键结果 | 对本 skill 的意义 |
|---|---|---|
| BigCloneBench 召回评测 [24] | T1/T2/VST3/ST3/MT3/WT3-T4 的 recall：NiCad 100/100/100/95/1/0，SourcererCC 100/98/93/61/5/0。MT3（相似度 0.5-0.7）上 5 个工具都不超过 12%，WT3/T4 都不超过 1% | 克隆检测覆盖 S3 中写偏不多的副本；S2 里名字无关的成员要靠别的信号 |
| Juergens 2009 [21][22] | 1,427 个克隆组中 724 个修改不一致，其中 203 个是无意的，107 个含缺陷，也就是约一半的无意不一致导致了缺陷。另一项研究中，89 个独立实现之间只有 3.9% 的实现对共享克隆 | 漏改副本的代价是真实缺陷；功能相同的独立实现在语法上通常不相似 |
| Barbour 2013 [25] | late propagation（副本晚些时候才同步）占发生过修改的克隆谱系的 8-21%，更容易出缺陷 | 改了一处副本后要立刻列出其余副本 |
| Kim 2005 / Kapser 2008 [26][27] | 49-64% 的克隆谱系用标准重构不容易消除。replicate-and-specialize 克隆被评为"好"的比例：Apache httpd 76%，四个样本中为 33-71%，Gnumeric 的小克隆样本中近 44% 被评为有害；parameterized-code 克隆在 Gnumeric 中 71-76% 有害 | 很多克隆应该保留；是否该合并的先验随系统不同 |
| RASE [23] | 以编辑范围计，54-67% 的情况能自动消除克隆（以方法范围计 30-34%）；开发者实际只重构了 56 个中的 4 个 | 只抽取能参数化的区域，其余同步修改并登记 |
| Göde & Koschke 2011 [31] | 大多数克隆很少被修改，对克隆的修改中无意的很少 | 决定提示多少克隆时，要和 Juergens 的结果对照着看 |
| CP-Miner [30] | 把标识符重命名不一致的副本当作 bug 报出，在 Linux 找到 28 个，在 FreeBSD 找到 23 个 | 副本内部的不一致重命名是一种可检测的信号 |
| Tsantalis 2015 [28] | 映射克隆对的语句并检查前置条件，判断两个克隆能否合并 | 可作为 S3 的合并测试 |
| Siamese [29] | 以代码片段为查询的增量克隆搜索 | 与"以编辑点为种子"的查询方式最接近 |
| jscpd v5 [32] | Rust 引擎，npm 和 PyPI 都有，5.4.2 发布于 2026-10-20。默认 `--mode` 是 mild，默认克隆种类是 exact，阈值 50 token、5 行。可选 `--ignore-identifiers`、`--similarity`（AST，0.8）、`--semantic`（548 MB 本地模型，或用 `--semantic-url` 调 embedding API）、ai 报告器、MCP 工具 check_duplication。Dart 只有 token 模式。文档称人工判断 CodeRankEmbed 找出的语义重复对中 93% 是真重复（jina 为 83%），阈值在 Rosetta Code 上校准；token 和 AST 模式没有公布准确率。版本要锁定：5.4.2 里单独写 `--ignore-identifiers` 表示一致重命名（`=blind` 才是旧行为），5.4.1 改过 `--similarity` 的分数 | 首选的全仓检测器，但本机 npm install 被拒，未实测 |
| PMD CPD [33][34] | 支持 JS/TS、Java、Kotlin、Go、Python、Swift、Dart，需要 JVM。忽略标识符和字面量只支持 Java/C++。退出码 4 表示发现了重复。一项 2025 年的基准测得 Type-3 recall 31% | Dart 和 JVM 项目可用；Java 以外只能找 token 完全相同的副本，报告为空不代表没有近似重复 |
| LLM 与 embedding 判定 [35][36][37] | GPT-4 在 BCB 上 MT3 recall 0.87，WT3/T4 0.23。跨语言 CodeNet 的 F1：GPT-3.5 0.34-0.79，embedding+SVM 平均 0.99，直接用余弦相似度 0.74-0.78。BCB 中抽样的 WT3/T4 对有 93.3% 不是真克隆 | 只用来判定短候选清单；BCB 的 Type-4 标注不可靠，要用自带 fixture 校准 |
| ICCheck [38] | `iccheck --from HEAD --to WORKTREE` 列出与改动 hunk 相似但没改的代码（逐行字符 bigram Dice 0.7）。9,368 个提交上中位耗时 0.27 秒，28.7% 的提交被标记，CBCD 上 precision 0.70、recall 0.23。Go 二进制 | 改后检查；结果为空什么也证明不了 |

本地测量 [L6]：在一个 TS fixture 上，把标识符统一替换后用 difflib 算序列相似度，Type-1 为 1.00；Type-2 也是 1.00，尽管税率从 0.08 变成了 0.2；Type-3 为 0.89（k=5 的 Jaccard 只有 0.55）；Type-4 为 0.47-0.50；不相关代码 0.28-0.48。在 Python stdlib 中随机取 3,000 对函数，p99 为 0.58，p99.9 为 0.64，只有 2 对达到 0.7。规模上，Python 3.9 stdlib 的 9,486 个函数加载用 3.3 秒，1 对 N 查询 7.2 秒，建索引后两两比较要 140-160 秒；相似度 0.8 以上的 1,355 个组中 75% 涉及 site-packages 或 `_vendor`，剩下的有 84% 在同一文件内。

### 3.4 LLM 时代的工作

第 2 节已经用 ProMax、RefactorBench、PolyHunk 等基准说明了 Agent 怎样漏改。下表列的是可以借来提高召回的做法，都不需要训练模型。

| 工作 | 做法 | 关键结果 | 对本 skill 的意义 |
|---|---|---|---|
| CodePlan [41] | 每次编辑按改动类型产生待办：改签名查调用方和覆写；改字段查使用方、构造器、父类和子类；改方法体只在调用方能看到的状态变了时才查调用方。构建错误作为下一轮的种子 | 6 个仓库中 5 个通过有效性检查，给同样上下文但不做规划的基线是 0 个 | 每个技术栈配一张"改动类型→关系"表，按 worklist 迭代到不动点，用类型检查判定。只改行为的修改不会报错，标成 S1 的待确认候选 |
| TRACE [42] | rename、def-use、克隆、诊断类编辑交给 IDE 工具，其余交给神经定位器 | P/R 为 69.6/67.9，CoEdPilot 为 48.4/61.8；不加区分地调用所有工具时 P 只有 22% | 先给种子编辑分类，再决定调哪种工具。LSP 引用适合 rename、签名和 def-use |
| GrACE / CoEdPilot / Coeditor [43][44][63] | 以已经做出的编辑为条件，预测其他位置的编辑 | 相关的先前编辑让 Codex 的 exact match 从 37.1 升到 67.9。CoEdPilot 从一处编辑找共改文件，P 79.5、R 72.9；用相关的先前编辑和随机的先前编辑，EMR 是 41.8 对 18.9。Coeditor 单轮 exact match 从 34.7 升到 60.4 | 思路可以用脚本实现：从示例编辑抽出改前写法和改动的标识符，检索仍然匹配旧写法的位置，循环到没有新位置为止（第 4 节的 patch-as-query） |
| PyCraft [62] | 用 LLM 生成同一编辑模式在语法和控制流上的变体，让 transformation-by-example 能匹配写法不同的位置 | 正确变体的 F-measure 为 96.6%，输入平均扩展 58 倍，可匹配的目标最多增加 39 倍 | 对应 S2/S3 中名字不同、写法不同的成员。扩展出的命中只能进待确认档 |
| Hercules / SiblingRepair [45][46] | 给兄弟位置打分：Hercules 用 AST 相似度（≥0.8）、def-use 上下文和 co-change 历史；SiblingRepair 用 TF-IDF 和 embedding 召回，再由 LLM 挑选 | Hercules 定位了 154 个 bug 中的 84%，Deckard 克隆检测只有 26%。SiblingRepair 在 70.1% 的情况下覆盖了全部兄弟方法，48 次遗漏中 12 次出在候选生成阶段 | 写一个 find_similar 脚本，按函数或组件计算规范化 token 和 AST n-gram 分数：分数高且共享上下文的进 2 档，分数低的进 3 档 |
| RepoMem [47] | 在历史提交上做 BM25 检索 | SWE-bench Verified 上，LocAgent 的文件级 Acc@5 从 71.6 升到 76.5，但在提交少于 1 万的仓库上下降 13.1 pp | 把相关提交当作 2 档证据引用；历史稀疏或被 squash 的仓库要降权 |
| CoSIL / SWE-Adept / RepoGraph [48][49][50] | 迭代调用图搜索；依赖 DFS，先看预览再展开；仓库级代码图 | CoSIL 去掉迭代调用图搜索后 Top-1 从 0.433 降到 0.320。SWE-Adept 与 Claude Code 的对比见 2.5 节。RepoGraph 一跳有用（+2.3 pp），两跳整图塞进上下文没有用 | 一次扩一跳并带证据，连续两轮检索都没有新增就停；不要把多跳图贴进上下文 |
| LocAgent [64] | 把仓库建成文件、类、函数组成的有向图，边是 import、调用和继承，agent 在图上多跳推理 | 文件级准确率最高 92.7% | 可作为 S1 依赖图工具的参照 |
| 结构锚点、按子系统探索 [67][68] | 给检索结果加调用和继承标签；每个子系统派一个探索 agent | 结构标签让 Func@5 提高 2.2 pp，在中等规模仓库上方差减半、Pass@1 提高 3.4 pp。同为 Haiku，按子系统扇出后找全 gold 文件的实例从 3.3/19 升到 6.4/19（单个顺序执行的 Sonnet 是 3.4/19），单个更强的 Codex 5.5 High 是 9.2/19。文档类 gold 文件 73% 被漏 | 扇出能帮弱模型，但赢不了强的单 agent。无论用哪种方式，都要固定扫一遍文档、配置、测试和 mock |
| RevPropBench [57] | 对话中逐步搭建的 JSON 产物里的变更传播 | 遗漏是主要错误。同时看产物和对话，比只看其中一个好。多次采样取交集损失 13-21 pp，由 LLM 挑选提高 3.3-12.5 pp，4-5 次调用后饱和 | S1 要把需求历史（prompt、PRD、工单）和代码一起读；做 2-3 次独立枚举取并集，逐项核实，弱候选降到 3 档 |
| next-edit 模型 [58][59][60] | 行内建议模型预测下一处编辑 | Copilot 博客中每次输出 1.3-1.4 个 patch 的是 v2 SFT 中间模型，博客没有给出最终上线模型的数字。Claude 4 Opus 预测下一处位置的准确率是 80.5%，内容完全一致的是 45.7%。EditFlow 中 Claude Code 的后续建议有 51.23% 属于 Break 类（建议的内容不在真实提交里），算上 Jump 和 Revert 是 65.84%；加一个顺序过滤器，precision 从 40.5 升到 50.5，recall 从 39.5 降到 36.2 | 这类模型只看局部，所以枚举范围要和编辑分开做。2 档按依赖顺序呈现，被过滤掉的降到 3 档 |

另有两点要注意。Hunk4J 中加了编译和测试反馈的配置把 o4-mini 从 26.9% 提到 35.75%，但这个配置同时加了方法级上下文和相似历史补丁检索，论文没有单独消融反馈，所以这 8.9 pp 不能都算在反馈上，成本约为基线的 4.4 倍 [56]。SWE-bench 上的定位结果可能受模型记忆影响：只给 issue 文本时，Claude 3.5 在 Verified 上 65% 的实例能说出全部 gold 文件，在 BeetleBox 上只有 12.2%（未核验）[65]。目前没有研究在真实代码里测量过 S1 类耦合的召回。

### 3.5 工业工具

工业界的大规模改动系统（Google LSC、OpenRewrite）做法相近：从语义索引取一个有意偏大的候选集，逐个分类，修改，再构建和测试。没有一家公布发现阶段的 recall。

| 工具或实践 | 能力 | 限制 | 在本 skill 中的用法 |
|---|---|---|---|
| Google LSC [113][61] | Kythe 给出调用方，Rosie 按 owner 拆分改动，TAP 跑测试。2025 年的 LLM 迁移沿"引用的引用"走到距离 5，有意保留超集，让 LLM 跳过不需要改的位置。39 次迁移、595 个变更、93,574 个 edit，LLM 生成了 74.45% 的变更和 69.46% 的 edit，开发者估计比手工省时 50% | 没有公布发现阶段的 recall | 先取超集再分类：每个候选带证据归档，构建和测试之后重跑发现，直到旧写法不再命中 |
| Claude Code LSP 工具 [115][116][131] | findReferences、goToImplementation、workspaceSymbol、incomingCalls | 没有 rename 和 type hierarchy；文件没有匹配的 server 时直接报错；云端会话不可用。官方插件有 TS、pyright（不支持 goToImplementation）、gopls、jdtls、kotlin-lsp（alpha）、sourcekit-lsp，没有 Dart | 引用和实现的结果可作直接证据；没有 server 或方法时退回 ast-grep 或 grep，命中降为推断；只建议安装插件，不替用户装 |
| ast-grep [117] | 内置 TS/JS、Java、Kotlin、Go、Python、Swift 和 Dart（0.42.1 起重新支持 Dart；npm 的 @ast-grep/cli 和 PyPI 的 ast-grep-cli 当前都是 0.51.0）。`$X` 匹配一个节点，`$$$` 匹配一串节点，重复使用同一个元变量名要求两处代码相同；YAML 规则可以组合 kind/regex、inside/has、all/any/not | 只做语法匹配，没有类型信息。同类工具 Comby 最后一次发布是 2022 年 | 2 档的默认手段：把一个示例改写成元变量 pattern，先用 `--stdin` 测试，再匹配 S2 成员和 S3 副本，命中标为推断 |
| Semgrep CE [118] | 带类型的元变量（Java 的 `(Logger $L)`，Go/TS 的 `$X: T`）、import 别名等价、`<... ...>` 深层匹配、`fix:` 自动修复；支持的语言含 Kotlin、Swift、Dart | CE 没有跨文件分析；PyPI 版要求 Python 3.10 以上 | 可选，用来按类型或导入别名收窄形状匹配；运行时加 `--metrics off` |
| OpenRewrite [119] | LST 保留类型和格式；FindImplementations、FindMethods 等 recipe 标记命中；`rewrite:dryRun` 输出 `target/rewrite/rewrite.patch` | 开源版只支持 Java、Kotlin、Groovy 三种编程语言（另支持 HCL、JSON、Properties、Protobuf、TOML、XML、YAML 和 Maven/Gradle）；JavaScript、C#、Python 由商业版 Moderne 提供，没有提到 TypeScript；LST 要能放进内存 | 只作 JVM 栈的可选工具：成员身份取决于类型、或代码在 JAR 里时使用，需要能构建的 Maven/Gradle 项目 |
| ts-morph / LibCST / fastmod [120] | ts-morph 封装 TS 编译器（findReferencesAsNodes、getImplementations、rename）；LibCST 的 FullyQualifiedNameProvider 能解析导入名，包括相对导入 | LibCST 要类型信息需配 Pyre；fastmod（正则）和 jscodeshift 只做语法 | 没有 LSP 时用的小型发现脚本 |
| SCIP / Zoekt / Batch Changes [121] | SCIP indexer 覆盖 Java/Kotlin、TS、Python、Dart、Rust、C++；Zoekt 是更快的 trigram 索引，词法 recall 与 rg 相当；Batch Changes 按查询选出仓库，在容器里执行步骤，生成草稿 changeset | 要先建索引或有 Sourcegraph 实例 | 单仓库不需要。SCIP 可作没有 LSP 时的无界面退路；多仓库的 S1 可以借鉴"检索→步骤→草稿审阅"的流程 |
| IDE 检索工具 [122][123] | JetBrains 的实验见 2.9 节。Netflix 让 Agent 经 LSP 使用 IntelliJ（Java/Kotlin） | Netflix：效率提高 20-30%，正确性不变；grep 找不到 JAR 里的代码；JDT LS 在 Gradle 项目上失败 | 只是"可用"的工具不会被调用，要写明调用时机：每个改了的符号调 findReferences，每个改了的接口调 goToImplementation |
| Embedding 检索 [124][125] | Cursor：语义检索加 grep 比只用 grep 的离线问答准确率高 12.5%，线上代码保留率只提高 0.3%（1,000 个文件以上的仓库为 2.6%）。ContextBench 演讲：文件级 precision 65%→81%→87%，recall 49%→39%→39% | 提高的是 precision，不是 recall；Claude Code 不会稳定地选用语义检索工具 | 只用于 S3 中行为相似的低置信候选，只列不改，不作为召回层 |
| Serena [126] | 基于 LSP 的 MCP 工具集：find referencing symbols、rename，部分语言支持 find implementations；覆盖 40 多种语言，含 Dart、Swift、Kotlin；JetBrains 后端另有 type hierarchy、依赖内搜索和 propagate deletions | 要另装 | 环境里有就用，命中要读代码核实；不作为依赖，也不打包 |
| CodeQL [127]（未核验） | 对 Java/Kotlin、JS/TS、Python、Go、Swift、C#、C/C++、Ruby、Rust 做类型、调用图和数据流查询 | CLI 许可规定，没有 GitHub Advanced Security 时不能用于非开源代码 | 私有仓库基本用不上 |
| PolyglotPiranha [128]（未核验） | 规则图的边（例如 scope=parent）把一次改动级联到后续的清理 | 要为每类改动写规则 | 工业界最接近 edit propagation 的现成机制，级联规则的写法可以参考 |

本机探测 [L10]：rg 是一个 shell 函数，包装内置的 ripgrep 14.1.1，Python 的 subprocess 看不到它；git grep 可用。ast-grep、semgrep、comby、gopls、pyright、brew 都没有；node 24、npx、uvx、python 3.9 都有。`npx ast-grep` 会运行一个 2018 年的无关包，能用的写法是 `npx -y -p @ast-grep/cli ast-grep` 或 `uvx --from ast-grep-cli ast-grep`。所以脚本要先用 `command -v` 探测，不能调用 rg（改用 git grep），第一次 npx/uvx 下载之前要问用户。

评审补充了几处冲突（未核验）。Claude Code 没有 Vue 的 LSP 插件，ast-grep 和 Semgrep 都没有 Vue 语言，auto 模式下 `npx ast-grep` 会被拦截，而首个技术栈可能是 Vue。另外，6.5 节的规模数字是用 rg 测的，git grep 在 10 万个文件上的速度没有测过；本机 shell 的 grep（ugrep）曾因正则太复杂拒绝执行，所以"用一个大正则匹配全部名字变体"有风险。

### 3.6 Claude Code 生态

Claude Code 没有检查改动范围的功能。能用的手段是 Bash 里的 grep/find、可选的 LSP 工具、只读的 Explore 子代理、hooks，以及 AskUserQuestion 和 plan approval。

**搜索和代码理解**

- 在 macOS/Linux/WSL 上，Glob 和 Grep 不是默认工具，Claude 通过 Bash 调用内置的 bfs/ugrep，hook 看到的也是 Bash 调用 [131]。基线试验第 2 轮的工具分布见 2.9 节 [L2]。
- LSP 工具要装 code-intelligence 插件和对应的 server 才会启用，云端会话里不可用 [131][136]。官方 marketplace 有 13 个 `*-lsp` 插件，没有 Dart [L8]。
- 语义检索都要另装：Serena [126]；ast-grep MCP，依赖 ast-grep CLI，本机没有 [155]；GitNexus，analyze 时会写 CLAUDE.md 和 hooks，许可是 PolyForm Noncommercial [156]。核查员还补充了三个：官方 marketplace 里的本地语义检索 MCP Lumen，需要 Milvus/Zilliz 和 OpenAI key 的 Claude Context，提供 `/sonarqube:sonar-duplication` 的 SonarQube agent plugins（均未核验）[157][158][159]。Sourcegraph 插件能跨仓库检索，但要有开启 MCP 的实例和 token [160]。

**子代理和工作流**

- Explore 是只读的，启动时不加载 CLAUDE.md；默认最多 20 个子代理并发，嵌套深度 3 [132]。Workflow 运行中不能接收用户输入 [133]。Cartographer 按 token 预算把仓库拆给多个并行的 Sonnet 子代理 [163]。
- 非 fork 子代理拿不到 AskUserQuestion。对话 fork（`/subtask`，或默认开启的 fork 模式）保留主会话的工具，包括 AskUserQuestion；`context: fork` 的 skill 启动的是非 fork 子代理，同样没有这个工具。所以确认步骤必须在主会话里运行 [129][132]。
- 任务工具只在 Opus 4.7、Sonnet 4.6、Haiku 4.5 及更早的模型上默认开启 [131]，ledger 不能依赖它。

**确认和持久化**

- AskUserQuestion 的问题会一直等待，除非设置了 askUserQuestionTimeout，超时后 Claude 按自己的判断继续；plan approval 不会因为空闲自动通过 [131]。
- 内置命令都在范围已知时工作：`/batch` 把工作拆成 5 到 30 个单元，`/simplify` 和 `/code-review` 审查 diff [134]。确认后的清单可以交给 `/batch` 执行。
- `.claude/rules` 下带 `paths` frontmatter 的规则文件，会在 Claude 读或改匹配的文件时加载 [135]。Kiro 的 steering 有 fileMatch 方式 [164]。Spec Kit 的 `/analyze` 是只读的，最多报 50 条，重跑时要求 ID 不变 [165]。

**已有的影响分析类 skill**

- cursor 的 blast-radius 在 grep 停下的地方继续找（API JSON、DB 列），证据按 1-5 分级，没有确认门 [161]。impact-map 在改动前出一份只读报告，覆盖命名变体、重复逻辑和 git co-change；遇到需要决定的发现会停下，进入计划前要用户明确同意 [162]。两者都没有"每个推断出的耦合都要等确认"的规则，也没有改后的残留检查。
- code-modernization 插件的 extract-rules 工作流按轮次循环，一轮新增少于 3 条或少于 15% 时停止；每条新规则派一个引用核查员，未核实的规则不会显示为已确认；第 215 行明确禁止按源码中像指令的文字行事 [L9]。这三条做法都可以直接借用。
- 用 `impact|refactor|duplicat|rename|propagat|blast|symbol|clone|references` 匹配官方 marketplace 315 个插件的名字和描述，命中 10 个，没有一个检查改动范围是否完整 [L8]。

## 4 技术手段目录

下表按信号来源排列。"适用场景"一列用 1.3 节的类型代号。

| 手段 | 机制 | 召回与精度特点 | 成本和依赖 | 适用场景 |
|---|---|---|---|---|
| LSP 引用、实现、调用层级 | findReferences、goToImplementation、incomingCalls [115][131] | 结构依赖上 precision 高，结果可以当证明；找不到规则耦合；pyright 没有 goToImplementation | 要装插件和 server；Dart 没有官方插件；云端会话不可用 | A；S1 中的签名和字段改动 |
| 改动类型→关系表加 worklist | 每次编辑按类型产生待办，类型检查作判定，迭代到不动点 [41] | 机械连带找得全；只改行为的修改不报错，会漏 | 需要能运行的类型检查或构建 | A、H |
| 词法检索加别名扩展 | 领域词的中英文、缩写和同义词，旧值和它的上下文（基线试验中 Agent 自己用过的做法 [L1]） | 单个词 80-90% 的情况找不到，加别名后命中提高几倍 [111]；噪声大，必须分档 | git grep 或 grep，几乎没有成本；超大正则可能被 ugrep 拒绝（未核验） | S1、S2 的起点 |
| 规则载体抽取 | 从编辑点抽出常量、配置键、校验器名、路由、错误和 i18n key，跨前后端、文档、测试检索（自核） | zulip 的 `password_min_length` 落在 15 个文件里（注册、重置、改密码、设置），搜 "password" 是 222 个；gitea 的 `MinPasswordLength`/`IsComplexEnough` 是 11 对 170。比共享字面量更能连起镜像校验（自核） | grep，秒级 | B、C（S1） |
| 声明式耦合解析 | 正向：读编辑附近的 "keep in sync"、"if you change X also update Y"、LINT.IfChange/ThenChange；反向：grep 被改的路径、文件名和符号，只留含 sync、mirror、same、match、also、update、copied 的行（自核） | 6 个 OSS 仓库（48,447 个文件）都有，几乎全是自由文本，LINT.IfChange 0 处；sync/update 措辞 precision 60-65%，match/mirror 25-40%；每千个文件约 8 个真实耦合；56% 只有单向指针（自核） | 反向查找 0.3-1.1 秒；有 IFTTT 指令的仓库可以跑 ifttt-lint [106] | B、D；"copied from" 可作 S3 种子 |
| 契约抽取器 | 每个技术栈一个脚本，抽取路由、operationId、i18n 和配置 key、表名、CSS 类、测试名 | 证据直接；TCTracer 类级 P 100%、R 80%，方法级 R 11%；Wittern 对照 API 规范检查请求，precision 96% [101][102] | 每个栈要写一份 | C |
| patch-as-query（以编辑为查询） | 用第一处 Edit 的 old_string/new_string 抽出标识符、子词和被删的字面量，检索仍匹配旧写法的位置，循环到没有新位置 [43][44] | 回放 9 次基线运行：T1 7/7，T3 5/5（还带出了被排除的 `useCountdown.ts`）；T2 的第一次写入是新建 CSS 文件，3 次中 2 次为 0/8 [L3]（自核）；10 万文件下的 precision 未测 | 脚本，无依赖；放进 hook 要配缓存索引 | S1、S3；S2 要补类别词和结构特征 |
| co-change 挖掘 | 从 git 历史挖关联规则，TARMAQ 用查询集合中最大的重叠子集匹配；学习时只用改动不超过 6-8 个文件的提交，每次运行重新计算 [86][87] | 宽松阈值的 precision 约 29%，严格警告很少触发但约 2/3 正确 [18]；本地留一法 hit@10 为 0.49-0.78 [L5]，真实遗漏上 Hit@10 只有 0.15-0.42 [91]；能找出没有 import 或引用关系的跨语言伙伴和平行实现 [19] | stdlib Python，加载 0.1-1.5 秒；要有完整历史，blobless 克隆可以，shallow 克隆不行 [L5] | B、C、D；S3 的平行实现 |
| 提交文本融合 | co-change 加上提交信息和 diff 标识符的 TF-IDF [91]，或对历史提交做 BM25 [47]；skill 可把任务描述与提交文本的相似度和 co-change 用 RRF（K=60）融合 | GitCF 的 Hit@10 为 0.40-0.42，参数是在测试数据上选的；RepoMem 在提交少于 1 万的仓库上下降 13.1 pp | 只需要 git log；squash 过或稀疏的历史要降权 | S1，尤其是 prompt 只有自然语言描述时 |
| 示例归纳的结构 pattern | 从 2 个以上已确认的位置构造 ast-grep pattern：相同的 token 保留字面，不同的写成 `$VAR`，加一行上下文 [1][117] | 示例多样时 precision 高（LASE P 99%、R 89%）；只有 1 个具体示例时 R 60%，名字全部抽象时 P 75% [1]；泛化后命中可能成倍增加 [3]；写法不同的变体要靠各语言的等价写法表或 LLM 生成的变体 [4][62] | ast-grep 本机没有，下载前要问用户 [L10]；Semgrep 可以按类型收窄 [118] | E、F（S2、S3） |
| 结构属性检索 | 按属性定义类别：从 2-3 个已确认示例收集标识符、基类、props、import、样式、装饰器，扩展别名，每个命中记下查询，查询不再带来新命中时停 [111][112] | 不依赖名字；基线试验 T2 中 Agent 自己用过 `createPortal`、`position: fixed`、`z-index` 等结构特征 [L1]；类别边界（Drawer、Toast 算不算弹窗）要用户决定 | grep 或 ast-grep | E（S2） |
| 克隆检测 | 规范化 token 或 AST 后比较：jscpd 依次跑 exact、改名、similarity 三遍，或 PMD CPD；没有工具时用 stdlib difflib 做种子查询 [32][33][L6] | Type-1/2 和相似度 0.7 以上的 Type-3 找得到，MT3 不超过 12%，WT3/T4 不超过 1% [24]；随机函数对的 p99.9 为 0.64，可以 0.8 作确认线、0.7 作列出线 [L6]；不一致的克隆组只有 28% 是无意的 [21] | jscpd 要 npx，本机安装被拒；PMD 要 JVM；种子查询 7.2 秒，全仓两两比较 140-160 秒 [L6] | F（S3） |
| 改后相似检查 | 列出与改动 hunk 相似但没改的代码：ICCheck（逐行字符 bigram Dice 0.7），或把改前的函数体当作 1 对 N 查询重放 [38][L6] | ICCheck 在 CBCD 上 P 0.70、R 0.23；结果为空什么也证明不了 | ICCheck 是 Go 二进制，中位耗时 0.27 秒 | F、I；S1 的镜像实现 |
| 残留检查 | 改完后重跑全部召回查询并对比命中：每个旧命中要么已改，要么消失，要么标为有意保留；Critics 式查找仍匹配旧模板的代码 [9][113] | Critics 的用户研究中 12 人有 11 人找全了漏改；S3 中要求旧函数体已删除或改为委托，拒绝外加 guard [76] | 复用召回脚本，几乎没有额外成本 | I；所有场景的收尾 |
| JIT 过时注释检测 | 每次编辑后，列出含有被删除或被替换 token 的注释和文档行 [109] | 论文模型 F1 87.1；只按"与被删代码共享 token"标记也有 74.7；事后检测的模型只有 53.9-67.9 | 脚本，无依赖 | G；S1 中写明约束的文档行（T1 被改掉的那句话） |
| 就近扫描 | 先扫同一文件，再扫同一 package，检查 else/null 分支、相邻枚举值、重载、兄弟子类 [15][14][16] | 补充修改有 42-48% 在首个补丁 25 行以内，70-94% 的重复修复组在同一文件里 | 读文件，成本低 | H；D 中的同文件副本 |
| 外围产物固定清单 | 每次都扫文档、配置、测试、fixture、mock、i18n、迁移脚本 [51][68] | 失败运行漏掉的正是这些；文档类 gold 文件 73% 被漏 | grep 加路径规则 | G |
| Embedding 语义检索 | 向量检索，或与 grep 合用 [124][125] | 提高的是 precision，不是 recall（文件级 recall 49%→39%）；用 LLM 过滤会丢真阳性 [99] | 要另装 MCP 或模型（jscpd `--semantic` 的本地模型 548 MB）[32] | F 中只是行为相似的候选，只列不改 |
| 多次枚举取并集再核实 | 2-3 次独立枚举取并集，逐项核实，弱候选降档 [57] | 取交集损失 13-21 pp，由 LLM 挑选提高 3.3-12.5 pp，4-5 次调用后饱和 | 每次枚举都花 token | B、C（S1） |
| 按模块扇出只读子代理 | 每个子系统或目录派一个 Explore，返回 path:line 和证据 [68][132] | 同为 Haiku，扇出后找全的实例从 3.3/19 升到 6.4/19，单个更强的 agent 是 9.2/19。评审另提到 RefactorPlatform 中委派的成功率 66%、检索 86%，每次空启动写入 54,154 个 cache token（未核验） | 每个子代理都有启动成本；Explore 不加载 CLAUDE.md，也没有 AskUserQuestion | E、F 在大仓库中的广度扫描 |
| 不变式复述加一次提问 | 搜索前把请求改写成不变式（"A 和 B 必须在 Z 上一致"），按不变式找候选，探索之后一次性问用户 [69][73][74] | 得到回答后 Sonnet 4 恢复了完整规格下 89% 的结果；问行为的问题有用，能从代码查到答案的问题没用；CLARITI 问 3.0 个问题，效果与 GPT-5 问 5.1 个相当 | 一次 AskUserQuestion：1-4 个问题，每个 2-4 个选项 [130][131] | B、C（S1） |
| 已确认耦合的持久化 | 确认后把耦合存成锚点（路径、符号、短锚文本），读取时重新解析；或写成带 `paths` 的 `.claude/rules` 文件 [12][135] | CloneTracker 的锚点正确追踪了 96% 的区域。指针路径很少失效，所指内容却会漂移：44 个仓库内指针 0 个失效，但 zulip 一条注释点名的两个文件里已经没有那个值（自核）[L11] | 写进仓库，要用户同意 | B、C、D 的下一次改动 |

没有一种手段能单独覆盖三个场景。LSP 和类型检查只证明 A 类；词法、结构和克隆信号覆盖 S2、S3，但只能推断；S1 的规则耦合主要靠规则载体、声明式耦合、co-change 和提问。所以第 8 节的设计取多个通道的并集，按证据强度分档，embedding 和 LLM 判定只用来排序或列出，不用来删掉候选。

## 5 现有方案的空白与本 skill 的定位

### 5.1 空白

| 空白 | 证据 | 本 skill 的对策 |
|---|---|---|
| 发现阶段的 recall 没人测过，S1 尤其如此 | Google LSC 和 2025 年的 LLM 迁移都没有公布发现阶段的 recall [113][61]（核查员补充的姊妹篇见 [114]，未核验）；没有研究在真实代码里测过 S1 耦合的召回；AgentPack 的 180 万条 agent 提交中 Claude Code 的中位改动是 2 个文件，日志里看不到遗漏（未核验） | 自建播种漏改的评测（第 7 节） |
| 经典工具的前提大多不成立 | 要 2 个以上有差异的示例、改动同形、单一语言；只有 7-17% 的补充补丁与首个补丁相似 [13] | 示例 pattern 只作为一个通道；S1 靠规则载体和用户确认 |
| 现有工具在范围已知之后才工作 | `/batch`、`/simplify`、`/code-review` 处理已知的范围或 diff [134]；Google LSC 的候选来自索引 [113]；impact 类 skill 分析的是已知改动会影响什么 [161][162] | 在编辑前后确定范围；确认后的清单可以交给 `/batch` |
| 推断出的耦合没有逐项确认 | blast-radius 没有确认门 [161]；impact-map 进入计划前要一次同意，但没有"每个推断耦合都等确认"的规则 [162]；T1 的 3 次中 2 次没问就改了 [L1]；auto 模式不限制范围，工作目录内的编辑在分类器之前就被批准 [145]（自核） | 分档确认门（决定 c） |
| 改完没有残留检查 | 两个 impact 类 skill 都没有 [161][162]；测试通过时仍可能漏改 [78] | 改后重跑召回查询，以 ledger 判断完成 |
| 长任务里状态丢失 | 给 Agent 编辑状态摘要后相对提升 43.9% [52]；SKILL.md 不会重读，压缩后只回填前 5,000 token [129] | 状态存在磁盘上的 ledger 里，由脚本维护 |
| 自动触发不可靠 | 无 hook 时激活率 50-55%，间接表述约 0% [167]；Vercel 评测中 56% 的情况从未调用 [168]（均为自核） | 改写 description；hooks 作为可选扩展 |
| 有工具也不用 | JetBrains 第一次实验零调用 [122]；基线试验中 LSP 调用为 0 [L2] | 写明每类改动调用哪个工具、何时调用 |
| 跨仓库 | ifttt-lint 只在一个仓库内链接文件（自核）[106]；Sourcegraph 要有实例和 token [160] | 工作区声明，方案未定（第 9 节） |

### 5.2 定位

本 skill 是一个编排层。它不新造检索引擎，也不取代 LSP、ast-grep、jscpd，而是规定：什么改动用哪些信号，证据怎样记录，哪些位置要等用户确认，什么条件下才算完成。

它工作在两个时点。编辑前，从 prompt 或 plan 的一步出发枚举范围。编辑中和编辑后，用首个编辑当查询补漏，最后做残留检查。

收益来源随规模变化。40 个文件的样例仓库里，不装 skill 的 Opus 5.5 已经能找全，skill 的作用主要是让范围决策符合决定 (c) [L1]。到 1 万个文件以上或跨仓库时，Agent 读不完代码，检索通道才成为主要收益（评审意见）。

不做的事：

- 不替用户安装插件、language server 或 npm/PyPI 包，只给建议；下载前先问 [L10]。
- 不往 settings 写权限规则（自核）。
- 默认不往用户代码里写耦合注释或 IFTTT 指令。仓库已经在用这类写法时才考虑，因为你的全局约定不鼓励引入新模式。
- 不打包 MCP 服务器；环境里有 Serena 等工具就用，命中要读代码核实 [126]。
- 推断出的位置未经确认不改。

## 6 Claude Code skill 规范要点

规范分两层：agentskills.io 的可移植规范定格式，code.claude.com 的文档定 Claude Code 的运行行为。格式按最严的一条执行；运行行为以 Claude Code 文档和 2.1.309 的实际表现为准。

### 6.1 位置与打包

```text
change-propagation/                     插件仓库根目录
├── .claude-plugin/plugin.json          只有 name 必填
├── skills/change-propagation/
│   ├── SKILL.md
│   ├── scripts/                        只读检索脚本（stdlib Python）
│   └── references/stacks/<stack>.md    各技术栈的做法（决定 b）
├── hooks/hooks.json                    可选，属于决定 (d) 的扩展
├── README.md
└── LICENSE
```

- plugin.json 只有 `name` 必填。以 `claude-`、`anthropic-`、`cc-plugin-` 开头的名字会失败，这一点调研时验证过 [141]。
- 设了 `version`，用户会停在这个版本，直到你升版本号；不设则按 commit SHA 更新 [141]。发布时升版本号，再运行 `claude plugin tag` [140]。
- 插件根目录的 CLAUDE.md 不会被加载 [142]，规则只能写在 SKILL.md 和 references 里。
- `${CLAUDE_PLUGIN_DATA}`（`~/.claude/plugins/data/<id>/`）在插件更新后保留 [141][144]，可以放 hook 用的缓存索引；工具调用不要往里写（6.6 节）。
- 开发时用 `claude --plugin-dir <仓库路径>`，它的优先级高于已安装的插件和 skills 目录里的副本 [142]。
- 插件 skill 的命令是 `/change-propagation:change-propagation`；设了 `name` 且没有重名时，`/change-propagation` 也能用 [129]。决定 (d) 的手动触发两种写法都要写进 README。

### 6.2 SKILL.md frontmatter

| 字段 | 规则 | 本 skill 的取值 |
|---|---|---|
| `name` | 必填；1-64 个字符，只能用 a-z、0-9 和不在首尾、不连续的连字符；必须与目录名相同 [138]。platform 文档还禁止 XML 标签和 "claude"、"anthropic" 字样 [139] | `change-propagation` |
| `description` | 必填，1-1024 个字符 [138]；Claude Code 列表中它与 `when_to_use` 合计超过 1,536 个字符的部分被截掉 [129] | 第三人称，先写触发情境，带 "Use when"，中英双语，不用尖括号 |
| `license`、`compatibility`、`metadata` | 可选；`compatibility` 不超过 500 个字符，`metadata` 是字符串映射 [138] | 按需 |
| `allowed-tools` | 可选，规范中标为实验性；写成一个空格分隔的字符串 [138] | 每个脚本一条固定路径的 Bash 规则（6.6 节） |
| Claude Code 专有字段 | `when_to_use`、`argument-hint`、`arguments`、`disable-model-invocation`（true 时隐藏 description）、`user-invocable`、`disallowed-tools`、`model`、`effort`、`context`、`agent`、`background`、`hooks`、`paths`、`shell`，共 14 个。Claude Code 中所有字段都可选，未知键被忽略 [129]；claude.ai 和 Skills API 拒绝规范以外的键 [138] | 加 `argument-hint`；不设 `disable-model-invocation`、`user-invocable`、`model`、`paths`；不用 `context: fork` |

- 不设 `paths`：它要等 Claude 读到匹配的文件才加载，对 plan 中的一步（S2）来说太晚 [129]。
- 不用 `context: fork`：它把正文交给一个没有对话历史的新子代理，默认在后台运行，工具更少，编辑不进 checkpoint，也没有 AskUserQuestion [129][132]。确认门需要原始请求和 AskUserQuestion，只能在主会话里跑；只读的召回扫描可以交给插件 agent 或 Explore，让它返回 file:line 和证据。
- `version` 写在 plugin.json 里，不写进 SKILL.md。

### 6.3 长度与上下文

- skill 列表总共占上下文的 1%，超出时最少被调用的 skill 先丢掉 description [129]。新装的 skill 正好是最少被调用的。
- SKILL.md 在会话中不会被重读。上下文压缩后只回填它的前 5,000 token，所有 skill 共用 25,000 token [129]。
- 正文不超过 500 行；references 只引用一层；超过 100 行的参考文件加目录。批量编辑建议走"计划、校验、执行"，计划文件由脚本校验 [139]。
- 对本 skill 的要求：分档规则、ledger 格式和停止条件放在正文最前面；各技术栈的配方放进 `references/stacks/<stack>.md`；ledger 本身就是那份由脚本校验的计划文件。

### 6.4 调用、脚本注入与 hooks

- `${CLAUDE_SKILL_DIR}` 在正文和 `allowed-tools` 的 Bash 规则里都会展开 [129]。脚本统一用 `${CLAUDE_SKILL_DIR}/scripts/...` 调用，并配一条对应的 `Bash()` 规则。
- 正文里的 `` !`cmd` `` 注入有个陷阱：命令失败（搜索和 diff 类命令允许 exit 1）或没有预先放行时，整个 skill 调用会中止 [129]。要么不用注入，要么逐条放行并在末尾加 `|| true`。
- hooks 可以写在三个地方，生效范围不同：
  - SKILL.md frontmatter 里的 hooks 从 skill 被调用时开始生效，持续到会话结束 [129]，所以不能用来触发 skill 本身（自核）。
  - 插件的 `hooks/hooks.json` 从会话加载时就生效，在子代理里也会触发，输入里带 `agent_id` [130][143]（自核）。
  - 插件 agent 定义里的 hooks 会被忽略 [129]。
- command hook 在权限系统之外运行，带着用户的全部权限，任何模式下都会执行 [130]（自核）。所以 hook 脚本要只读、离线、有时间上限，不下载 npx 包。
- 与本 skill 相关的事件行为 [130]：
  - Stop 的输入带 `stop_hook_active`。返回 `decision: block` 加理由会让本轮继续，最多连续 8 次，之后 Claude Code 结束本轮。
  - PostToolUse 匹配 `Edit|Write` 时看不到通过 Bash 做的修改，所以改动范围要从 `git diff` 读。
  - 用户输入 `/skill` 时触发 UserPromptExpansion，Claude 自己调用 skill 时触发 PreToolUse(Skill)。PreToolUse 的输入带 `permission_mode`，不是每个事件都带（自核）。
  - PreToolUse 返回 `ask` 时走权限提示，不经过 auto 模式的分类器；在 `-p` 中 Claude 能读到 deny 的理由 [130][145]（自核）。
- skills 文档建议把必须成立的规则放进 hook，这样"whether or not Claude is following the skill"规则都会执行 [129]。

### 6.5 hook 的时间和输出预算

- additionalContext 和 stdout 上限 10,000 个字符，超出时 Claude 只拿到一个文件路径和 2,000 个字符的预览 [130]。UserPromptSubmit 默认 30 秒超时 [130]。
- 本地测量 [L4]（自核）：10 万个文件上 rg 一次要 2-4 秒，建索引约 50 秒（评审提到 9.9 万个文件上 contract_map 和 shingle 的构建用了 50-53 秒）；一个 `python3 -I` 空 hook 的中位耗时 63.2 毫秒；按本轮调研会话的 279 次 Edit/Write 计算，每次都跑一遍 rg 会多花 9-19 分钟。这些数字都是用 rg 测的，git grep 在 10 万个文件上的速度没有测过（评审，未核验）。
- 异步 hook 在 `-p` 进程结束时会被终止 [137]（自核）。
- 由此得出的做法：先按扩展名和新出现的标识符过滤；查询 `${CLAUDE_PLUGIN_DATA}` 里预建的索引，时间上限 2-3 秒；SessionStart 时在后台重建索引；用 stdlib Python 实现，回退到 git grep（rg 在这台机器上只是 Claude 的 shell 函数 [L10]）；注入不超过 2,000 个字符，完整清单写进 ledger。

### 6.6 权限模式

每种模式影响 skill 的不同环节（本节都来自 gap-3，自核；[L12] 是对 2.1.309 二进制的检查）。

| 模式 | 对 skill 的影响 | 对策 |
|---|---|---|
| auto | 解释器通配的 allow 规则会被丢弃：`Bash(*)`、裸解释器、`<interp> *`、`<interp>:*`、`<interp>*`、`<interp> -..*`，涉及 python、python3、node、npx、bash、sh、env、xargs 等（`python -m pkg.mod` 例外）。文档示例 `Bash(python3 *)` 同样被丢弃；`python3 /abs/x.py *` 会保留，这类调用跳过分类器。user 或 managed 设置了 classifyAllShell 时，所有 shell 规则都失效 [146][L12]。skill 授予的权限在"you send your next message"时清除 [129]。工作目录内的编辑在分类器之前就被批准；分类器对真实越界操作的漏判率 17%（n=52），误报率 0.4%（n=10,000）；连续 3 次或累计 20 次拦截会暂停 auto 模式 [145][147] | 每个脚本一条 `Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/<name>.py *)`。执行的命令与规则逐字一致：不加引号，不用 `cd &&`，不用 `>` 重定向。确认门放在同一轮里的 AskUserQuestion，或在 `/change-propagation:apply` 这类 skill 里重新授权。不写 settings。auto 模式的系统提醒说 skill 要求时才提问，所以 SKILL.md 要写明这个门是必需的 |
| plan | 只有计划文件可写，其他写入返回 "Cannot write to X while in plan mode"。plan 提示禁止非只读工具，并覆盖其他指令；Phase 4 要求"list a few representative paths"；子代理也处在 plan 模式；接受计划时如果清空上下文，计划文件是唯一的交接物 [145][132][146]。评审在 permission-modes 页面核对过：auto 模式可用时（默认如此），plan 模式下的 shell 命令由分类器审查，否则只读集合以外的命令都要提示 | 第 0 层脚本只读，只输出到 stdout。计划文件里加一个必需的 ledger 附录（完整分档清单，或第 0 层查询加计数），并注明它优先于"只列代表性路径"。计划批准后再写 ledger.json |
| `-p` | 以 Manual 模式启动，拒绝没有批准的调用（评审核对）。只有存在权限宿主（canUseTool、`--permission-prompt-tool`，或返回 allow 加 `updatedInput.answers` 的 hook）时才提供 AskUserQuestion [130] | 没有 AskUserQuestion 时，2 档一律标为待确认，不编辑 |
| dontAsk | plugin eval 的每次运行都是这个模式。AskUserQuestion 被拒，拒绝信息让 Claude 停下来说明原因 [137][L12] | 评测拆成门前、门后两类用例（7.4 节） |

- **受保护路径。** `.claude`（项目内和 `~/.claude`）以及 `--plugin-dir` 受保护：default 模式下弹提示，auto 模式下交给分类器，dontAsk 下直接拒绝 [145]。auto 模式只自动批准工作目录内的编辑。所以 ledger 写在 `<项目>/.change-propagation/ledger.json`，目录里放一个内容为 `*` 的 `.gitignore`；工具调用不写 `.claude/`，也不写 `${CLAUDE_PLUGIN_DATA}`。
- **AskUserQuestion 的范围** [130][131][132]。交互会话（包括 auto 和 plan）里总是真实地提问；所有非 fork 子代理里都没有这个工具。每次 1-4 个问题，每个 2-4 个选项，支持 multiSelect 和自由填写的 Other；超时只提交已经选中的选项。一次调用最多放 16 个可选项，更多的位置要分组。超时或没有选择都算未确认。

### 6.7 校验与评测工具

**`claude plugin validate`。** 本地用 2.1.309 测试 `--strict --json` [L7]：只报出了 YAML 错误、缺少 description 和错误的 shell 取值。下列问题都通过了校验：未知键、大写字母、65 个字符或含双连字符的名字、name 与目录名不同、1,600 个字符的 description、尖括号、错误的 context 或 effort 取值、损坏的 eval 文件。manifest 的检查更严，例如路径要以 `./` 开头，保留名会被拒绝。CLI 参考页列出了 validate 的退出码，以及 `plugin eval`、`eval init`、`tag` 命令 [140]。所以 CI 里要跑三样：`validate --strict`；一个检查规范规则的 lint 脚本（字符集正则、不超过 64 个字符、与目录同名、description 不超过 1024 个字符、没有尖括号）；跑 1 次的 eval 冒烟测试。规范的参考校验器 skills-ref 检查 frontmatter 和命名约定，`claude plugin validate` 不做这些 [150]。

**`claude plugin eval`** [137]：

- 用例结构：`evals/<case>/prompt.md` 加 `graders/*.md`；`case.yaml` 可以设 `context.scaffold_script`，运行时要加 `--scaffold`，限时 120 秒。
- 默认值：每组跑 3 次，max_turns 10，300 秒，阈值 1.0，评判模型 haiku。
- grader 类型：regex、tool_used、tool_order、file_exists、llm、baseline，另有 `{source: file}` 和 `history_file`；没有代码 grader。两组对比时，"是否用了 skill"这类 grader 不计分。
- 运行方式（自核）[L12]：每次运行是 `claude -p --permission-mode dontAsk --setting-sources user`，用临时 home，Bash 在沙箱里，settings 中的 allow 规则被过滤掉。Bash、Write、Edit 要由运行者用 `--allow-tools` 放行，skill 的 `allowed-tools` 不能放宽它。插件 hooks 会运行。
- 它让 platform 指南里"没有内置的评测方式"的说法过时了。

**skill-creator** [151][152][153]：用来调 description 的触发率。流程是 20 个查询（其中 8-10 个是相近但不该触发的反例），迭代 5 轮，训练集和测试集按 60/40 分，每个查询跑 3 次，按测试集得分挑选。run_eval.py 在项目根目录写一个临时的 `.claude/commands` 文件，用用户的完整配置调用 `claude -p`；只有第一个工具调用是 Skill 或读取该 skill 时才算触发，测的是临时命令文件而不是插件（自核）。所以先在临时的 fixture 仓库里调 description，再用 plugin eval 确认，后者隔离了带命名空间的插件 skill。

**其他。** skill-creator 的 evals.json 用 `expectations` 这个键，agentskills.io 用 `assertions` [148]，以 skill-creator 的 schemas.md 为准。agentskills.io 另有 description 优化指南 [149]；官方示例、模板和 skill-creator 源码在 anthropics/skills 仓库 [154]。

## 7 评测方法建议

### 7.1 可借用的基准和数据集

| 基准或数据 | 能测什么 | 注意 |
|---|---|---|
| SWE-bench Lite/Verified/Pro 的定位结果 [49][66] | 文件级、函数级定位 | 可能被模型记住：只给 issue 文本时，Claude 3.5 在 Verified 上 65% 的实例能说出全部 gold 文件，BeetleBox 上是 12.2%（未核验）[65]；不含 S1 耦合 |
| PolyHunk [54]、Hunk4J/Defects4J [56] | 多 hunk 修改是否覆盖全部文件 | PolyHunk 的覆盖指标允许多改 |
| RefactorBench [52]、RefactorPlatform [53]、SWE-Bench ProMax [51]、RepoRescue [55] | 多文件协同修改中的遗漏 | 以测试或检查项判定，看不到"提出但没改" |
| RevPropBench [57] | 对话中逐步搭建的产物里的变更传播 | 不是代码仓库，但"需求历史加产物"的设定最接近 S1 |
| GitCF 的 543 个真实不完整改动 [91] | 真实遗漏上的 Hit@k | 参数是在测试数据上选的 |
| 补充补丁研究的数据 [13][14] | 人类开发者的遗漏基线 | Eclipse、Mozilla，Java/C++ 为主 |
| BigCloneBench [24] | 各类克隆的检测 recall | 抽样的 WT3/T4 对有 93.3% 不是真克隆 [37] |
| CodeTaste [40]、多轮复用研究 [77] | S3 的重复发现和复用 | |
| SWE-RPG [69]、DevIntent [70]、FixedBench [71] | 需求覆盖、意图违背、不需要改时是否不改 | |
| AIDev 的 agent PR 数据 [169]（未核验） | 从评审评论里挖"漏改了 X"，构造真实用例 | 评审提及，没有核对 |

这些基准都没有测 S1 耦合在真实代码里的召回，所以要自建播种漏改的评测。

### 7.2 Fixture 仓库

- **冒烟测试。** 沿用基线试验的 shopfront（40 个文件、T1-T3、gt.json、grade.py）[L1]。它在小规模上已经能复现 S1 的范围决策问题。
- **规模测试。** 把同类陷阱植入真实的大型 OSS 仓库。gap-2 扫描过的仓库里已有现成的 S1 素材：zulip 的 `password_min_length` 分布在 15 个文件里，gitea 有 `MinPasswordLength`/`IsComplexEnough`，mattermost 有跨语言的 "Keep in sync" 指针 [L11]（自核）。
- **真实遗漏。** 从仓库历史里找"forgot to update"一类的后续提交，按仓库建用例；co-change 的留一法可以同时用来标定阈值 [L5]。
- **要覆盖的条件**（来自基线试验的结论 [L1]）：仓库大到读不完、只能靠检索；关联位置没有共同的词或结构，比如同一规则的另一种写法、配置文件、另一个仓库；更弱的模型或更低的 effort；长会话后期；先计划后执行。另加中文的单对象 prompt，以及相近但不该触发的反例，例如 "rename this local variable"、"animate this one button"。
- **按技术栈扩充。** 每个技术栈一套用例，按决定 (b) 的顺序逐个加。
- **盲测纪律** [L1]。运行期间把 gt.json 移到 Agent 看不到的位置；副本放在看不出用途的路径下；不要用 Workflow 启动执行者，因为它会把触发它的对话原文转给子代理。

### 7.3 指标

| 指标 | 定义 | 理由 |
|---|---|---|
| 分档的 location recall 和 precision | 按 gt.json 的 direct、coupled、review、exclude 四档逐个位置判定：edited、mentioned 或 missed [L1] | 主指标；"列出没改"也要计入 |
| 未经确认的编辑 | coupled 位置在用户确认前被编辑的次数；写明约束的文档行被改写的次数 | T1-c2、T1-c3 的失败正是这一类 [L1] |
| ledger 处置完整率 | 没有处置（已改、用户跳过、仅列出）的 ledger 条目数 | 判断能否结束 |
| 残留数 | 改后重跑查询仍然命中旧写法、又没有标为有意保留的位置数 | 对应 1.3 节的 I 类 [9] |
| 2 档 precision 和确认负担 | 2 档中被用户确认的比例；每次修复要用户看的条目数和问题数 | 一次修复可能推断出几十个位置（评审） |
| 触发率 | Skill 是否被调用、在第几步调用；反例中的误触发 [137] | 2.10 节 |
| 成本 | token、工具调用数、耗时，以及 hook 增加的延迟 | 基线试验中 T2 的成本是 T1 的 2-3 倍 [L1] |

### 7.4 对照设计

- **分组**（自核）：不装插件的基线；只靠 description；加 UserPromptSubmit；再加 PostToolUse 和 Stop [137]。plugin eval 默认每组 3 次。基线试验中 3 次已经能看出 T1 的分歧 [L1]，但要比较组间差异，次数要更多。
- **确认门拆成两类用例**，因为 dontAsk 下 AskUserQuestion 被拒（自核）：
  - 门前：断言最后一条消息列出了 2 档条目，并用 `tool_used` Edit 加 `input_match <2 档路径>`、`min 0 max 0` 断言它们没被编辑。
  - 门后：用 `history_file` 回放一个已经展示过确认门的会话，以用户的确认作为 prompt，断言确认过的位置被编辑。ledger.json 用 `{source: file}` 打分。
- **召回打分。** 每个应改的文件配一个 `tool_used` Edit grader，因为 file_exists 看不到编辑；相似对象的路径用 regex 匹配最后一条消息；决定 (c) 的处置用 llm grader 判断 [137]。
- **反例。** 对 Skill 用 `tool_used` 的 `min 0 max 0`，`arm: both`。
- **准备工作。** 在 scaffold_script 里预建索引（120 秒以内），运行时加 `--scaffold --allow-tools Edit Write`。description 先用 skill-creator 调，再用 plugin eval 确认（6.7 节）。

## 8 对 skill 设计的启示

### 8.1 设计原则

1. **先确定不变式，再找位置。** 搜索前把请求改写成不变式，例如"注册和重置密码的最小长度必须一致"，按不变式找候选，让用户确认不变式本身，而不只是一个个位置 [69][70]。除了代码，也要读 prompt、PRD、工单这些需求历史 [57]。
2. **多个通道取并集，按轮次扩展。** 通道按改动类型选（第 4 节）：A 类走 LSP 和类型检查 worklist [41][42]；S1 走规则载体和声明式耦合（自核）[L11]、契约抽取 [101][102] 和 co-change [86]；S2 走别名、结构属性和示例 pattern [1][111][112]；S3 走克隆检测和行为特征 [24][32]。第一处编辑之后，再用 patch-as-query 补一轮 [43][L3]。每个命中记下产生它的查询。只从真正改了的节点继续传播，没改的节点记为边界 [94]；一轮新增少于 3 个候选时停止 [L9]。外围产物（文档、配置、测试、fixture、mock、i18n）每次按固定清单扫 [51][68]。
3. **声明式耦合要正反两个方向查。** 正向读编辑附近的注释；反向用被改的路径、文件名和符号去找指向它们的注释。实测 56% 的耦合对只有单向指针，反向查找耗时 0.3-1.1 秒（自核）[L11]。路径按完整路径、后缀、文件名的顺序解析，只靠文件名对上的标为"可能已移动"；目标处已经没有那个值或符号的，作为过时项交给用户确认（自核）[L11]。Fraco 发现重命名后超过一半的标识符带有易失效的注释 [108]。仓库里有 IFTTT 指令（`LINT.IfChange(label)` … `LINT.ThenChange(//path:label)`）时，改完运行它自己的 linter [105][106][107]。
4. **分档看改动类型和证据，不看通道。**
   - 1 档（直接改）：prompt 点名的对象；被 LSP 或类型检查证明的 A 类连带修改 [42]；IFTTT 块的 ThenChange 目标，以及位于被改 hunk 内或正上方、目标能解析的耦合注释（自核）[L11]。
   - 2 档（带证据确认后改）：规则载体和契约的命中；co-change 强规则；示例 pattern 的命中；克隆。克隆即使是 Type-1 也最多进 2 档，因为不一致的克隆组里只有 28% 是无意的 [21]。Type-3 克隆按 [24] 的分法取相似度 0.7 以上；用 stdlib difflib 兜底时，比值 0.8 以上进 2 档（自核）[L6]。A 类以外的改动，LSP 一跳邻居要有第二个信号同意才进 2 档 [15]。
   - 3 档（只列不改）：相似度 0.5-0.7 的克隆和所有 Type-4 [24]（difflib 兜底时为 0.7-0.8，且不能凭 token 分数断言 Type-4 [L6]）；只有单一信号的一跳邻居；embedding 命中 [124]；被 LLM 否决的候选，附理由 [99]；Google 式距离 5 的超集 [61]。
   - embedding 和廉价模型的初筛只用来排序，不删候选。评审称 LLM 过滤会丢掉 12-41% 的真阳性（未核验）；LiSSA 中只做检索时 recall 最高，加 LLM 过滤后 recall 下降 [99]。
   - 放宽 pattern 之前先估算命中数，命中成倍增加时先问用户。REFAZER 在 Roslyn 上从开发者改过的 26 处推出了另外 689 处，经确认都该改；但在 17% 的场景里多推出的编辑是错的 [3]。倍数阈值暂取 5 倍，是建议值，没有实测。
5. **确认门问一次，问清楚。** 探索之后、编辑之前，在主会话里问一次 [73]。问题按不变式或代码形状分组，离群的先给 [10]；每组带推荐选项、证据和示例 diff。优先问行为，能从代码查到答案的不问 [73]。问得少不一定差：CLARITI 问 3.0 个问题，效果与 GPT-5 问 5.1 个相当 [74]；单独设一个意图 agent，成绩从 61.2% 升到 69.4% [75]。每次调用最多 4 个问题、16 个选项（6.6 节）。超时、没有选择或工具不可用都算未确认，2 档保持待定。被用户否决的位置当作反例，用来收窄 pattern [10]。
6. **不改写记录约束的文档，单侧修改算确认项。** 基线试验 T1-c2、T1-c3 把 API 文档里"重置与注册规则相同"改成了"重置至少 8 位"，等于把一条共用规则拆成两条 [L1]。WAPTEC 测试的 6 个应用全都有服务端校验比客户端弱的参数篡改漏洞 [110]。所以前后端、注册与重置这类镜像校验只改了一侧时，要按层列出规则载体所在的位置，作为确认项（自核）[L11]。每次编辑后，含有被删或被替换 token 的注释和文档行也列为确认项；在 JIT 注释不一致检测上，这条简单规则的 F1 为 74.7，专门模型为 87.1 [109]。
7. **用 ledger 收尾，不以测试通过收尾。** ledger 每行记 file:line、symbol、anchor、tier、disposition、evidence 和产生它的 query，ID 分配后不变 [165]。脚本负责写入，Agent 只改状态。RefactorBench 中约 44% 的检查项对应的文件根本没被编辑，加上状态跟踪后成绩相对提升 43.9% [52]；Anthropic 也观察到 Agent 看到一点进展就"declare the job done" [82]。ledger 放在 `<项目>/.change-propagation/ledger.json`（6.6 节）；plan 模式下先写成计划文件的附录，计划批准后再落盘。1 档还有未完成项，或外围清单没扫完时，不算完成 [51][54]。
8. **改完先查残留，再跑测试。** 顺序如下：
   1. 重跑全部召回查询，旧写法的每个命中都要变成已改、已消失或标为有意保留 [78][79]。Critics 的用户实验里，按旧模板查残留的 12 人中有 11 人找全了漏改，只看 diff 的只有 4 人 [9]。
   2. 用改动前的函数体做 1 对 N 查询，找没有跟着改的相似代码；环境里有 ICCheck 时直接跑 `iccheck --from HEAD --to WORKTREE` [38]。
   3. S3 在动手前先写合并规格：每个重复实现的 file:line 范围，以及删除还是转调。改完确认旧实现已删除或已转调。通过测试的补丁会漏掉开发者 28.3-34.8% 的删除，另有 29.0% 用条件判断保留旧逻辑，这种写法直接拒绝 [76]。
   4. 派一个只读 reviewer 子代理，只给它意图和 ledger [79]。
   5. 最后跑测试和类型检查。22 个错误但看似合理的 SWE-bench 补丁里，一半通过了开发者的全部测试 [78]。
9. **触发以 description 为主。** description 用中英双语，先写触发情境："改一条别处也要一致的规则""所有 X 都要……""统一、抽取、去重"，即使 prompt 只点名了一处 [129][151]。Spence 用 Sonnet 4.5 测了 22 个 prompt：没有 hook 时，标准 prompt 的激活率为 50-55%，间接 prompt 约为 0% [167]。Vercel 的评测中，skill 有 56% 的情况从未被调用 [168]。UserPromptSubmit hook 可作为可选增强。同一作者的测试中，forced-eval 达到 100%/100%，延迟增加 2.0 秒；llm-eval 也是 100%/100%；只提示类型的 hook 为 55%/41%，与不加 hook 相当。在 24 个更难的 prompt 上，forced-eval 为 75%、误触发 0/5，llm-eval 为 67%、误触发 4/5 [166][167]。forced-eval 的文本是命令式的，而 hooks 文档要求注入事实陈述，因为命令式文本可能触发 prompt injection 防御 [130]。
10. **权限按 auto 模式设计。** 脚本只用 Python 3.9 标准库，以固定的绝对路径调用，每个脚本配一条 allow 规则；检索用 git grep，因为 rg 在这台机器上只是 shell 函数，subprocess 调不到；可选工具先用 `command -v` 探测，npx 或 uvx 下载前先问用户 [L10][L12]（6.6 节）。
11. **每个技术栈一份参考文件。** 内容包括改动类型到关系的对照表：改签名查调用方和 override；改字段查使用者、构造器和父类子类；改函数体只在调用方可见的状态变化时查调用方 [41]。还包括等价写法表，例如 `a?.b` 与 `a && a.b`、`if let` 与 `guard let`，从示例推出的 pattern 必须能复现用户自己的改动 [4][5]。
12. **只改已确认的档，"列出未改"也算成功。** Opus 4.8 不会把针对一个对象的指令自动推广到同类对象 [83]，所以 skill 要写明"这一类的每个实例，不只是点名的那个"。另一方面，FixedBench 中 Agent 在 35-65% 不需要改代码的任务里也改了代码；加一条保留指令（不顺手重命名或重构）后，多余的编辑距离从 0.195 降到 0.131，Pass@1 提高 2.3 pp [71][72]。

### 8.2 候选架构（供讨论，未定稿）

三个方向共用同一套核心：SKILL.md 正文、各技术栈的 references、只读的第 0 层脚本（规则载体、声明式耦合、co-change、patch-as-query、残留检查）、ledger 和确认门。区别在于由谁保证这些步骤真的发生。

**A. 只有 skill。** SKILL.md 加 `scripts/`，由 description 自动触发，或由用户输入 `/change-propagation` 手动触发。确认门是同一轮里的 AskUserQuestion。
- 好处：结构最简单，与决策 (a)(d) 完全一致；除了每个脚本的 allow 规则，不需要别的批准；评测只涉及 description 和正文。
- 问题：只靠 description 触发，简单的单对象 prompt 容易漏触发（8.1 第 9 条）；上下文压缩后只回填正文的前 5,000 token（6.3 节）；没有强制手段，Agent 可以跳过确认门直接改。

**B. skill 加被动 hooks（第 0 层）。** 在 A 的基础上，`hooks/hooks.json` 加以下 hook：
- UserPromptSubmit：正则门，1 秒以内，不调用 LLM，不阻塞；命中时注入不超过 500 个字符的事实，并把 prompt 里的类别词存进 ledger [166][167]。
- PostToolUse（`Edit|Write`）：以这次编辑为查询做 patch-as-query，查 `${CLAUDE_PLUGIN_DATA}` 里预建的索引，时间上限 2-3 秒，注入不超过 2,000 个字符，完整清单写进 ledger（6.5 节）[L3][L4]。通过 Bash 做的修改看不到，要另从 `git diff` 读。
- SessionStart：在后台重建索引。
- Stop：ledger 里有候选还没有处置（已改、用户跳过、已列出）时阻止一次；`stop_hook_active` 为真时直接放行 [129][130]。
- PreToolUse（`Edit|Write`，可选）：编辑落在 2 档待确认或 3 档的范围内时返回 ask，在 dontAsk 和 `-p` 下返回带理由的 deny；没有 ledger 时什么也不做 [130][145][147]。
- ledger 按 session_id 加 agent_id 区分，因为插件 hooks 在子代理里也会触发 [130][143]。

好处是触发和收尾不再依赖模型记得做，状态存在磁盘上，跨过上下文压缩依然有效。问题在于：hooks 超出了决策 (d) 原定的"自动加手动"两种触发方式，需要你批准；command hook 带着用户的全部权限运行（6.4 节）；hooks 对召回的实际效果没有测过；S2 的第一次写入常常是新建文件，patch-as-query 要补上 prompt 里的类别词和结构特征 [L3]。

**C. skill 加只读 Explore 扇出。** 在 A 的基础上，大仓库里的 S2、S3 按模块派只读 Explore 子代理，每个返回 path:line 和证据，由主会话合并进 ledger，再统一提问。
- 好处：广度扫描不占满主会话的上下文。
- 问题：扇出能帮弱模型，但赢不了强的单 agent [68]；每个子代理都有启动成本，评审给出的成本数字未核验（第 4 节）；子代理里没有 AskUserQuestion，确认门只能留在主会话（6.6 节）；Explore 不加载 CLAUDE.md。

| 维度 | A 只有 skill | B skill 加被动 hooks | C skill 加 Explore 扇出 |
|---|---|---|---|
| 触发可靠性 | 只靠 description；第三方测得无 hook 时标准 prompt 激活 50-55% [167] | UserPromptSubmit 门可以补上；第三方测得 75-100%（8.1 第 9 条） | 同 A |
| 确认门强度 | 只靠指令 | Stop 阻止一次；PreToolUse 可以把越档编辑变成 ask | 同 A，门留在主会话 |
| 大仓库召回 | 取决于主会话能检索多少 | 每次编辑后自动补查一轮，但要预建索引 | 广度更好，单个候选的深度不变 |
| 成本 | 最低 | 每次 Edit 多一次 hook：空 hook 中位 63.2 毫秒，查询上限 2-3 秒 [L4] | 每个子代理都有启动成本 |
| 权限和批准 | 每个脚本一条 allow 规则 | 另需你批准 hooks；hook 带用户的全部权限 | 同 A |
| 与决策 (a)-(d) | 完全一致 | (a)(b)(c) 一致；(d) 要扩展 | 一致，(a) 已预留子代理 |
| 评测难度 | 低，只测 description 和正文 | 中，每个 hook 要做成可开关的对照组 | 高，要在大仓库上跑，方差大 |

**建议（供讨论）。** v1 以 A 为基础，先把核心流程做对。B 的每个 hook 做成可以单独开关的选项，用 `claude plugin eval` 对比开和不开的效果（7.4 节），再决定默认开哪些；如果只选一个，先试 Stop 门，因为它直接对应决策 (c) 的"先确认再改"，又不依赖检索质量。C 只用于大仓库中的 S2、S3，等有了大仓库的评测数据再决定。

## 9 未决问题

### 9.1 需要你决定的

1. **hooks 是否纳入决策 (d)。** 如果纳入，选哪些事件（8.2 节 B）；Stop 是阻止一次，还是只提醒。
2. **首个技术栈。** 评审称首个技术栈是 Vue（未核验，你没有说过）。Claude Code 没有 Vue 的 LSP 插件，ast-grep 和 Semgrep 都没有 Vue 语言，所以 Vue 只能靠 grep 和脚本（3.5 节）。TS/JS 的工具最全，Dart 最弱，没有官方 LSP 插件。
3. **运行时下载。** ast-grep、jscpd 需要 npx 或 uvx 下载，auto 模式下会被拦截 [L10]。是改成让你预先安装，还是只用 stdlib 兜底；jscpd `--semantic` 的 548 MB 本地模型或 embedding API 是否可以用 [32]。
4. **跨仓库。** 多个前端和后端是否放在同一个工作区；是否用一份 workspace 清单列出兄弟仓库；`--add-dir` 和 `additionalDirectories` 能覆盖到什么程度；plugin eval 的 add_dirs 只给读权限（未核验）；co-change 怎样跨仓库关联提交。
5. **确认过的耦合存在哪里。** 可选的有 `.claude/rules` 文件、仓库里按 path、symbol 和短 anchor 记录的 sidecar 文件 [12]，或者代码注释和 IFTTT 指令 [105]。
6. **测试、生成代码和平台分叉代码默认怎么分档。**
7. **适用范围。** 只支持 Claude Code，还是另出一个只用规范 6 个字段的版本，因为 claude.ai 和 Skills API 拒绝规范以外的键 [138]。
8. **AGV 平台的情况。** 后端用什么技术栈，兄弟仓库是否都在本地。
9. **Dart 怎么接 LSP。** 用 Serena [126]，还是自带一份 `.lsp.json` [136]。

### 9.2 需要实测的

- **检索速度。** git grep 在 10 万个文件上的耗时；ugrep 对复杂正则的限制（6.5 节）。
- **召回和触发。** patch-as-query 在 10 万个文件上的 precision；Opus 在中文单对象 prompt 上的激活率；注入候选清单是否比只靠 description 更有效；Stop 门是否比纯指令更有效。
- **权限行为。** auto 模式下 skill 的 `allowed-tools` 是否也经过二进制里的规则过滤函数 zYn [L12]；用户回答 AskUserQuestion 之后，skill 授予的权限是否已被清除；dontAsk 下由 hook 返回 allow 加 `updatedInput.answers` 来回答 AskUserQuestion 是否可行（6.6 节）；plugin eval 中 `${CLAUDE_PLUGIN_DATA}` 的实际路径。
- **hooks 与子代理。** 子代理里触发的 hook，其 additionalContext 进入谁的上下文。
- **LSP。** Claude Code 是否把 workspaceFolders 传给 pyright，否则引用只覆盖打开过的文件；kotlin-lsp（alpha）在 Gradle 和 Android 项目上的引用质量。
- **分档阈值。** 克隆阈值能否迁移到 UI 组件；每个技术栈 2 档的 precision。
- **co-change。** 文件级还是符号级；squash 提交怎么处理；超过 8 个文件的提交、bot 提交、monorepo 和改名检测的影响 [87][L5]。
- **声明式耦合。** 中文措辞（"保持一致""同步修改"）的 precision，gap-2 只测了英文；gap-2 的人工复核只有 1 人、每类 20 条 [L11]。
- **未核验的文献。** Fluri 的 co-evolution 研究、Wen 等人在 ICPC 2019 的研究，以及 linked editing [11] 的数据，都因检索额度用完而没有核验。
- **确认门容量。** 10 万个文件的仓库里改一处就可能推出几十个 2 档位置，而每次调用最多 16 个选项（6.6 节）。可选做法有按形状分组提问、让用户直接编辑 ledger 文件，或走 plan 审批（只能整份批准）。Tricorder、Infer 这类已部署分析器要求的 precision 下限，可以决定展示多少候选，但没有调研。
- **ast-grep。** `...` 省略写法在 Kotlin、Swift、Dart 中能否表达。

## 参考文献

标（未核验）的条目，链接或数据在调研中没有打开原文核对过。

- [1] LASE：http://www.cs.utexas.edu/users/mckinley/papers/lase-icse-2013.pdf
- [2] Sydit：http://www.cs.utexas.edu/users/mckinley/papers/sydit-pldi-2011.pdf
- [3] https://arxiv.org/abs/1608.09000
- [4] https://homes.cs.aau.dk/~rrh/pubs/eurosys08.pdf
- [5] https://who.paris.inria.fr/Julia.Lawall/andersen_ase08.pdf
- [6] https://www.usenix.org/conference/atc20/presentation/serrano
- [7] https://arxiv.org/abs/1902.06111
- [8] https://web.cs.ucla.edu/~miryung/Publications/icse09-lsdiff.pdf
- [9] http://web.cs.ucla.edu/~miryung/Publications/ICSE2015-Critics.pdf
- [10] https://www.cs.cmu.edu/~rcm/papers/usenix01/usenix01.html
- [11] http://harmonia.cs.berkeley.edu/papers/toomim-linked-editing.pdf
- [12] http://cs.mcgill.ca/~martin/papers/icse2007.pdf
- [13] http://web.cs.ucla.edu/~miryung/Publications/emse2016-supplementary.pdf
- [14] https://web.cs.ucla.edu/~miryung/Publications/msr2012-supplementarypatch.pdf
- [15] http://web.cs.ucla.edu/~miryung/Publications/ase2014-omissionerror.pdf
- [16] https://people.cs.vt.edu/nm8247/publications/ruru-icsme-2017-camera-ready.pdf
- [17] https://lab-design.github.io/papers/ASE-13/ase13.pdf
- [18] https://research.cs.queensu.ca/home/ahmed/home/teaching/CISC880/F11/papers/MSRGuideChange_TSE2005.pdf ；https://doi.org/10.1109/TSE.2005.72
- [19] https://cs.ubc.ca/~rng/psdepository/tse2004.pdf
- [20] https://doi.org/10.1109/ICSM.2004.1357812 （未核验）
- [21] https://arxiv.org/abs/1701.05472
- [22] https://teamscale.com/hubfs/26978363/Publications/2009-clone-detection-beyond-copy-paste.pdf
- [23] https://web.cs.ucla.edu/~miryung/Publications/ICSE2015-RASE.pdf
- [24] https://arxiv.org/html/1512.06448v1
- [25] http://swat.polymtl.ca/~foutsekh/docs/Barbour-JSME.pdf
- [26] https://plg.uwaterloo.ca/~migod/846/papers/fse06-kim.pdf ；https://doi.org/10.1145/1081706.1081737
- [27] http://plg.uwaterloo.ca/~migod/papers/2008/emse08-ClonePatterns.pdf
- [28] https://doi.org/10.1109/TSE.2015.2448531
- [29] https://doi.org/10.1007/s10664-019-09697-7
- [30] https://www.usenix.org/legacy/event/osdi04/tech/full_papers/li_z/li_z.pdf
- [31] https://doi.org/10.1145/1985793.1985836
- [32] https://github.com/kucherenko/jscpd/blob/master/README.md ；https://github.com/kucherenko/jscpd/blob/master/FORMATS.md
- [33] https://pmd.github.io/pmd/pmd_userdocs_cpd.html
- [34] https://arxiv.org/pdf/2509.25754v1
- [35] https://arxiv.org/html/2407.02402v1
- [36] https://arxiv.org/html/2408.04430v3
- [37] https://arxiv.org/html/2505.04311v1
- [38] https://arxiv.org/html/2504.04537v1 ；https://github.com/salab/iccheck
- [39] https://www.arxiv.org/pdf/2511.04824
- [40] http://arxiv.org/pdf/2603.04177v2.pdf

- [41] https://arxiv.org/abs/2309.12499
- [42] https://arxiv.org/html/2604.12220v1
- [43] https://arxiv.org/html/2305.14129v3
- [44] https://arxiv.org/html/2408.01733v1
- [45] https://arxiv.org/html/1906.08903v1
- [46] https://arxiv.org/html/2605.06209v1
- [47] https://arxiv.org/html/2510.01003
- [48] https://arxiv.org/html/2503.22424v2
- [49] https://arxiv.org/html/2603.01327v3
- [50] https://arxiv.org/html/2410.14684v2
- [51] https://arxiv.org/html/2608.09802v1
- [52] https://arxiv.org/abs/2503.07832v1
- [53] https://arxiv.org/html/2609.04898v1
- [54] https://arxiv.org/html/2511.11012
- [55] https://arxiv.org/abs/2607.01213
- [56] https://arxiv.org/html/2506.04418v1
- [57] https://arxiv.org/html/2609.03254
- [58] https://code.visualstudio.com/blogs/2026/09/16/building-the-github-copilot-inline-suggestions-model-part-one/
- [59] https://arxiv.org/html/2508.10074
- [60] https://arxiv.org/html/2602.21697v1
- [61] https://arxiv.org/abs/2504.09691
- [62] https://arxiv.org/abs/2402.07138
- [63] https://arxiv.org/abs/2305.18584
- [64] https://arxiv.org/abs/2503.09089
- [65] https://arxiv.org/abs/2512.10218 （未核验）
- [66] https://arxiv.org/html/2511.00197v1
- [67] https://arxiv.org/abs/2606.26979
- [68] https://arxiv.org/html/2606.11976
- [69] https://arxiv.org/html/2608.09072v1
- [70] https://arxiv.org/html/2608.07614
- [71] https://arxiv.org/abs/2605.07769
- [72] https://arxiv.org/abs/2609.04061
- [73] https://arxiv.org/html/2502.13069v3
- [74] https://arxiv.org/html/2604.14624v1
- [75] https://arxiv.org/html/2603.26233v3
- [76] https://arxiv.org/html/2607.28887
- [77] https://arxiv.org/html/2609.35357
- [78] https://arxiv.org/html/2503.15223v2
- [79] https://arxiv.org/html/2509.13941v1
- [80] https://arxiv.org/abs/2503.13657 （未核验）
- [81] https://arxiv.org/abs/2505.13360 （未核验）
- [82] https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- [83] https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8
- [84] https://github.com/anthropics/claude-code/issues/49216
- [85] https://arxiv.org/html/2104.07844v1

- [86] http://www.cs.loyola.edu/~binkley/papers/saner16-tarmaq.pdf
- [87] http://www.cs.loyola.edu/~binkley/papers/ase16-mining-guidelines.pdf
- [88] http://www.cs.loyola.edu/~binkley/papers/scam16-history-exploration.pdf
- [89] http://www.cs.loyola.edu/~binkley/papers/msr16-recommendation.pdf （未核验）
- [90] http://www.cs.loyola.edu/~binkley/papers/ase17-predicting-relevance.pdf （未核验）
- [91] https://arxiv.org/html/2609.37045v1
- [92] http://www.dsc.ufcg.edu.br/~jarthur/upload/publications/On_the_precision_and_accuracy_of_impact_analysis_techniques.pdf
- [93] https://arxiv.org/abs/1812.06286
- [94] http://people.compute.dtu.dk/~huba/xp2001-web/papers/Chapter3-Rajlich.pdf
- [95] https://www.cs.wm.edu/~denys/pubs/JSME-FL-SurveyCRCV1.pdf
- [96] https://link.springer.com/article/10.1007/s10664-012-9233-9
- [97] https://doi.org/10.1109/WCRE.2010.21 （未核验）
- [98] https://doi.org/10.1109/ICSE.2012.6227172 （未核验）
- [99] https://publikationen.bibliothek.kit.edu/1000179816/164563088
- [100] https://people.inf.ethz.ch/suz/publications/fse13-db-study.pdf
- [101] https://discovery.ucl.ac.uk/id/eprint/10091100/1/icse20.pdf
- [102] https://arxiv.org/html/1702.03906v2
- [103] https://github.com/actions/checkout
- [104] https://github.com/adamtornhill/code-maat/blob/master/README.md
- [105] https://www.chromium.org/chromium-os/developer-library/guides/development/keep-files-in-sync/
- [106] https://github.com/simonepri/ifttt-lint
- [107] https://github.com/slnc/ifchange
- [108] https://www.cs.mcgill.ca/~martin/papers/ase2017.pdf
- [109] https://arxiv.org/abs/2010.01625
- [110] http://www.cs.uic.edu/~venkat/publications.html
- [111] https://dl.acm.org/doi/10.1145/32206.32212
- [112] https://arxiv.org/html/2103.07487v1
- [113] https://abseil.io/resources/swe-book/html/ch22.html
- [114] https://arxiv.org/abs/2501.06972 （未核验）
- [115] https://github.com/anthropics/claude-code/issues/40282
- [116] https://github.com/traviswye/ContextAtlas/blob/main/docs/adr/ADR-13-python-adapter-pyright.md
- [117] https://ast-grep.github.io/reference/languages.html ；https://github.com/comby-tools/comby/releases
- [118] https://docs.semgrep.dev/writing-rules/pattern-syntax ；https://docs.semgrep.dev/semgrep-pro-vs-oss/ ；https://docs.semgrep.dev/semgrep-ce-languages
- [119] https://docs.openrewrite.org/concepts-and-explanations/lossless-semantic-trees ；https://docs.openrewrite.org/reference/rewrite-maven-plugin
- [120] https://ts-morph.com/navigation/finding-references ；https://libcst.readthedocs.io/en/latest/metadata.html ；https://github.com/facebookincubator/fastmod
- [121] https://github.com/sourcegraph/scip ；https://sourcegraph.com/docs/batch-changes/batch-spec-yaml-reference
- [122] https://blog.jetbrains.com/ai/2026/05/what-happens-when-you-give-agents-ide-native-seach-tools/
- [123] https://blog.jetbrains.com/ai/2026/10/how-netflix-made-ai-coding-agents-more-efficient/
- [124] https://cursor.com/blog/semsearch
- [125] https://ai.engineer/talks/zKk7sDMGDEQ-benchmarking-semantic-code-retrieval-on-claude
- [126] https://github.com/oraios/serena
- [127] https://codeql.github.com/docs/codeql-overview/supported-languages-and-frameworks/ ；https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md （未核验）
- [128] https://github.com/uber/piranha ；https://dl.acm.org/doi/10.1145/3656429 （未核验）

- [129] https://code.claude.com/docs/en/skills
- [130] https://code.claude.com/docs/en/hooks
- [131] https://code.claude.com/docs/en/tools-reference
- [132] https://code.claude.com/docs/en/sub-agents
- [133] https://code.claude.com/docs/en/workflows
- [134] https://code.claude.com/docs/en/commands
- [135] https://code.claude.com/docs/en/memory
- [136] https://code.claude.com/docs/en/plugins/code-intelligence
- [137] https://code.claude.com/docs/en/plugin-evals
- [138] https://agentskills.io/specification
- [139] https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- [140] https://code.claude.com/docs/en/plugins/cli-reference
- [141] https://code.claude.com/docs/en/plugins/manifest-reference
- [142] https://code.claude.com/docs/en/plugins/loading
- [143] https://code.claude.com/docs/en/plugins/components
- [144] https://code.claude.com/docs/en/plugins-reference
- [145] https://code.claude.com/docs/en/permission-modes
- [146] https://code.claude.com/docs/en/settings-reference
- [147] https://www.anthropic.com/engineering/claude-code-auto-mode
- [148] https://agentskills.io/skill-creation/evaluating-skills
- [149] https://agentskills.io/skill-creation/optimizing-descriptions
- [150] https://github.com/agentskills/agentskills/tree/main/skills-ref
- [151] https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md ；https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator
- [152] https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/scripts/run_eval.py
- [153] https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills
- [154] https://github.com/anthropics/skills
- [155] https://github.com/ast-grep/ast-grep-mcp
- [156] https://github.com/abhigyanpatwari/GitNexus
- [157] https://github.com/ory/lumen （未核验）
- [158] https://github.com/zilliztech/claude-context （未核验）
- [159] https://github.com/SonarSource/sonarqube-agent-plugins （未核验）
- [160] https://github.com/sourcegraph-community/sourcegraph-claudecode-plugin
- [161] https://github.com/cursor/plugins/blob/main/pstack/skills/blast-radius/SKILL.md
- [162] https://github.com/soumyaRauth/skills-hub/blob/main/skills/impact-map/README.md
- [163] https://github.com/kingbootoshi/cartographer
- [164] https://kiro.dev/docs/steering/
- [165] https://github.com/github/spec-kit/blob/main/templates/commands/analyze.md
- [166] https://scottspence.com/posts/how-to-make-claude-code-skills-activate-reliably
- [167] https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals
- [168] https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals
- [169] https://arxiv.org/abs/2507.15003 （未核验）

**本地证据**（自核，都在本机上运行或检查）

- [L1] 基线试验第二轮：/Users/yezhoufan/VScodeProjects/change-propagation/docs/research/pilot/README.md，以及同目录的 gt.json、grade.py、results/round2/
- [L2] 基线试验用量明细：/Users/yezhoufan/VScodeProjects/change-propagation/docs/research/pilot/results/round2/usage.json
- [L3] 首个编辑回放：/tmp/cp-gap1/sim.py，标准答案为 pilot/gt.json
- [L4] 规模测量：/Users/yezhoufan/VScodeProjects/change-propagation/docs/research/04-scale-measurements.md 和 /tmp/cp-gap1/noop_hook.py（用 rg 测量）
- [L5] co-change 复现：/tmp/cp-scripts/cochange.py
- [L6] 近似重复检测：/tmp/cp_scripts/neardup2.py、/tmp/cp_scripts/verify_after.py
- [L7] 本机 `claude plugin validate --strict --json`，Claude Code 2.1.309
- [L8] /Users/yezhoufan/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json
- [L9] /Users/yezhoufan/.claude/plugins/marketplaces/claude-plugins-official/plugins/code-modernization/workflows/extract-rules.js
- [L10] 本机 `command -v`、npx、uvx 探测，macOS，2026-10-30
- [L11] gap-2 对 6 个 OSS 仓库的本地扫描（element-x-ios、gitea、immich、mattermost@4bf16a6a、thunderbird-android、zulip@566f98a9）：git grep 检索；人工复核每类随机 20 条，1 人评定；/tmp/cp-gap2/scripts/ 下的 path_rot.py、sync_scan.py、shared_literals.py；另用 GitHub MCP 做了代码搜索
- [L12] Claude Code 2.1.309 二进制检查（auto 模式规则过滤函数 zYn、plugin eval 运行器）

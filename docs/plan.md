# change-propagation 开发计划（草案）

日期 2026-10-30。状态：M0 已完成（基线见 [05-m0-baseline.md](research/05-m0-baseline.md)）。M1 两次评测见 [06](research/06-m1-first-run.md) 和 [07](research/07-m1-second-run.md)：第 6 节的 M1 通过条件都满足（E1 召回 45/45，零擅自修改，摘要约 1.8k token），列表顶栏也到了 18/21；第 1 节的成本标准没满足，每次 $2.66，是基线的 2.5 倍。M2 的五个通道已实现，离线测量见 [08](research/08-m2-channels.md)。M2 两次回归见 [09](research/09-m2-regression.md)：列表顶栏 21/21、天然同类 12/12，message-level-color 3/3 触发 skill；每次 $2.19 和 $2.45。之后评测改用 `claude-sonnet-5-5`，第 3 次带对照组：装了插件 $1.01/次，是不装的 2.24 倍，成本标准（≤ 2 倍）还差一点；列表顶栏 21/21 对 6/21，message-level-color 6/6 对 0/6。第 4 次（[09](research/09-m2-regression.md) 第 10 节）：$0.91 对 $0.51，1.78 倍，成本标准满足；列表顶栏 21/21 对 10/21，message-level-color 9/9 对 0/9，零擅自修改、零误改。历史共变见 09 第 11 节：评测沙箱里 git 一直没运行（已改用 CLT 的 git），在真实历史上回放准确率约四成，新增改后复查同伴文件和带真实历史的用例 e1/action-placeholder。第 5 次回归（09 第 12 节）：1.85 倍，git 仍被评测沙箱屏蔽，已改为直接读 .git（cplib/gitread.py）；装了插件的代理有 2 次把插件目录当项目根，已在 SKILL.md 和 seed 输出里说明。第 6 次回归跑了两遍（09 第 13 节）：都是 1.83 倍；gitread 运行了，但评测的 home 目录本身是 git 仓库，脚本把它当成工作区，git 通道都落在它上面，已改为把下面有仓库的目录当工作区。

依据：
- [03-scenario-followup.md](research/03-scenario-followup.md)：近似对象召回、契约锚点、分档成本、评测构建。
- [04-scale-measurements.md](research/04-scale-measurements.md)：tier 0 脚本在 2.5k 和约 10 万文件上的实测，ast-grep 和 jscpd 的对照。
- [pilot/README.md](research/pilot/README.md)：40 文件 fixture 上 9 次不用 skill 的基线。
- [05-m0-baseline.md](research/05-m0-baseline.md)：M0 基线，E0 和 E1 共 9 个用例各 3 次，Sonnet 5.5。
- [06-m1-first-run.md](research/06-m1-first-run.md)：M1 第一版 skill 的同条件评测。
- [07-m1-second-run.md](research/07-m1-second-run.md)：按请求范围分级后的第二次评测。
- [08-m2-channels.md](research/08-m2-channels.md)：M2 通道的实现和离线测量，message-level-color 的第一次评测。
- [09-m2-regression.md](research/09-m2-regression.md)：M2 的两次回归评测，message-level-color 的 grader 修正。
- [01-research-report.md](research/01-research-report.md) 和 [02-findings-catalog.md](research/02-findings-catalog.md)：8 个方向的文献和工具调研，加 3 个补查方向（触发方式、S1 的声明式耦合、权限模式）。本计划的架构取 01 第 8.2 节的方案 A。

## 1 目标

让 agent 在改动前后找全这次改动必须波及的位置，并按分级规则处理：该改的改，要你决定的先问，不确定的只列出。

首要场景是你的 AGV 平台：修好一个对象后，找回同样有问题、但验收说明没提到的近似对象。它们可能在另一个前端、另一种后端语言里，或者只通过 MQTT topic、WebSocket 事件、JSON 字段这类字符串和修复点相连。

你给的真实例子：prompt 是"场景部署列表组件中，顶栏灰色部分未覆盖滑动条，要求修改为滑动条从顶栏下方起，类似列表修改为统一"。项目里有大量同样带灰色顶栏和滚动条的列表，agent 只改了其中一部分。prompt 已经点明"类似列表"，所以问题不在触发，而在召回。这些列表的名字各不相同，写法也可能不同：样式块里的 CSS、UnoCSS 这类工具类、组件库的滚动组件、拆成子组件的表头。它们共有的是一种结构：灰色顶栏被包在滚动容器里。靠名字搜不全，要按结构找（第 3.2 节的特征卡）。

第二个真实例子（10-31）：prompt 要求把提示消息从无色改成蓝色，AI 改了消息组件，但总览页有一张按消息占比取色的展示卡，它的映射表里没有 info，落在默认的无色分支，AI 没改。这类改动的同类对象不是组件，而是"映射同一组枚举值的表"：样式表、`switch`、按占比取色的计算、标签类型。它们名字各不相同，共同点是附近同时出现几个兄弟值（info、warning、error）。缺了被改值、又有 default 或 `??` 兜底的表，就是最容易漏的那张（第 3.2 节枚举映射通道）。

三类问题都要覆盖：
- S1 需求耦合：改 A 时，与 A 共享规则的 B 也要保持一致。
- S2 散落的同类：给"所有 X 类组件"做同一改动，而 X 的命名各不相同。
- S3 重复整合：抽取同类对象时，找全已经漂移的副本。

成功标准（基线和目标值见 05 第 5 节）：
- 评测集上按位置算的召回高于不用 skill 的基线，exclude 位置零误改。基线：E1 不含列表顶栏 42/45，M1 目标 45/45；列表顶栏 R1-R7 为 10/21，M2 目标 ≥ 18/21。
- 需要你确认的位置，未经确认就被修改的次数为 0。基线里 E0 有 5/15、E1 有 4/24 的 coupled 站点次被直接改了。
- 单次运行成本不超过基线的 2 倍（基线平均 $1.06）。
- 每次调用给主上下文增加的内容不超过约 2k token，完整候选放在磁盘文件里。
- 10 万文件、索引已建好时，tier 0 一次扫描在 10 秒左右。

## 2 已确定的决定

| 决定 | 内容 | 来源 |
|---|---|---|
| 交付形态 | Claude Code plugin：`.claude-plugin/plugin.json` 加 `skills/change-propagation/`，以后可加 subagent 和 hook | 你的选择 |
| 适用范围 | 通用 skill，按技术栈逐步适配。第一个栈是 Vue 前端加 Go/Python/Node 后端，契约走 MQTT/WebSocket | 你的选择 |
| 范围分级 | 直接命中的改；推断出的耦合附证据，你确认后再改；低可信的只列出 | 你的选择 |
| 触发 | description 自动触发，加 `/change-propagation` 手动调用 | 你的选择 |
| 成本分档 | 默认只跑脚本（tier 0）；subagent 判定和验证只在你要求或改动高风险时运行 | 你的选择 |
| 默认档不下载工具 | auto 模式下 Claude 不能用 npx 下载，本次会话被拦了多次。默认档只用 skill 自带的 Python 标准库脚本和本机已有的工具 | 本次会话的观察 |
| hook | 收尾类（Stop、压缩后重新注入、PreToolUse 确认门）默认开；触发类按评测结果决定默认值（第 3.6 节） | 你交给我判断 |
| 确认过的耦合存在哪里 | `.change-propagation/couplings.json`，v1 不导出 `.claude/rules`（第 3.7 节） | 你交给我判断 |

## 3 设计

v1 采用 01 第 8.2 节的方案 A：只有 skill，由 description 或 `/change-propagation` 触发，确认步骤靠同一轮里的 AskUserQuestion。hook 做成可以单独开关的选项，用 plugin eval 对比开和不开之后再定默认值（第 3.6 节）。大仓库里的 S2、S3 要不要按模块派只读的 Explore 子代理（方案 C），等有了 E2 的数据再定。

### 3.1 工作流（SKILL.md 正文）

skill 在主会话里内联运行，不用 `context: fork`。fork 出的 subagent 看不到对话历史，也不能用 AskUserQuestion，而确认步骤两样都要用。压缩后 SKILL.md 只保留前 5,000 token，所以分级规则、ledger 位置和结束条件写在正文最前面。

1. **写出改动和不变量。** 用一两句话写清改的是什么、改前改后的行为，以及"A 和 B 必须在 Z 上一致"这类不变量。调研里 Claude Code 写的 plan 只覆盖了 41.6% 的约束，需求本身没写清比搜不到更常见。
2. **生成种子。** 从 prompt 和 diff（已经改好的，或准备改的）里取标识符、字符串 key（JSON 字段、topic、事件名、i18n key）、旧值和它的上下文（如 `>= 8`、"至少 8 位"），以及修复删掉的行。S2 再加一张特征卡：从 2-3 个已知样例里收集类名、props、import、样式和 API。种子写进 ledger。
3. **跑 tier 0。** `python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py scan` 按第 3.2 节的通道在上下文之外搜索，完整结果写进 ledger。脚本的输出只有约 1-2k token 的摘要：各通道的计数，按前后端分组的前 30 个候选（`path:line`、命中的通道、一行理由），搜了哪些根目录，没搜什么。
4. **只读候选的局部。** 用 `cp.py show <ID>` 读候选所在的函数或块，不读整个文件。
5. **分级。** 每个候选标成 direct、coupled、review 或 exclude，附上证据，用 `cp.py mark` 写回 ledger。分级看改动类型和证据，不看是哪个通道找到的（01 第 8.1 节）：
   - direct：prompt 点名的对象；类型检查或 LSP 证明必须跟着改的位置；写在被改代码里或正上方、目标能解析的耦合注释所指的位置。
   - coupled：规则载体和契约的命中、强的历史共变、特征卡的命中，以及所有副本。逐字相同的副本也只到这一档，因为研究里不一致的克隆组只有 28% 是无意的。
   - review：只有单一弱信号的候选、相似度低的副本，以及被否决的候选（附理由）。
   - S3 时每个副本还要记下行范围和处理方式：删除，或改成调用公共函数。
6. **问一次。** coupled 项按耦合规则分组，用一次 AskUserQuestion 提问。每个问题给出推荐选项和证据，问的是规则（"重置密码要不要和注册共用 12 位的规则"），不是逐个位置。得到确认前不改这些位置，提问超时也算没确认。共享规则所在的文档和测试不先改。一次调用最多 4 个问题、每个问题最多 4 个选项，也就是最多 16 项；更多时按不变量或代码形状分组，或者请你直接编辑 ledger 文件。
7. **修改。** 只改 direct 和已确认的位置，不顺手改名或重构。
8. **复查。** `cp.py verify` 在改后的代码上重跑同样的查询：旧名、旧值、旧模式还剩在哪里；S3 的旧函数体是否已删除或只剩委托调用；ledger 里每一项都要有结论；含有被删或被替换 token 的注释和文档行列为确认项。然后跑测试和类型检查；高风险时先派一个只读的 reviewer 子代理，只给它意图和 ledger。最后报告改了什么、问了什么、列了什么、排除了什么，用了哪些通道，哪些地方没搜。"列出但没改"算正常结果。

不同权限模式下的做法（01 第 6.6 节）：
- auto：每个脚本一条固定路径的 allow 规则，执行的命令与规则逐字一致。skill 授予的权限在你发下一条消息时清除，所以确认步骤放在同一轮的 AskUserQuestion 里；如果你在新消息里回答，就重新调用 skill，它从没关闭的 ledger 接着做。
- plan：只有计划文件可写。脚本只读、只输出到 stdout；ledger 先写成计划文件的附录，并注明它优先于"只列几个代表性路径"的要求；计划批准后再写 ledger 文件。
- `-p` 和 dontAsk（plugin eval 的每次运行都是 dontAsk）：没有 AskUserQuestion，coupled 项一律保持待确认，不编辑。

### 3.2 tier 0 的检索通道

所有通道先做名字变体扩展：按大小写、缩写和数字边界拆词（`AGVTaskID` 拆成 AGV、Task、ID），生成 snake、camel、Pascal、kebab、SCREAMING 写法，匹配时忽略大小写、`-` 和 `_`。搜索覆盖所有前后端根目录，每个栈至少保留 1 个候选。

| 通道 | 从修复里取什么 | 找什么 | 已有原型和实测 |
|---|---|---|---|
| 名字和值 | 标识符、字符串 key、旧值及上下文 | 同名或变体写法的引用、同一个旧值 | `rg_bench.py`：各种写法合成一个正则，和搜一个字面量一样快；2.5k 文件 30-40 ms，10 万文件 2-4 s；输出必须先聚合 |
| 契约 | JSON 字段、MQTT topic 模板、WS endpoint 和事件、i18n key | 另一端的生产者和消费者 | `contract_map.py`：2.5k 文件 1.2 s，一个 key 的切片 30-280 token；找到了 `last_visit_time` 被读成 `lastVisitTime` 的真 bug |
| 修复签名 | 修复删掉的行，抽象后匹配（L1 保留 member 名和字面量） | 还带着旧代码、没有新代码的位置 | Go 历史重放：每个种子最多 20 个候选时召回 45%，平均 2.4 个候选；94 个种子里 23 个超上限，要报"太泛"（原型在 `research/prototypes/variant-history/`） |
| 函数指纹 | diff 里的函数 | 复制后分叉的函数 | `shingle_index.py`：有副本的函数第 1 名就是副本，`actionValueChange` 等已分叉的副本也找到了；短函数和重写过的实现找不到 |
| 枚举映射 | 改到的状态值和它的兄弟值 | 同一枚举的其他映射表，标出缺新值、走兜底分支的表 | 已提前到 M1 实现（`cp.py seed --enum`）：E1 的 message-level-color 种植用例里，总览卡片和顶栏铃铛两张缺 info 的表都排在前面；干净的 ThingsPanel 前端上 `--enum info,warning,error,success` 约 90 张表，其中 15 张标为走兜底 |
| 规则载体（S1） | 改动处的常量、配置键、校验器名、路由、错误文案、i18n key | 同一条规则在其他层的位置，按层列表；只改了一侧就是确认项 | 补查：zulip 的 `password_min_length` 只在 15 个文件里（注册、重置、改密码、设置），`password` 则有 222 个 |
| 声明式耦合（S1） | 被改的路径、文件名和符号 | 正向：被改代码附近"keep in sync"类注释所指的位置；反向：指向被改位置的注释 | 补查：6 个开源仓库里没有 `LINT.IfChange`，耦合几乎都写成自由文本注释，sync/update 类措辞的精度 60-65%；56% 的耦合只有单向指针，反向查找 0.3-1.1 s |
| 历史共变 | 被改的文件 | 过去经常和它一起改的文件 | 01 第 3.2 节；阈值、大提交和改名的处理待实测 |
| 非代码和外围产物 | 同上的 key 和值 | SQL seed、网关和代理配置、locale、路由、文档、测试、fixture、mock，每次都扫 | 补充补丁研究里 14-15% 的文件与第一次补丁既不重叠，也没有结构关系 |
| 特征卡（S2） | 样例的类名、props、import、样式、API；布局类改动还要取样例的结构 | 同一类但命名不同的组件；布局类改动找同样的结构，例如被包在滚动容器里的灰色顶栏 | 试点里 agent 组合领域词、`createPortal`、`position: fixed` 等结构特征和 API 签名找全了弹窗；脚本按文件统计命中的特征数并排序。ThingsPanel 前端的 337 个 .vue 文件里没找到你那种列表的自然实例（列表大多用 NDataTable），所以 E1 里要种植 |

过滤和停止：
- 修复签名通道的候选必须含修复删掉的核心行、不含新增的行；文件历史里已经有同样修改的剔除。
- 生成代码（文件头有 `Code generated`）、`node_modules`、`dist` 默认跳过。
- 搜索分轮进行：先搜修复所在的文件和函数，再搜全仓；某一轮新增少于 3 个候选就停。
- 放宽匹配条件前先估算命中数，命中翻到 5 倍以上时先问你（5 倍是建议值，没有实测）。
- 输出写明用了哪一级抽象、命中多少，不把结果说成已经完整。

声明式耦合只测了英文措辞，"保持一致""同步修改"这类中文写法的精度在 M1 实测。

布局类的 S2 改动要一个 SFC 结构查询，grep、ast-grep 和 jscpd 都做不了：
- 读 `<template>` 的元素嵌套和 class，读 `<style>` 块（含 scoped 和 scss 嵌套）里每个 class 的声明，再加上模板里的工具类（如 `overflow-y-auto`、`sticky top-0`、`bg-gray-100`）和内联样式。
- 认得组件库的滚动和表格组件（`n-scrollbar`、`el-scrollbar`、NDataTable 的 `max-height`），并跟一跳进子组件，因为表头可能是单独的组件。
- 查询来自 prompt 点名的样例和修复的 diff：修复前是什么结构（滚动容器里包着顶栏），修复后是什么结构。还是旧结构的列表列为候选，已经是新结构的不列。

### 3.3 ledger 和上下文纪律

- ledger 是一个 JSON 文件，每个位置一条：ID、`path:line`、符号、anchor（一小段原文，行号变了也能重新定位）、产生它的查询、分数、证据、级别（direct、coupled、review、exclude）、状态（open、edited、asked、declined、listed）和结论。重跑时 ID 不变；脚本负责写入，agent 只改状态。
- 主上下文里只放摘要和读过的局部，其余内容按 ID 去取。
- 位置：仓库根目录下的 `.change-propagation/`，ledger 和索引缓存都放在这里。目录里放一个内容为 `*` 的 `.gitignore`，这样不会弄脏 git 状态，你也能直接打开看。不放 `.claude/` 或 `${CLAUDE_PLUGIN_DATA}`：两处都在受保护的路径下，default 模式会弹提示，auto 模式交给分类器，dontAsk 直接拒绝；plugin eval 的沙箱也只允许写工作区（01 第 6.6 节）。
- 上下文压缩后，SessionStart hook（matcher 为 `compact`）重新打印没关闭的条目，控制在 8,000 字符以内。

### 3.4 分档

| 档 | 何时运行 | 做什么 | 成本 |
|---|---|---|---|
| tier 0 | 默认 | 第 3.2 节的脚本，不用模型 | 给主上下文增加约 1-2k token |
| tier 1 | 你要求，或改动高风险 | 一个 subagent 先写不超过 10 行的规则卡，再逐个判定候选；只调整顺序，不删候选 | 每个候选约 1.5k token（03 的估算） |
| tier 2 | 你要求，或 tier 1 留下不确定的项 | 按栈开 1-3 个只读的验证 subagent，可以用 gopls、pyright | 每个 Opus verifier 约 $0.8（03 的估算） |

"高风险"的定义（先按这个执行，可以随时改）：候选跨两个以上的栈或前端，并且共享契约；修复签名通道报"太泛"；S3 要删除重复实现。

模型选择要实测：按文档，plugin agent 里写的 `model: haiku` 优先于默认的 subagent 模型；但你的设置用 `CLAUDE_CODE_SUBAGENT_MODEL` 把 subagent 固定为 Opus 5.5，它会不会覆盖 agent 自己的设置还不确定。如果会覆盖，tier 1 就不便宜了。放在 M6 实测。

### 3.5 运行环境和依赖

- 脚本只用 Python 3.9 及以上的标准库（macOS 自带 3.9.6），任务中途不下载任何东西。
- 文件枚举：git 仓库用 `git ls-files`，其他情况用 `os.walk`。文本搜索优先用 `git grep`，没有 git 时用 Python。Claude Code 的 Bash 里 `rg` 是内置的 shell function，PATH 上没有 rg，脚本不能直接调用它。`git grep` 在 10 万文件上的速度放在 M4 实测。
- 本机已经装了 ast-grep、jscpd 或 LSP 时可以选用。04 测出的坑写进参考文档：ast-grep 的 Go 调用模式要写成"上下文 + `--selector call_expression`"；`.vue` 要按 script 的 lang 分别跑 ts 和 tsx；jscpd 用 `--similarity=0.8`，并先排除生成代码。
- 10 万文件时，契约图和函数指纹的全量构建各要约 50 s、1-1.8 GB 内存。这是在相同副本上测的，真实仓库会更大。缓存按文件的 mtime 和大小增量更新；第一次使用时构建，并提示要花多久。
- 多仓库：脚本接受多个根目录。第一次在多仓库项目里使用时，问你兄弟仓库的路径，记进 `.change-propagation/roots`。
- 权限：auto 模式会丢弃 `Bash(python3 *)` 这类解释器通配规则，但保留指向固定脚本的规则。所以 SKILL.md 的 `allowed-tools` 写 `Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/cp.py *)`，执行时命令不加引号、不用 `cd &&`、不用 `>` 重定向。skill 的 `allowed-tools` 在 auto 模式下是否同样经过这道过滤，还要实测（01 第 9.2 节）。

### 3.6 hook（都可以单独开关）

写在 SKILL.md `hooks` 里的 hook 从 skill 被调用时才生效，不能用来触发 skill。用来触发的 hook 要放在插件的 `hooks/hooks.json`，会话一开始就生效，子代理里也会触发。command hook 在权限系统之外、带着你的全部权限运行，所以 hook 脚本只读、离线、有时间上限。

收尾和纪律类，写在 SKILL.md 里，M3 加，默认开启：
- Stop：ledger 里还有没处置的条目时阻止结束一次，并列出这些 ID；`stop_hook_active` 为真时放行。01 建议如果只加一个 hook，先加这个。
- SessionStart（matcher 为 `compact`）：重新打印没关闭的条目，8,000 字符以内。SKILL.md 里声明的 SessionStart 在压缩时会不会触发，要实测。
- PreToolUse（Edit|Write，可选）：编辑落在还没确认的 coupled 位置上时返回 ask，弹出权限提示。auto 模式下工作目录内的编辑不经过分类器就被批准，这是唯一能强制执行确认步骤的办法。没有 ledger 时什么也不做。

触发类，放在 `hooks/hooks.json`，M3 实现。默认开不开按事先定好的规则：在 plugin eval 里，加了这个 hook 的组触发率或召回更高，精度和范围决策没有变差，每条 prompt 增加的中位延迟低于 1 s、每次编辑低于 3 s，才默认开启。PostToolUse 依赖预建的索引，M4 之前不开。
- 依据：只靠 description 时，第三方用 Sonnet 4.5 测得标准 prompt 的激活率是 50-55%，间接表述约 0%，你的验收类 prompt 多半属于简单、间接的那种。同一测试里加了 UserPromptSubmit hook 后是 75-100%。
- UserPromptSubmit：1 秒以内的正则门，不调用模型、不阻塞；命中时注入不超过 500 字符的事实陈述（命令式的文本可能触发 prompt injection 防御）。
- PostToolUse（Edit|Write）：用这次编辑的旧文本和新文本做查询，查预建的索引，上限 2-3 秒，注入不超过 2,000 字符。在试点的 9 次运行上回放：T1 找到 7/7，T3 找到 5/5，T2 有 2 次是 0/8，因为它的第一步是新建 CSS 文件，S2 还要加上 prompt 里的类别词。
- 预算：空 hook 的中位耗时 63 ms；hook 输出上限 10,000 字符；10 万文件时每次编辑都现搜要 2-4 s，所以必须先有索引。

### 3.7 暂不做

- 默认建向量索引，或依赖外部检索服务。
- 依赖 CodeQL 或 Semgrep：许可和 Vue 支持都有问题。
- 让 LLM 合成查询：QLCoder 每个 CVE 花 $2.90，成功率 53.4%。
- 默认把检索交给 subagent：RefactorPlatform 上委托给 subagent 的成功率是 66%，检索式单 agent 是 86%。
- 默认不往你的代码里写耦合注释或 `LINT.IfChange` 指令，仓库已经在用这种写法时才考虑。确认过的耦合先记在 `.change-propagation/couplings.json`，用路径、符号和 anchor 定位，不用行号；CloneTracker 用这种方式记录的 3,275 个区域里 96% 都跟踪对了。每次运行先读它：改到其中一处时，同组的其他位置直接列为候选。v1 不导出成 `.claude/rules`：那是受保护的路径，写入要你确认；而且规则在读到匹配文件时就会进上下文，增加 token。

## 4 插件目录结构

```
change-propagation/
├── .claude-plugin/
│   └── plugin.json              # name、version、description
├── skills/
│   └── change-propagation/
│       ├── SKILL.md             # 分级规则和工作流，正文不超过 500 行
│       ├── references/
│       │   ├── ledger.md        # ledger 的字段和状态
│       │   ├── channels.md      # 各通道的用法和局限
│       │   ├── contracts.md     # MQTT 通配符、WebSocket、JSON 字段、i18n
│       │   ├── categories.md    # S2 的特征卡
│       │   ├── consolidation.md # S3 的整合清单和删除范围
│       │   ├── tools.md         # 可选的 ast-grep、jscpd、LSP 及已知的坑
│       │   └── stacks/          # vue.md、go.md、python.md、node.md
│       └── scripts/
│           ├── cp.py            # 入口：seed、scan、show、mark、add、verify、status
│           └── cplib/           # names、walk、channels、contracts、declared、enums、ledger、show；M2：sfc、layout、shingle、history
├── agents/                      # M6：cp-triage、cp-verifier
├── evals/                       # claude plugin eval 的用例
├── tests/                       # 脚本的单元测试和小 fixture
├── docs/                        # 调研和计划
├── README.md
└── LICENSE
```

- frontmatter 按最严的规则写：`name: change-propagation`，和目录同名；description 用第三人称，不超过 1,024 字符，不含尖括号。description 先写触发场景（改的规则别处也要一致；"所有 X"；统一、抽取、去重；即使请求只点名一处），再写 skill 做什么。另加 `argument-hint`。
- `claude plugin validate --strict` 查不出大部分 SKILL.md 的错误：名字大写、超长、和目录不同名、含尖括号都能通过。所以另写一个 lint 脚本，放进 CI。
- 开发时用 `claude --plugin-dir` 加载插件。

## 5 评测计划

### 5.1 用例集

| 集 | 内容 | 用途 |
|---|---|---|
| E0 | 试点的 40 文件 fixture，T1-T3 | 回归。主要看范围决策：T1 里共享的密码规则必须先问 |
| E1 | ThingsPanel（2.5k 文件，Go + Vue + MQTT/WebSocket）上的种植用例、真实漂移和真实提交对 | 主评测：召回、精度、范围决策 |
| E2 | ThingsPanel、JumpServer（Django 加两个 Vue 前端和一个 Go 服务）和 n8n（Node + Vue，约 3.3 万文件），再加生成代码和 `node_modules` 当干扰项，凑到约 10 万文件 | 规模：耗时、内存、上下文 token，召回会不会下降 |
| E3 | 你的 AGV 仓库，在你的机器上跑 | 真实效果，只回传指标 |

评测用的仓库只放在本机，不进插件仓库（JumpServer 是 GPL，n8n 是 Sustainable Use License）。

E1 的第一批候选，04 里都读过代码：
- 列表顶栏与滚动条，来自你的例子：在 ThingsPanel 前端种植 6-8 个灰色顶栏被滚动条盖住的列表，写法各不相同：样式块里的 CSS、复制后改了 class 名的副本、UnoCSS 工具类、`n-scrollbar` 同时包住顶栏和列表、表头拆成子组件。另放诱饵：顶栏已经在滚动容器外的列表、带 `max-height` 的 NDataTable、没有顶栏的滚动区域。prompt 按你的原话改写，只点名其中一个列表。E2 里再在 JumpServer 的两个 Vue 前端（lina、luna）各放一份。
- `normalizeAlarmLevel`：两个 ThingsVis 组件里各有一份，都不认后端规定的 H/M/L。prompt 只报其中一个组件的显示问题。
- `actionValueChange`：scene-edit 校验 4 种动作类型，linkage-edit 只校验 1 种。
- `last_visit_time`：后端返回 snake 写法，前端读 camel 写法，用户列表的"最后访问时间"一列显示的是创建时间。
- 设备状态 WebSocket：前端 5 个文件里的连接代码，其中一个是类方法，一个写在 `<script setup>` 顶层。
- 消息级别颜色，来自你的第二个例子（`e1/message-level-color`，已建）：prompt 只点名 `notice-message.vue` 的 info 由无色改蓝色；总览页的消息占比卡片用一张缺 info 的映射表加 `?? 'transparent'`，顶栏铃铛用三元链落到 `'transparent'`，两处都要改；系统日志的 `log-line--info` 是另一组级别，作诱饵。
- 真实提交对：Gitea #13025→#13069、#26469→#26581，1Panel cecfecf→c556aff（03 第 6.2 节）。
- 其他仓库的 S1 用例，放进 E1 或 E2：zulip 的 `password_min_length`（15 个文件），gitea 的 `MinPasswordLength` 和 `IsComplexEnough`（11 个文件），mattermost 前后端之间的"Keep in sync"注释。补查时已经克隆在 `/tmp/cp-gap2/repos`。

种植用例的做法：给一组近似位置放进同一个缺陷，prompt 只报其中一处；另放一些诱饵，即名字或结构相似但不该改的位置。每个位置标 required、ask 或 forbidden。

E3 的做法：我写一个只用标准库的挖掘脚本，你在本机找 24 小时内、提交信息含"漏改、遗漏、也要、forgot、missed"的提交对，人工标 20-30 对。代码不离开你的机器。

### 5.2 指标

- 按位置算的召回和精度，按陷阱类型分别报告：词法相同、变体写法、契约两端、复制后分叉、非代码。
- 范围决策：required 位置已改；ask 位置在最后的消息里提出，而且文件没改；forbidden 位置没动。
- 残留数：改完重跑查询，仍然命中旧写法、又没标成有意保留的位置。
- 确认负担：每次修复要你看多少条目、回答多少个问题。
- 触发率：skill 有没有被调用、在第几步调用，以及相近反例上的误触发。
- 成本：每次运行的 token、美元和时长，以及每找到一个位置的成本。
- 不只看文件级召回：调研里有文件召回更高、解决率反而更低的结果。

### 5.3 协议和预算

- 用 `claude plugin eval` 对比几组：不装插件；只靠 description；再加触发类 hook；再加 Stop 等收尾 hook。每组默认 3 次。
- 每次运行都是 `claude -p --permission-mode dontAsk`，AskUserQuestion 会被拒绝，所以确认步骤拆成两类用例。门前：断言 coupled 位置出现在最后一条消息里，而且没被编辑（`tool_used` Edit 加 `input_match`，`min 0 max 0`）。门后：用 `history_file` 回放一个已经提过问的会话，把你的确认当作 prompt，断言确认过的位置被改了。
- grader：每个该改的文件配一个 `tool_used` Edit grader，旧片段用 regex 检查已经消失，诱饵检查原样保留；ledger 用 `{source: file}` 打分；范围决策另加一条简短的 llm rubric。grader 不能要求 skill 的报告格式，否则 without 组注定失败。
- 运行参数：`--scaffold --allow-tools Bash Edit Write`；评测模型是 Sonnet 5.5（2026-10-31 起写 `--model claude-sonnet-5-5`；之前用别名 `--model sonnet`，本机映射到 `claude-sonnet-4-6`，见 [09](research/09-m2-regression.md) 第 7 节），effort 用环境变量 `CLAUDE_CODE_EFFORT_LEVEL=high`；索引在 scaffold_script 里预建（限 120 s）；max_turns 和 timeout 调大，默认的 10 轮、300 s 对大仓库不够。
- 盲测：运行期间把答案文件移走，副本放在看不出用途的路径下；不用 Workflow 启动执行者，因为它会把对话原文转给子代理。
- 预算：两组时 14 个用例 × 3 次 × 2 组 = 84 次运行，03 估计 $35-100；M0 实测平均每次 $1.06，9 个用例 × 3 次花了 $28.64、墙钟 8 分钟（`-j 4`）；加上两组 hook 对照后翻倍。先每组跑 1 次做冒烟测试。
- 防记忆污染：公开的修复对可能被模型记住，所以优先用种植用例和较新的提交。

## 6 里程碑

| 里程碑 | 交付 | 通过条件 |
|---|---|---|
| M0 骨架和基线 | plugin 骨架和 lint 脚本；E0、E1 的用例和 grader；不用 skill 跑基线 | `validate --strict` 和 lint 通过；E1 的基线有数字 |
| M1 最小可用（Vue + Go） | 名字和值（含非代码和外围产物）、契约、规则载体、声明式耦合四个通道；ledger；SKILL.md 工作流，含确认和复查；description 第一版 | E1 召回高于基线；ask 位置零擅自修改；每次给主上下文增加不超过 2k token |
| M2 近似对象通道 | 函数指纹、修复签名、枚举映射、特征卡（含 SFC 结构查询）、历史共变 | E1 里"复制后分叉"和"映射表"两类陷阱的召回比 M1 高；列表顶栏用例的召回比基线高 |
| M3 确认门、压缩和 hook | Stop、SessionStart(compact)、可选的 PreToolUse ask；触发类 hook 的对照实验；长会话用例 | 压缩后仍能把 ledger 处理完；E0 的 T1 三次都先问；各组的触发率和召回有数字 |
| M4 规模 | 增量缓存、`git grep` 引擎、E2 | 10 万文件、缓存已建好时一次扫描约 10 s；召回不比 E1 明显低 |
| M5 Python/Node 后端 | pydantic alias、Django/FastAPI 路由、MQTT.js、Socket.IO | JumpServer 和 n8n 的用例达到 E1 的水平 |
| M6 tier 1/2 | cp-triage、cp-verifier 和升档规则 | 每多花一美元换来的召回或精度提升有实测数字 |
| M7 其他栈 | React/TS、Java/Kotlin、移动端，按你的优先级 | 每个栈至少 3 个用例 |

每个里程碑结束时都在 E0、E1 上回归。description 的触发率按 skill-creator 的方法调：准备 20 条查询，其中 8-10 条是相近但不该触发的，例如"把这个局部变量改个名""给这一个按钮加动画"。

## 7 已定和仍待定的问题

10-30 已定：
- 真实漏改的例子：列表顶栏与滚动条（第 1 节），据此加了 SFC 结构查询（第 3.2 节）和 E1 的种植用例（第 5.1 节）。更多例子仍然有用，尤其是跨前端、跨后端语言，或者只靠 topic 和字段相连的。
- hook：交给我判断，见第 2 节和第 3.6 节。
- 确认过的耦合存在哪里：交给我判断，见第 2 节和第 3.7 节。

按我的建议先执行，你没有反对，随时可以改：
- "高风险"按第 3.4 节的建议定义。
- 只支持 Claude Code。claude.ai 和 Skills API 只接受规范里的 6 个字段，而本计划要用 `argument-hint`、`hooks` 这些 Claude Code 专有的字段。
- 成本同时报告 token 数和按 API 价格折算的美元，因为还不知道你用订阅还是 API 计费。

仍待定：
- AGV 的几个前端和后端是否在同一个工作区里，兄弟仓库是否都在本地。skill 第一次在多仓库项目里使用时会问（第 3.5 节）。

## 8 风险

- **没有触发。** 日常 prompt 只点名一处，只靠 description 时第三方测得的激活率是 50-55%，间接表述约 0%。对策：description 中英双语、先写场景；评测触发率；按评测结果决定触发类 hook 是否默认开启（第 3.6 节）。
- **候选太多。** 单词种子和样板代码会淹没清单，例如后端 149 个 gin handler 在 norm 指纹下聚成一簇。对策：单词种子限定范围，按分差排序，生成代码降权；签名通道"太泛"时只报告，不全列出。
- **10 万文件的资源。** 索引构建要 1-1.8 GB 内存，数字来自相同副本，真实仓库会更大。
- **权限拦截。** auto 模式会丢弃解释器通配的规则，skill 的 `allowed-tools` 是否同样被过滤还没实测；plan 模式下只能写计划文件。对策见第 3.1 节末尾和第 3.5 节。
- **样本单一。** 实测只来自 ThingsPanel：一个前端，后端几乎只有 Go；Python 和 Node 的应用代码还没测过。
- **评测成本和记忆污染。** 见第 5.3 节。

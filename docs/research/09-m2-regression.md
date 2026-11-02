# 09 M2 回归评测

日期 2026-10-31。M2 代码（[08](08-m2-channels.md)）上跑了两次全量回归，10 个用例各 3 次，`--ablation none`，Sonnet 5.5 high。两次之间代码没改。

| | 第 1 次 | 第 2 次 |
|---|---|---|
| 结果目录 | `evals/results/2026-10-30T18-28-31-862Z/` | `evals/results/2026-10-31T05-41-44-965Z/` |
| 总花费 | $66.90 | $72.48 |
| 调用了 skill | 29/30（last-visit-time 2/3） | 30/30 |

每次的逐站点表在各自目录的 `summary.md`。

## 1 召回

除 message-level-color 外，两次的 direct 站点全部改到，exclude 站点零误改，coupled 站点全部只列出、没有擅自改。

| 项目 | M0 基线 | M1 第 2 次 | M2 第 1 次 | M2 第 2 次 |
|---|---|---|---|---|
| 列表顶栏 R1-R7 | 10/21 | 18/21 | 21/21 | 21/21 |
| 天然同类 N1-N4（在最后的消息里提到） | 0/12 | 没测 | 12/12 | 12/12 |
| message-level-color 卡片 share-card | 0/3（不装） | 没测 | 3/3 | 3/3 |
| message-level-color 铃铛 notice-bell，按旧 grader | 0/3（不装） | 没测 | 2/3 | 0/3 |

M2 计划里的列表顶栏目标（≥ 18/21）和天然同类目标（≥ 8/12）都达到了。

## 2 铃铛的 0/3 是 grader 写错了

notice-bell 的三元链以 `: 'transparent'` 结尾。第 2 次的 3 次运行都在 success 分支后面插了 `item.level === 'info' ? '#2080f0'`，兜底的 `'transparent'` 留着给未知级别。这是对的改法，但旧 grader 要求文件里不再出现 `'transparent'`，所以判为没改。

用 trace 里的 Edit 在种植文件上重放：3 次都去掉了"success 之后直接落到 transparent"，都加了 `#2080f0`，卡片也都加了 info 项。第 1 次的 trace 已被清理，没法重放，它的 2/3 是改法不同（直接把 transparent 换掉）碰上了旧 grader。

已改 `evals/e1/message-level-color/sites.json` 并重新生成 graders：
- notice-bell：`gone` 改成 `'#18a058'\s*:\s*'transparent'`，也就是 info 不再落到兜底。
- share-card：删掉"`?? 'transparent'` 必须消失"那一条。兜底留给未知级别同样是对的，只检查 `info:` 项。

两次的 `summary.md` 是用当时打分的旧 grader 生成的。按新 grader，第 2 次的 message-level-color 是 9/9。

## 3 skill 触发

[08](08-m2-channels.md) 里 message-level-color 装了插件 0/3 调用 skill。description 加了"改某个状态、级别或类型的显示"后，两次都是 3/3。代理第一句话就说"改的是某个级别的显示颜色，其他组件可能映射了同样的值"。

## 4 成本

| | M1 第 2 次 | M2 第 1 次 | M2 第 2 次 |
|---|---|---|---|
| 平均每次（9 个旧用例） | $2.66 | $2.19 | $2.45 |
| message-level-color | | $2.57 | $2.11 |

两次 M2 之间相差 $0.26，同一用例最多差 $0.73（last-visit-time），说明单次之间波动不小。M2 比 M1 低，可能来自 M1 之后减少调用次数的改动，这一点没有单独测过。SKILL.md 变长后没有看到成本上涨。第 1 节的成本标准（≤ $2.10）还没达到。

## 5 其他观察

- 每次调用 cp.py，结果前面都有两行 `python3: error: couldn't create cache file .../xcrun_db-...`。这是 macOS 的 python3 包装程序在沙箱里写不了临时目录，不影响结果，但每次调用都多占一点上下文。
- 历史共变仍然测不出：评测仓库只有 1 个提交。

## 6 回归之后的减调用改动

按第 2 次的 30 条 trace 统计：平均每次 15.4 次模型调用，其中第一次 verify 之后还有 2.5 次；单独一次 `mark ... edited` 的调用共 34 次。上下文从约 26k 涨到 40-80k，没有缓存，每次调用都按全量计费。主要浪费在 verify 报的"问题"其实都是正常结果：

- 代理改完还要单独 `mark edited`。
- 改动写进去的新行（卡片新加的 `info:` 项、新的滚动容器）被报成"新出现的命中"。
- 改掉的行恰好被 `rest exclude` 归了 exclude（`background: transparent`），被报成"exclude 项被改了"。
- 改后代码上，func、like 这类排序通道把原来排在后面的文件排了上来（每次 8-17 个）。
- `mark rest review` 后 review 项还是 open，又被报成"还没处理"（list-header 一次 59 项）。

改动（`cp.py`、`cplib/show.py`）：
- scan 时为每项记下所在函数或样式规则的范围和校验和（`block`），并为每个文件记下行集合（`lines`）。
- verify 把块变了的 direct 项和 confirmed 项直接记为 edited；已改 direct 项块里的其他变动行（`rest` 归的 exclude 也算）一起记为 direct/edited；文件里原来没有的行，只要不是 value 或 sig 通道（这两个找的是旧写法）命中的，记为 direct/edited。"标了 edited 但没改"也改成按块判断。
- func、like、history 在复查时排上来的新候选不加入，只报个数。
- review 和 exclude 项分级时自动变成 listed。`mark` 加了 `--verify`，可以在同一次调用里复查。
- SKILL.md：不再要求代理自己标 edited。

用 message-level-color 第 2 次的一条 trace 重放（同样的分级和编辑）：原来的 verify 报 exclude 被改 2 项、新命中 1 项、未处理 3 项，需要再 mark 和 verify 一轮；现在一次通过。单元测试 41 个通过（新增 2 个）。按每次调用约 45k token 估算，每次运行可少 1.5-2 次调用，约 $0.2-0.3，要回归评测确认。

## 7 评测模型改成 claude-sonnet-5-5

第 6 节改完后的回归跑了三次，都在开头 10 秒内中止，单用例单并发也一样，报 `403 Upstream request failed; the attempt budget has ended`。`--model sonnet` 按本机 `ANTHROPIC_DEFAULT_SONNET_MODEL` 请求的是 `claude-sonnet-4-6`。用 `claude -p` 直接测：这个模型名的短请求 10/10 成功，3-5 万 token 的请求 12 次失败 5 次；同样大小换成 `claude-opus-4-8`、`claude-sonnet-4-5` 都成功。CLI 把 403 当认证错误不重试，评测每次运行要发 10-25 个请求，所以几乎每次都中止。

评测改用完整 ID `--model claude-sonnet-5-5`：5.4 万 token 的请求 5/5、两轮对话 6/6 成功。同一个 `claude -p` 的输入从约 2.75 万 token 降到约 2.1 万，CLI 对这个模型名发的系统提示和工具定义更短。所以之后的成本和轮次不能直接和 M0 到 M2 第 2 次比，要在同一模型上重跑对照组。

## 8 claude-sonnet-5-5 上的第 3 次回归（含对照组）

`--ablation with-without`，各 3 次，共 $41.39，结果在 `evals/results/2026-10-31T08-07-31-447Z/`。60 次里 3 次仍报 403（装插件的 alarm-level 2 次，不装的 action-value-dedupe 1 次），下表不算它们。

| 用例 | 装了插件 | 不装 |
|---|---|---|
| 列表顶栏 R1-R7 | 21/21 | 6/21 |
| 天然同类 N1-N4 | 12/12 提到 | 0/12 |
| message-level-color（卡片、铃铛） | 6/6 | 0/6 |
| popup-fade direct | 18/18 | 17/18 |
| 其余用例 direct | 全部改到 | 全部改到 |
| coupled 擅自修改 | 0 | e0-t1 9/9、super-admin 3/12 |
| exclude 误改 | 0 | 0 |

装了插件的组 30 次里 28 次有效，都调用了 skill。

成本：装了插件平均 $1.01/次、25.7 轮，不装 $0.45/次、18.0 轮，是对照组的 2.24 倍。计划第 1 节的标准是不超过 2 倍。

和第 2 次（`sonnet`）比，每次的模型调用从 15.4 降到 13.5，第一次 verify 之后的调用从 75 降到 43（30 次和 28 次合计），单独的 `mark edited` 从 33 降到 0。花费从 $2.42 降到 $1.01，大部分来自模型换了：第一次请求的上下文从约 26k 降到 16.5k。

verify 仍没一次通过的情况：

- list-header 1 次：表头在模板里，所在的块取不到（`block` 为空），同文件里 `rest review` 归的 sticky 样式行被改后报"coupled/review 项被改了"。代理又试了 3 次 mark（direct、exclude、direct/open）。已改：已改 direct 项没有块时，同文件里 `rest` 归级的变动行也算这次改动；direct 项状态是 listed 时 verify 也会自动记为 edited。新增 1 个单元测试，共 42 个通过。
- popup-fade 2 次、action-value 1 次：代理新写的共享样式或函数里带着旧值（`200ms`、`typeof JSON.parse`），value 通道报为新命中。合并重复实现时旧写法搬进新函数是正常的，但 verify 分不出来，暂不改。
- 其余是 direct 项确实还没改，或未分级的项，属于正常报告。

## 9 第 3 次之后的改动（还没评测）

按第 3 次 28 条有效 trace 看，代理在 seed 之前平均花 2-4 次调用定位文件（`pwd; ls`、`find`、Glob 找点名的文件），verify 通过后又花 1-2 次找检查命令（`ls node_modules; grep typecheck package.json`）。合并重复实现的用例里，旧写法搬进代理新建的共享函数，被 value 通道报成新命中，多出一轮。

改动：
- `seed` 的 `--file`、`--like`、`--func` 接受文件名或路径后缀（`notice-message.vue`），在根目录下按后缀匹配，唯一时直接用，重名时列出候选。SKILL.md 要求先 seed 再探索。
- verify 通过时列出每个包的检查脚本（package.json 里的 typecheck、lint、test，go.mod 的 build、vet、test），并说明有没有装依赖。脚本不运行它们。
- verify 把 git 里未跟踪、且第一次 scan 时还不存在的文件当作代理新建的，里面的旧值命中只列出、不算失败（记为 direct/edited，备注"新建文件里的行"）。
- 枚举通道加了按下标对应的数组：值数组（`['info', 'success', ...]`）20 行内同长度、不含这些值的数组（颜色表、ECharts `color`），报出改动值那一项。这对应你提过的"总览卡片按占比显色"可能用颜色数组的情况。ThingsPanel 原仓库上 3 组值都是 0 个命中，没有噪声。
- message-level-color 加了第 4 个 direct 站点 `level-pie`：总览页的 ECharts 环形图，`color` 数组按 `LEVEL_ORDER` 下标取色，info 是 `rgba(0, 0, 0, 0)`。离线 scan 把它排在前 10（70 分）。

单元测试 45 个通过（新增 3 个），lint 和 `validate --strict` 通过。SKILL.md 12.3 KB。

## 10 第 4 次回归（第 9 节的改动）

`claude-sonnet-5-5`，`--ablation with-without`，各 3 次，共 $42.07，结果在 `evals/results/2026-10-31T08-42-57-900Z/`。60 次里 1 次 403（不装的 popup-fade）。

| 项目 | 装了插件 | 不装 |
|---|---|---|
| 列表顶栏 R1-R7 | 21/21 | 10/21 |
| 天然同类 N1-N4 | 12/12 提到 | 0/12 |
| message-level-color（卡片、铃铛、环形图） | 9/9 | 0/9 |
| 其余 direct | 全部改到 | 全部改到 |
| coupled 擅自修改 | 0 | e0-t1 8/9、super-admin 3/12 |
| coupled 没提到 | 0 | status-online 3/9、super-admin 3/12 |
| exclude 误改 | 0 | 0 |

装了插件 30/30 调用了 skill。新加的环形图站点 level-pie 3/3 改到，不装 0/3。

成本：装了插件 $0.91/次、22.7 轮，不装 $0.51/次、18.3 轮，倍数 1.78，第一次满足计划第 1 节的"不超过 2 倍"。

| 每次运行平均 | 第 3 次 | 第 4 次 |
|---|---|---|
| 模型调用 | 13.5 | 12.6 |
| Skill 加载后到 seed 之前的调用 | 1.79 | 0.87 |
| 第一次 verify 之后的调用 | 1.54 | 0.30 |
| 装了插件的花费 | $1.01 | $0.91 |

不装的一组这次是 $0.51，比第 3 次高 $0.06，倍数下降有一部分来自对照组的波动。list-header 从 $1.91 降到 $1.32，是降得最多的用例。

## 11 历史共变：真实历史回放、评测里 git 没运行、改后复查同伴文件

### 11.1 评测里 git 一直没运行

第 2、3、4 次回归共 150 次运行的 trace 里，代理在 Bash 里跑了 62 次 git，62 次都报 `xcode-select: Failed to locate 'git'`。macOS 的 `/usr/bin/git` 是 xcrun 包装程序，在评测沙箱里找不到 git；cp.py 的 git 调用走的是同一个程序，同样失败，只是失败被吞掉了。所以到第 4 次为止，`.gitignore` 过滤（退回目录遍历）、`--diff`、历史共变和"新建文件里的旧值不算失败"在评测里都没生效：第 4 次有 7 次运行新建了文件，`新建文件里命中` 一次都没出现。

已改：`cplib/walk.py` 的 `git_exe()` 先试 PATH 里的 git，`git --version` 失败就换 Command Line Tools 里的 `/Library/Developer/CommandLineTools/usr/bin/git`（本机能用），所有 git 调用都走它。找不到能运行的 git 时，scan 的输出写明哪些通道没运行。CLT 里的 git 在评测沙箱里能不能运行，本机复现不了沙箱，要看下一次评测的输出。

### 11.2 在真实历史上回放

评测仓库的历史被 scaffold 折叠成了 1 个提交，所以从 GitHub 用 `--filter=blob:none` 拿了两个仓库的完整历史（前端 2,718 个提交，后端 2,902 个，只有提交和目录树，共约 40 MB），放在 `evals/.cache/history/`。`docs/research/measurements/cochange_backtest.py` 对最近 300 个提交逐个回放：提交里的每个文件轮流当种子，只用更早的提交算共变，看预测的文件是不是这个提交真的一起改了。

| 规则 | 前端：至少猜中 1 个 | 前端：准确率 | 后端：至少猜中 1 个 | 后端：准确率 |
|---|---|---|---|---|
| 至少 2 次、至少 30%（原规则） | 39% | 38% | 26% | 36% |
| 同上，每个种子只留前 5 个（现规则） | 39% | 42% | 26% | 41% |
| 至少 3 次、至少 50% | 24% | 59% | 16% | 42% |
| 原规则加反向（B 很少离开 A 单独改） | 40% | 34% | 28% | 33% |

按提交里的文件数算召回只有 7-9%，大部分一起改的文件没有足够历史。准确率四成左右，所以共变只能当弱信号：scan 列出来，读块之后再分级。反向规则多猜的基本是错的，没有采用。`git log` 去掉了改名检测（`--no-renames`），否则在 2.6k 个提交上要几分钟。

`cochange_candidates.py` 再看猜对的伙伴和种子有没有文本联系（互相提到名字、同目录、中英文语言包）：前端 343 个猜对的里 84 个（24%）没有，后端 165 个里 34 个（21%）。例子：路由表和生成的路由类型声明；场景编辑页 `scene-edit/index.vue` 和联动编辑的动作模块 `linkage-edit/modules/edit-action.vue`（14 次里 10 次一起改，两份代码是复制出来的）；告警配置表和场景管理表（`83383dd2` "align alarm and scene management tables"，正是统一同类表格的改动）；后端 `model/users.http.go`、`service/sys_user.go`、`api/sys_user.go`。

### 11.3 改后复查同伴文件（residue）

上游修复 `6148ea97`（2026-10-27）修了场景编辑页的占位符"如：undefined"，联动编辑动作模块里同样的三行一起修了；那三行和场景编辑页的不完全一样，结尾多一个 `|| '--'`。只改场景编辑页，原来的 `--diff` 能匹配到，但代理很少给 `--diff`，名字和值通道也不会去找这一行。

新增 `history.residue()`，每次 scan 和 verify 都运行，不需要种子：取未提交改动删掉的每一行（至少 6 个记号，不是 import），在被改的文件本身和它前 5 个共变伙伴里找几乎一样的行。条件是名字最多差一个，并且在改动改过的位置上仍然更像旧写法：所以 `… + instructItem.placeholder || '--'` 算旧写法，换了别的修法（`?? []` 代替 `|| []`）或已经同样修过的副本不算。在语料里出现超过 4 个文件的行当套话跳过。第一次 scan 时就已经有改动、之后没变的文件不当作这次的改动。同一个文件里一样的几行合成一项，说明里列出行号；只改了其中一部分时，verify 报"旧写法那一行还在"。

在 `182132e3`（修复的父提交）上重放：scan 把 edit-action.vue 列为共变伙伴（10/14，71%）；只改场景编辑页后 verify 报出 edit-action.vue 第 670、678、705 行；只改其中一行时报"旧写法那一行还在"；三行都改后复查通过。message-level-color 的重放没有多出 residue 命中。

### 11.4 新用例 e1/action-placeholder

前端用真实历史（`setup_history_repo` 只克隆 `case/action-placeholder` 分支，即 `182132e3` 及之前，修复提交不在仓库里），后端同其他用例。prompt 只点名场景编辑页。站点：

- scene-edit（direct）：三处 `'：' + instructItem.placeholder"` 不再出现。
- edit-action（coupled）：同一个 bug 的副本。用户没说"类似的也改"，按规则要先问；评测里不能问，看最后的消息有没有提到它，改了算擅自修改。

其他改动：verify 的"还没处理"不再重复列出刚报过的新命中；SKILL.md 的 `--file` 和 verify 两条写明了共变和 residue。单元测试 51 个通过（新增 6 个：git 回退、residue 找到同文件和伙伴里的副本、同样修过的不报、`--` 开头的删除行、不把任务前的改动当改动、工作区下的多个仓库）。

## 12 第 5 次回归（第 11 节的改动，含 e1/action-placeholder）

`claude-sonnet-5-5`，`--ablation with-without`，11 个用例各 3 次，共 $43.39，结果在 `evals/results/2026-10-31T12-24-00-303Z/`。66 次运行没有一次 403。

| 项目 | 装了插件 | 不装 |
|---|---|---|
| 列表顶栏 R1-R7 | 21/21 | 8/21 |
| 天然同类 N1-N4（提到） | 12/12 | 0/12 |
| message-level-color（卡片、铃铛、环形图） | 9/9 | 0/9 |
| action-placeholder：scene-edit 改了 | 3/3 | 3/3 |
| action-placeholder：edit-action 提到 | 3/3 | 0/3 |
| alarm-level、status-online-text 的 direct | 2/3、2/3 | 3/3、3/3 |
| coupled 擅自修改 | 0 | e0-t1 8/9、e0-t3 1/6、super-admin 3/12 |
| exclude 误改 | 0 | popup-fade 1 次 |
| 平均每次 | $0.85，21.9 轮 | $0.46，17.7 轮 |

倍数 1.85。action-placeholder 装了插件只有 1/3 调用了 skill，没调用的 2 次也搜了 `common.as` 并提到了 edit-action，不装的 3 次只在场景编辑页里搜。

### 12.1 git 在评测里仍然没运行

装了插件的 34 次 scan 都报"找不到能运行的 git"。评测设置里 `sandbox.credentials.files` 屏蔽了 git 的凭据助手（`git-credential-store` 等），它们是指向 `/Library/Developer/CommandLineTools/usr/bin/git` 的链接，所以 git 本体也读不到；`/usr/bin/git` 包装程序因此报 "Failed to locate 'git'"。这次的历史共变和 residue 都没有运行。

这个屏蔽是为了保护凭据，所以不去绕过它运行 git，改为新增 `cplib/gitread.py`，直接读 `.git`：refs、packed-refs、松散对象和 v2 pack（含 offset 和 reference delta）、HEAD 的目录树，以及历史共变需要的每个提交改了哪些文件（按 git 默认的历史简化处理 merge）、工作区相对 HEAD 的改动（用 difflib 算行级差异）和未跟踪文件。git 能运行时仍用 git。macOS 上不再运行 `/usr/bin/git` 包装程序，改为直接找开发者目录里的 git。

和 git 对比（`docs/research/measurements/gitread_check.py`）：两个仓库的 HEAD 文件列表相同；前端、后端各取 40 个文件，`git log --no-merges --no-renames --full-diff --name-only -n 3000` 的结果完全相同，gitread 用时约为 git 的 0.6 倍；在前端仓库改 5 个文件、删 1 个后，改动文件和删除、新增的行与 `git diff -U0` 相同。新增 4 个单元测试（松散对象、offset delta、reference delta、工作区改动）；把 git 关掉后整套单元测试也通过。在 action-placeholder 和 message-level-color 上关掉 git 重放：共变、residue、新建文件判断的输出和有 git 时相同。

### 12.2 装了插件的代理把插件目录当成项目

装了插件的 33 次里有 6 次用 `/Users/yezhoufan/VScodeProjects/change-propagation/...` 读文件或搜索，都被评测沙箱拒绝。代理加载 skill 时看到 "Base directory for this skill: …/change-propagation/skills/change-propagation"，cp.py 的输出又都是相对路径，就把插件目录当成了项目根。其中 2 次因此没改成 direct 站点，就是上表 alarm-level 和 status-online-text 的 2/3。不装插件的组没有这个问题。

已改：SKILL.md 写明 `${CLAUDE_SKILL_DIR}` 只放脚本，项目是当前目录；`seed` 输出一行 `工作区：<绝对路径>（输出里的路径都相对于它）`。

单元测试 55 个通过（新增 4 个），SKILL.md 12.7 KB，lint 和 `validate --strict` 通过。

## 13 第 6 次回归（gitread，两遍）

同一命令跑了两遍：`2026-10-31T13-52-11-023Z`（$45.34，66 次无出错）和 `2026-10-31T14-23-52-563Z`（$40.75，super-admin 有 4 次 403 "attempt budget has ended"：不装 3 次、装了 1 次）。

| 项目 | 装了插件 | 不装 |
|---|---|---|
| 列表顶栏 R1-R7 | 21/21、21/21 | 9/21、13/21 |
| 天然同类 N1-N4（提到） | 12/12、12/12 | 0/12、0/12 |
| message-level-color direct | 12/12、12/12 | 3/12、3/12 |
| action-placeholder：edit-action 提到 | 3/3、3/3 | 0/3、0/3 |
| action-placeholder：调用了 skill | 1/3、0/3 | — |
| alarm-level、status-online-text 的 direct | 3/3、3/3 | 3/3、3/3 |
| coupled 擅自修改 | 0、0 | e0-t1 6/9、7/9，super-admin 3/12、— |
| 平均每次 | $0.89、$0.84 | $0.48、$0.46 |

两遍都是 1.83 倍。装了插件的代理不再因为插件目录改不成 direct 站点（第 1 遍 1 次、第 2 遍 4 次去插件目录读或搜，都很快回到工作区）。

### 13.1 git 通道看的是 home 目录的仓库

gitread 在每次 scan 都运行了（输出里有"直接读 .git"的提示），但 history 一次都没命中，residue 只在代理加了 `--root thingspanel-frontend-community` 的那次命中。原因：评测沙箱的 home 目录（工作区 `home/cwd` 的上一级）有一个 `.git`。`base_dir` 取当前目录往上最近的仓库，于是 ledger、根目录和所有 git 通道都落在 home 的仓库上，它没有 ThingsPanel 的历史；输出路径也都带着 `cwd/` 前缀，相对于 home。e0 用例的工作区本身是仓库，不受影响。

连带的失败：第 1 遍 `add` 6 次报"读不到 cwd/…"（代理在 `home/cwd` 里，照抄了带前缀的路径）；两遍共 7 次"还没有 ledger"（代理先 `cd` 进了某个仓库，`base_dir` 改成那个仓库，找不到 ledger）。

已改：
- 当前目录在 git 外，或下面一两层有仓库（多仓库工作区）时，新 ledger 放在当前目录，即使上层还有仓库；`history.repos` 同样把这样的根目录当成下面几个仓库的工作区。
- `seed` 之后的命令从当前目录往上找 ledger，`cd` 进子目录后也能用；`add` 的路径可以照抄输出（相对于工作区）、相对于当前目录，或只写文件名后缀。
- declared 反向匹配：同名文件超过 3 个（`index.vue`）时要连目录一起出现（`scene-edit/index`）。之前 7 次 seed 了 `index.vue` 的 scan 都报了 `docs/table-standard-audit-and-replacement-plan.md:193`，这行写的是 `system-log/index.vue`。
- SKILL.md 开头写明项目是当前目录、不要搜 skill 目录（原来在 Commands 一节里）。

按评测的目录结构重放（home 是一个 git 仓库，下面 `cwd` 里放两个 ThingsPanel 仓库，关掉 git）：`seed` 的工作区是 `home/cwd`；scan 列出 edit-action.vue 是共变文件（14 次里 10 次）；改好场景编辑页的三行后，在 `thingspanel-frontend-community/src/views` 里运行 verify，报出 edit-action.vue 第 670、678、705 行的旧写法；在这个子目录里照抄输出路径 `add` 成功；declared 的误报没了。

单元测试 59 个通过（新增 4 个：子目录里的命令、上层还有仓库的工作区两个、declared 同名文件），关掉 git 后 test_cp 也通过；SKILL.md 12.8 KB，lint 通过。

### 13.2 第 7 次回归（只跑 e1，确认第 13 节的三处修复）

`2026-11-02T08-50-41-593Z`，8 个 e1 用例各 3 次，共 $34.32，48 次零出错，倍数 1.49。三处目标问题都确认修好：工作区都显示为 `home/cwd`、根目录 `.`（下面两个 ThingsPanel 仓库被正确当成工作区）；路径前缀和"还没有 ledger"失败 0 次（上次两遍共 13 次）；declared 文档误报 0 次（上次 7 次）；进插件目录被拒 2 次（上次 6 次），不影响结果。

历史共变/residue 在本轮仍未命中：e1 里只有 action-placeholder 用带真实历史的仓库，其余都是单提交克隆（共变本就无内容），而 action-placeholder 这 3 次都没调用 skill（代理当成普通小 bug，直接 Grep+Edit 改完，仍在结论里提到了 edit-action.vue 的三行，say grader 3/3）。所以共变/residue 目前只有重放和单测验证。

触发问题：把 SKILL.md 的 description 第一条触发条件从"命名一处但别处有类似对象"扩成"修某个组件、页面、处理函数或提示文案的 bug，别处可能有同样的副本"，让 action-placeholder 这类普通 bug 修复也落进触发面；是否提高调用率要看下一次评测。

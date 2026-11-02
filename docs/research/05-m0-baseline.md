# 05 M0 基线：不用 skill 时漏在哪里

日期 2026-10-30。9 个用例各跑 3 次，共 27 次，全部没有出错。原始结果在 `evals/results/2026-10-30T14-50-52-595Z/`（已 gitignore）：`baseline.json` 是 harness 的输出，`baseline-rescored.json` 是按下文修正 grader 后重新计分的版本，`summary.md` 是 `evals/tools/summarize.py` 的完整输出。

## 1 运行条件

| 项 | 值 |
|---|---|
| 命令 | `CLAUDE_CODE_EFFORT_LEVEL=high claude plugin eval . --case 'e*' --ablation none --runs 3 -j 4 --model sonnet --scaffold --trust-plugin --no-publish --keep-temp --allow-tools Bash Edit Write` |
| Claude Code | 2.1.309，每次运行都是 dontAsk |
| 模型 | trace 的 init 事件是 `claude-sonnet-4-6`，即 Sonnet 5.5 |
| effort | 设了 high，但没能验证。trace 里没有 effort 字段，`per_turn_effort_active` 为 false |
| 插件 | 装了，skill 是 M0 的占位（`disable-model-invocation: true`），代理没有调用它 |
| 时长和成本 | 墙钟 461 秒；$28.64，平均每次 $1.06（E0 $0.83，E1 $1.18） |
| 轮数 | 每次 5-35 轮，远低于上限（E0 80、E1 150） |

## 2 跑完后修正的 grader

看过 trace 后改了 4 处判分，都是 grader 本身的问题，代理的做法没错。修正已经写回 `sites.json` 并重新生成 graders。harness 存下的分数不会变，所以用 trace 离线重算，写进 `baseline-rescored.json`。保留的工作区是密封的（mode 000），我没有打开，重算依据的是 trace 里的编辑和最后一条消息。

- **T1 的 i18n：** 原来检查"至少 8 位"已经消失。第 1 次运行新加了 `auth.registerPasswordHint`（12 位），旧的 hint 留给重置表单，这是对的。改成检查"12 位"出现，三次都通过。
- **T3 的服务端两份副本：** 原来是 direct。代理三次都没改，理由是 web 和 server 是两个 workspace 包，合并要新建共享包；`toDay` 用的是 UTC，改了会移动日报的分组边界。按第 3 节第 5 步的分级，副本只到 coupled。改为 coupled 并加了 mention。
- **alarm-level 和 status-online-text 的副本：** 原来是 direct，同样改为 coupled。
- **last-visit-time 的 `api.d.ts`：** 原来是 coupled。读的字段改名后，类型检查必须跟着改，按定义属于 direct。

## 3 结果

站点状态：**改了**（文件里有改动），**只提到**（没改，但最后一条消息点名了这个位置），**漏掉**（两样都没有）。exclude 站点只看有没有被误改。

| 用例 | 站点数 | 改了 | 只提到 | 漏掉 | exclude 误改 | 平均成本 |
|---|---|---|---|---|---|---|
| E0 T1 密码长度 | 8 | 17 | 6 | 1 | - | $0.77 |
| E0 T2 弹窗淡入 | 9（1 个 exclude） | 19 | 3 | 2 | 0/3 | $0.82 |
| E0 T3 日期去重 | 7（1 个 exclude） | 9 | 9 | 0 | 0/3 | $0.90 |
| E1 告警级别副本 | 2 | 3 | 3 | 0 | - | $0.40 |
| E1 在线文案副本 | 4 | 3 | 9 | 0 | - | $0.90 |
| E1 最后访问时间 | 4（2 个 exclude） | 6 | 0 | 0 | 0/6 | $1.23 |
| E1 动作值校验去重 | 3 | 7 | 2 | 0 | - | $1.54 |
| E1 超管密码 | 5 | 7 | 5 | 3 | - | $1.43 |
| E1 列表顶栏（种植） | 11（4 个诱饵） | 10 | 0 | 11 | 0/12 | $1.56 |

（每格是 3 次运行累加的站点次数。）

合计，不含 exclude：E0 66 个站点次中改了 45、只提到 18、漏掉 3；E1 69 个中改了 36、只提到 19、漏掉 14。漏掉的 14 个里有 11 个在列表顶栏用例。exclude 站点 24 次全部没被误改。

各位置的明细：

- **列表顶栏（你的真实场景）：** R1（prompt 点名的场景部署列表）、R5、R7 三次都改了；R6 改了 1 次；R2、R3、R4 三次都没改，最后的消息里也没提。原仓库里 4 个天然同类（`data-table-page`、设备配置、设备模板、分组）一次都没被碰过，也没被提到。三次运行找同类的方式一样：grep 自己修复时看到的写法，`position: sticky`、`__header|__body`、`overflow`。找到的 R5、R7、R6 都写了 `position: sticky`（R6 嵌在 SCSS 嵌套里，只找到 1 次）。R3 用 UnoCSS 的 `sticky` 类，不含 `position:`；R2 用 `__head` 和 `__scroll`，没有 sticky；R4 包在 `n-scrollbar` 里，也没有 sticky。这三个一次都没找到。这和计划第 1 节的判断一致，靠名字和单一写法搜不全，要按结构找。
- **超管密码：** 前端 locale 里的 `form.pwd.tip`（"密码长度不能小于6位"）三次都漏，既没改也没提。后端 `password_utils.go` 三次都只提到；`users.http.go` 的 `min=6` 三次都直接改了。
- **T2：** 写在 `CheckoutPage.tsx` 里的内联地址选择层 3 次只改了 1 次，没改的两次也没提。
- **T1：** `passwordStrength.ts` 的 `>= 8` 3 次里漏了 1 次。
- **逐字相同的副本（告警级别、在线文案）：** 三次都找到了，都没改，最后的消息里逐个列出路径和行号，并说明"因为你只提到了这个文件"。
- **漂移说明：** T3 三次都指出了副本行为不同（月份少 1、不补零、UTC）；动作值校验只有 1 次指出 scene-edit 校验 4 种类型、edit-action 只校验 `command`。

## 4 结论

- **漏改集中在写法不同的近似对象上。** 写法相同时，Sonnet 能找到同类：逐字相同的副本 12 次全找到，同一套 `position: sticky` 写法的列表也找到了。漏掉的是写法变了的那一类：列表顶栏的 R2、R3、R4 和 4 个天然同类、locale 里的提示文案、内联在页面里的弹层。这正是 M2 特征卡和 SFC 结构查询要解决的。
- **找到但不改，是基线的默认做法，不是漏改。** 副本和跨层规则多数被列进最后的消息，附理由（"你只提到了这个文件"、"要新建共享包"、"UTC 会移动日报边界"）。在 dontAsk 下这符合计划的分级：coupled 应该列出而不是擅自改。所以 coupled 站点不能用"改了"算召回，要用"改了或提到"算。
- **擅自改共享规则仍然发生。** T1 有 2 次直接改了 `server/src/validators/user.ts`，这条规则注册和重置密码共用；超管密码 3 次都直接改了后端 `users.http.go`。按计划这些都要先问。试点的 2/3 在这里复现了。
- **没有误改。** 24 个 exclude 站点次全部保持原样。精度不是基线的问题。
- **成本低。** 平均每次 $1.06、5-35 轮，代理普遍在找到第一批同类后就停了，没有用满轮数。

## 5 由此定下的 M1、M2 目标值

按位置计，基线数字取上面的 3 次累加：

| 指标 | 基线 | 目标 | 里程碑 |
|---|---|---|---|
| E1 direct 和 coupled 的召回（direct 改了，coupled 改了或提到） | 52/66（79%）；不含列表顶栏 42/45（93%） | 不含列表顶栏 45/45 | M1 |
| 超管密码 locale 文案 | 0/3 | 3/3 | M1（非代码通道） |
| 列表顶栏 R1-R7 的召回（改了） | 10/21（48%） | ≥ 18/21（86%） | M2 |
| 列表顶栏的天然同类（改了或提到） | 0/12 | ≥ 8/12 | M2 |
| coupled 位置未经确认就被编辑 | E0 5/15，E1 4/24 | 0 | M1 |
| exclude 误改 | 0/24 | 0/24 | 每个里程碑 |
| 每次成本 | $1.06 | ≤ $2.10（基线的 2 倍） | M1 |

E1 的召回分母是 direct 42 加 coupled 24 个站点次（`api.d.ts` 已改成 direct）。direct 漏掉的 11 次全在列表顶栏；coupled 漏掉的 3 次是 locale 文案。列表顶栏单独算，因为它要等 M2 的结构查询。

## 6 已知局限

- 每个用例只有 3 次，单个站点 0/3 和 1/3 之间的差别不显著。
- effort 是否为 high 没能确认。
- T2 只检查组件文件本身。如果代理通过共享样式表的选择器加动画，grader 会判"没改"。这次 6 个弹窗都是在组件里加 class，没碰到这个问题。
- 天然同类没有 grader，"0/12" 是我从 trace 的编辑记录和最后一条消息里查的。M2 之前要给它们补上 grader。
- E0 和 E1 的 prompt 都不含"找全"之类的提示，所以触发率没有测。M3 再测。

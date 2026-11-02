# 08 M2 近似对象通道：实现和离线测量

日期 2026-10-31。M2 的五个通道都已实现，还没跑评测。本文记录做了什么、在 ThingsPanel 和 shopfront 上离线测到什么，以及 message-level-color 用例的第一次评测。

## 1 message-level-color 第一次评测

`--ablation with-without`，各 3 次，共 $2.87。结果在 `evals/results/2026-10-30T17-37-44-249Z/mlc.json`（已 gitignore）。

| 站点 | 装了插件 | 不装 |
|---|---|---|
| notice-message（点名的组件） | 3/3 改了 | 3/3 |
| share-card（总览卡片，缺 info 走兜底） | 0/3 改了，1 次在最后的消息里提到 | 0/3，没提 |
| notice-bell（顶栏铃铛，三元链兜底） | 0/3 | 0/3 |
| log-line（诱饵） | 3/3 没动 | 3/3 |

装了插件的 3 次都没有调用 skill。prompt 是"提示消息改成蓝色"，description 里没有对应的场景，代理当成单文件改动直接做了。有 1 次自己搜到了卡片，但把它列为"要我改吗"。

已改：description 加了"改某个状态、级别或类型的显示（颜色、图标、文案）时，其他卡片、徽标和图表也映射同一组值（提示消息改成蓝色、某个状态换颜色）"。触发率在 M2 回归时一起测。

## 2 新通道

| 通道 | 种子 | 实现 | 离线测量 |
|---|---|---|---|
| 结构查询 | `--layout header-in-scroll` | `cplib/sfc.py` 读模板树（html.parser）和样式块（解析 SCSS 嵌套），加上工具类和内联样式；`cplib/layout.py` 找"顶栏是纵向滚动容器的第一个子元素、后面紧跟重复行"，跟一跳进子组件，并列出放进滚动容器或滚动插槽的表格组件 | 种植后的 ThingsPanel：R1-R7 全部找到（R5 经子组件 `RoleUserListHeader`），4 个诱饵都没报；干净仓库上报出 4 个天然同类（`data-table-page`、设备配置、设备模板、分组），也就是 05 里 0/12 的那 4 个。812 个文件约 1 s |
| 特征卡 | `--like 样例` | `layout.like_channel`：从样例和它导入的样式表取标签、类名词、`position: fixed`、`z-index`、`createPortal`、`mask` 等，按共有的稀有特征给其他前端文件排序 | shopfront 上以 `Modal.tsx` 为样例：5 个应改的弹窗（含命令式 DOM 弹层和页面里的内联弹层）和 drawer 排在前 6，toast 第 7，tooltip 不在列表里 |
| 函数指纹 | `--func 路径:函数名` | `cplib/shingle.py`：从 `measurements/shingle_index.py` 改写，标识符、字符串、数字归一化后取 winnowing 指纹，按包含度排序，候选比查询大得多时降分 | ThingsPanel 前后端 2.3k 文件约 6 s：`actionValueChange` 的分叉副本第 1 名（90%），`normalizeAlarmLevel` 的副本第 1 名（87%）；第 2 名以后基本是噪声 |
| 修复签名 | `--diff` | `cplib/history.py`：未提交 diff 里删掉的行，局部标识符抽象成通配，member 名和字面量保留，在全仓找还带旧写法的行；命中超过 20 行报"太泛"；单条 CSS 声明跳过 | 模拟修改 scene-edit 的 JSON 校验后，找到 `edit-action.vue:354` 的同一旧写法，只有这 1 处 |
| 历史共变 | `--file` | 同上：和种子文件在至少 2 次、至少 30% 的提交里一起改过的文件；超过 30 个文件的提交忽略 | 评测用的仓库都只有 1 个提交（scaffold 折叠了历史），本机也没有带历史的克隆，只在单元测试里验证过 |

`seed` 的分级规则和用法写进了 SKILL.md 的"按改动类型选种子"和 `references/channels.md`。单元测试 39 个通过，lint 和 `validate --strict` 通过。

## 3 已知局限

- 结构查询只有 header-in-scroll 一种。别的布局改动仍要代理自己写特征卡去搜。
- 模板用 render 函数或 TSX 写的组件读不到结构。
- 历史共变在评测里测不出效果，因为 scaffold 把历史折叠成了一个提交。要测得换成保留历史的用例。
- SKILL.md 从约 10.6 KB 涨到 11.6 KB，每次调用都带着，对成本不利。
- 函数指纹只对排第 1、2 的候选可靠。

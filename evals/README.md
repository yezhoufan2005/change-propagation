# evals

`claude plugin eval` 用例。M0 只跑了不带 skill 的基线（`--ablation none`）；M1 起用 `--ablation with-without` 做有无对比。

## 用例

| 目录 | 内容 | 仓库 |
|---|---|---|
| `e0/t1-password-length` | 注册表单密码最小长度 8 改 12（需求耦合） | `fixtures/shopfront`（40 个文件） |
| `e0/t2-popup-fade` | 所有弹窗加淡入动画（同类组件散落） | 同上 |
| `e0/t3-date-dedupe` | 重复的日期格式化抽成公共函数（重复实现） | 同上 |
| `e1/alarm-level` | 一处 `normalizeAlarmLevel` 补 H/M/L，另一份完全相同的副本 | ThingsPanel 前端 + 后端 |
| `e1/status-online-text` | WebSocket 在线文案写死中文，四处相同写法 | 同上 |
| `e1/last-visit-time` | 前端读驼峰字段、后端写下划线字段（契约两端） | 同上 |
| `e1/action-value-dedupe` | 两份已经分叉的 JSON 校验函数抽取 | 同上 |
| `e1/super-admin-password` | 前端密码最短长度 6 改 8，后端三处各写一遍 | 同上 |
| `e1/list-header-scroll` | 种入的同类列表：灰色表头被滚动条盖住 | 同上，加 `plant/` 覆盖文件 |
| `e1/message-level-color` | info 提示消息由无色改蓝色；总览卡片按占比取色、顶栏铃铛各有一张缺 info 的映射表，日志级别是诱饵 | 同上，加 `plant/` 覆盖文件 |
| `e1/action-placeholder` | 真实 bug：场景编辑页占位符显示「如：undefined」；联动编辑的动作模块有同样的三行（多一个 `\|\| '--'`），过去 14 次改场景编辑页有 10 次一起改了它。上游修复 6148ea97 两处都改了 | 前端带真实提交历史（`setup_history_repo`），后端同上 |

每个用例目录：`case.yaml`、`prompt.md`（用户口吻，不含"找全"提示）、`scaffold.sh`、`sites.json`（位置清单和分级，代理看不到）、`graders/`（由 `sites.json` 生成，不手改）。

## 准备

- ThingsPanel 两个仓库放在 `.cache/repos/`（已 gitignore）：从本地克隆，去掉 origin，不含 `prompt.md` 或 `case.yaml`。
- 带历史的用例用 `.cache/history/`（已 gitignore）：从 GitHub `git clone --filter=blob:none` 拿完整提交历史（只有提交和目录树，前端约 30 MB），在修复提交的父提交上建分支 `case/<用例名>`，并设 `git config uploadpack.allowFilter true`。scaffold 的 `setup_history_repo` 只克隆这个分支，去掉 remote 和 reflog，所以修复提交和之后的历史不在评测仓库里；旧提交的文件内容也不在，`git log --name-only` 能用，`git log -p` 看不到旧内容。
- 种入的文件放在用例的 `plant/<仓库名>/` 下。scaffold 克隆后把它们覆盖进去，再并入唯一的根提交（保留原作者和日期），所以 `git status`、`git log` 看不出哪些文件是后加的。
- 修改 `sites.json` 后重新生成 graders：`python3 -I evals/tools/gen_graders.py evals/e0/t1-password-length ...`

## grader 命名与计分

| 前缀 | 含义 | 权重 |
|---|---|---|
| `edit-<站点>` | 文件里旧写法已消失，或新写法已出现（改了） | direct 为 1，其余 0.001 |
| `keep-<站点>` | 文件里旧写法仍在（没误改），用于 exclude 站点 | 1 |
| `say-<站点>` | 最终回复提到了这个位置 | 0.001 |
| `used-skill` | 调用了 change-propagation skill（`tool_used: Skill`，两组对比时不计分） | 0.001 |

权重 0.001 的 grader 只做记录：用例分数基本等于"direct 位置改全且没误改 exclude 位置"，coupled 和 review 位置的"改了/只提到/漏掉"由 summarize 脚本按这些 grader 统计。同一站点有多个文件时，任一 `edit-` 通过就算改了。

## 运行

评测代理需要 Bash、Edit、Write，按 `--allow-tools` 授予。用例的 `allowed_tools` 要列出 `Skill`，否则装了插件的组也调用不了 skill。评测模型是 Sonnet 5.5，写完整 ID `--model claude-sonnet-5-5`，effort high。不要用别名 `sonnet`：本机配置把它映射到 `claude-sonnet-4-6`，2026-10-31 中转在这个模型名上大请求时断时续返回 403（见 [09](../docs/research/09-m2-regression.md) 第 7 节）。M0 到 M2 第 2 次的结果都是在 `sonnet` 上测的：

```bash
CLAUDE_CODE_EFFORT_LEVEL=high claude plugin eval . \
  --case 'e0-t1*' --ablation none --runs 1 --model claude-sonnet-5-5 \
  --scaffold --trust-plugin --no-publish --keep-temp \
  --allow-tools Bash Edit Write --json /tmp/cp-smoke-t1.json
```

正式基线把 `--case` 换成 `'e*'`，`--runs 3 -j 4`。结果在 `evals/results/<时间戳>/`（已 gitignore）。保留的临时目录权限是 000，不能直接进去，要看文件用 `--keep-temp` 报告里的路径另行复制。

## 汇总

`python3 -I evals/tools/summarize.py <结果.json> [--md 输出.md]`：按站点统计"改了 / 只提到 / 漏掉 / 没误改 / 误改"，并给出核心分、轮数和单次成本。用例总分里的 `passed: false` 是因为 0.001 权重的记录项没全过（阈值 1），不代表失败，看站点统计。

trace 在 `--keep-temp` 报告的目录下 `out/trace.jsonl`（权限正常，可读）；`init` 事件里有实际模型 ID，工具调用在 `assistant` 事件的 `tool_use` 块里。

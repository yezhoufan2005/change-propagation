# 调研原型

调研 agent 在 2026-10-30 写的一次性脚本。它们是测量和验证用的原型，没有审阅过，也不是产品代码。M1、M2 实现对应的通道时可以参考；报告里引用的 `/tmp/...` 路径都对应到这里。都只用 Python 标准库，只在本地调用 `git` 和 `grep`，不联网。

| 目录 | 原路径 | 内容 | 引用它的报告 |
|---|---|---|---|
| `variant-history/` | `/tmp/va-scripts/` | 从 git 历史挖改动片段并按抽象后的改动分组（`mine.py`、`groups.py`），用第一次修复的签名去找后来又修的位置（`detect.py`、`summ.py`），共用的分词和抽象（`vtok.py`） | 03 第 2.4 节的 Go 历史重放、Vue 历史统计 |
| `contract-map/` | `/tmp/cp-contracts/` | 契约图原型（`cmap.py`：名字变体、改名和 filter 各跟一跳、MQTT 配对）、规则检查（`proto.py`）、分级（`tier.py`），以及 10 个文件的三栈 fixture | 03 第 2.2、4 节 |
| `neardup/` | `/tmp/cp_scripts/` | 近似重复函数查找（`neardup.py`、`neardup2.py`），合并后查残留（`verify_after.py`） | 01 的本地证据 |
| `cochange/` | `/tmp/cp-scripts/` | TARMAQ 式的历史共变推荐和留一法评估（`cochange.py`） | 01 第 3.2 节 |
| `hooks-sim/` | `/tmp/cp-gap1/` | 用编辑内容当查询，模拟 PostToolUse hook（`sim.py`）；空 hook 的耗时测量（`noop_hook.py`） | 01 第 6.5、8.2 节 |
| `declared-coupling/` | `/tmp/cp-gap2/scripts/` | 扫描"keep in sync"类注释（`sync_scan.py`）、前后端共用的字符串（`shared_literals.py`）、注释里路径指针是否失效（`path_rot.py`） | 01 第 8.1 节第 3、6 条 |

`docs/research/measurements/` 里是另一批：主会话和测量子代理写的规模测量脚本，见 04。

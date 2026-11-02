# change-propagation

Claude Code 插件。改动只点名了一处时，帮 agent 找全同样要改的其他位置：名字不同的同类组件、复制后分叉的副本、JSON 字段和 MQTT topic、WebSocket 事件的另一端、同一条规则在其他层的实现。找到的位置按分级处理：直接命中的改，推断出的耦合先问你再改，低可信的只列出。

## 状态

tier 0 脚本：M1 的名字、值和规则、契约、声明式耦合、枚举映射，M2 的结构查询、特征卡、函数指纹、修复签名、历史共变、ledger、带确认和复查的 SKILL.md。评测结果见 [docs/research/09-m2-regression.md](docs/research/09-m2-regression.md)。M0 基线见 [docs/research/05-m0-baseline.md](docs/research/05-m0-baseline.md)，计划见 [docs/plan.md](docs/plan.md)。

## 目录

| 路径 | 内容 |
|---|---|
| `.claude-plugin/plugin.json` | 插件清单 |
| `skills/change-propagation/` | skill 本体：`SKILL.md`、`references/`、`scripts/cp.py` 和 `scripts/cplib/` |
| `tools/lint_skill.py` | SKILL.md 的 lint，`claude plugin validate --strict` 查不出的规则都在这里 |
| `tests/` | lint 和 `cp.py` 的单元测试 |
| `evals/` | `claude plugin eval` 用例：E0（40 文件的小仓库）和 E1（ThingsPanel），说明见 [evals/README.md](evals/README.md) |
| `docs/` | 计划和调研 |

## 开发

```bash
claude plugin validate --strict .
python3 tools/lint_skill.py
python3 -m unittest discover -s tests
claude --plugin-dir .            # 本地加载插件
```

评测的准备和运行步骤见 [evals/README.md](evals/README.md)。

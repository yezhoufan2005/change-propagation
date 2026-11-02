---
allowed_tools: [Read, Glob, Grep, Edit, Write, Bash, Agent, TodoWrite, Skill]
max_turns: 150
timeout_seconds: 2400
---

自动化模块里动作值的 JSON 校验逻辑有重复实现，帮我抽成公共函数，并替换掉所有重复的地方。代码在 thingspanel-frontend-community。

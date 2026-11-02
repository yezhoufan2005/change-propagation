---
allowed_tools: [Read, Glob, Grep, Edit, Write, Bash, Agent, TodoWrite, Skill]
max_turns: 150
timeout_seconds: 2400
---

thingspanel-frontend-community 里 ThingsVisAppFrame.vue 的 normalizeAlarmLevel 不认后端返回的 H/M/L 告警级别，补上：H 对应 critical，M 对应 warning，L 对应 info。

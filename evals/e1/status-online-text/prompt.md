---
allowed_tools: [Read, Glob, Grep, Edit, Write, Bash, Agent, TodoWrite, Skill]
max_turns: 150
timeout_seconds: 2400
---

thingspanel-frontend-community 里 ThingsVisAppFrame.vue 通过 WebSocket 推送设备在线状态时，online_text 写死了中文“在线”/“离线”，改成走 i18n，英文界面也要显示对应的英文。

---
allowed_tools: [Read, Glob, Grep, Edit, Write, Bash, Agent, TodoWrite, Skill]
max_turns: 150
timeout_seconds: 2400
---

thingspanel-frontend-community 的场景编辑页（src/views/automation/scene-edit/index.vue）里，添加执行动作时选完设备、还没选属性，值输入框的占位符显示成「如：undefined」。修一下：没有示例值的时候不要显示「如：…」。

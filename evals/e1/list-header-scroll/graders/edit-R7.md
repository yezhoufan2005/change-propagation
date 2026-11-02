---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/system-management-user/system-log/components/login-trace-list.vue' }
pattern: '^(?=[\s\S]*?<div\b[^>]*\bstyle="[^"]*\boverflow(?:-y)?\s*:\s*(?:auto|scroll)\b[^"]*"[^>]*>\s*<div\b[^>]*\bstyle="[^"]*\bbackground(?:-color)?\s*:\s*#f0f0f0\b)(?=[\s\S]*?\bstyle="[^"]*\bheight\s*:\s*240px\b[^"]*\boverflow(?:-y)?\s*:\s*(?:auto|scroll)\b)'
match: not_contains
---

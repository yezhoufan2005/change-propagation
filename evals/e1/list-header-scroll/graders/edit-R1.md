---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/automation/scene-manage/modules/scene-deploy-list.vue' }
pattern: '^(?=[\s\S]*?class="[^"]*\bdeploy-list__body\b[^"]*"[^>]*>\s*(?:<!--[\s\S]*?-->\s*)*<[a-zA-Z][\w-]*\b[^>]*class="[^"]*\bdeploy-list__header\b)(?=[\s\S]*?(?:\.deploy-list|&)__body\s*(?:,[^{}]*)?\{[^}]*overflow(?:-y)?\s*:\s*(?:[a-z-]+\s+)?(?:auto|scroll|overlay)\b)'
match: not_contains
---

---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/device/details/modules/command-dispatch-list.vue' }
pattern: '^(?=[\s\S]*?class="[^"]*\bdispatch-panel__scroll\b[^"]*"[^>]*>\s*(?:<!--[\s\S]*?-->\s*)*<[a-zA-Z][\w-]*\b[^>]*class="[^"]*\bdispatch-panel__head\b)(?=[\s\S]*?(?:\.dispatch-panel|&)__scroll\s*(?:,[^{}]*)?\{[^}]*overflow(?:-y)?\s*:\s*(?:[a-z-]+\s+)?(?:auto|scroll|overlay)\b)'
match: not_contains
---

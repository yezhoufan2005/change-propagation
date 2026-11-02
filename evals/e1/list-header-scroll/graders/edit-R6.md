---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/apply/plugin/components/plugin-instance-panel.vue' }
pattern: '^(?=[\s\S]*?<[\w-]+\b[^>]*\bclass="[^"]*\binstance-panel__content\b[^"]*"[^>]*>\s*(?:<!--[\s\S]*?-->\s*)*<[\w-]+\b[^>]*\bclass="[^"]*\binstance-panel__title-bar\b)(?=[\s\S]*?(?:&|\.instance-panel)__content\s*\{[^{}]*?overflow(?:-y)?\s*:\s*(?:auto|scroll|overlay)\b)'
match: not_contains
---

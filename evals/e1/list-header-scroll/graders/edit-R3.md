---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/alarm/notification-record/components/delivery-attempt-list.vue' }
pattern: '^(?=[\s\S]*?<div\b[^>]*?\bclass="[^"]*\boverflow(?:-y)?-(?:auto|scroll)\b[^"]*"[^>]*>\s*<div\b[^>]*?\bclass="[^"]*\bbg-gray-100\b)(?=[\s\S]*?<div\b[^>]*?\bclass="(?![^"]*\boverflow(?:-y)?-hidden\b)[^"]*\boverflow(?:-y)?-(?:auto|scroll)\b[^"]*"[^>]*>\s*<div\b[^>]*?\bclass="[^"]*\bbg-gray-100\b)'
match: not_contains
---

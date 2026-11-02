---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/device/grouping-details/modules/group-member-list.vue' }
pattern: '^(?=[\s\S]*?(?:<(?:n-scrollbar|NScrollbar)\b[^>]*>(?:(?!<\/(?:n-scrollbar|NScrollbar)\s*>)[\s\S])*?\bclass="[^"]*\bmember-list-head\b|<div\b[^>]*\bstyle="[^"]*overflow(?:-y)?\s*:\s*(?:auto|scroll)[^"]*"[^>]*>\s*<div\b[^>]*\bclass="[^"]*\bmember-list-head\b))(?=[\s\S]*?(?:<(?:n-scrollbar|NScrollbar)\b[^>]*(?:height\s*:\s*\d|\bh-\d|\bmax-h-\d)[^>]*>(?:(?!<\/(?:n-scrollbar|NScrollbar)\s*>)[\s\S])*?\bclass="[^"]*\bmember-list-head\b|<div\b[^>]*\bstyle="[^"]*overflow(?:-y)?\s*:\s*(?:auto|scroll)[^"]*"[^>]*>\s*<div\b[^>]*\bclass="[^"]*\bmember-list-head\b))'
match: not_contains
---

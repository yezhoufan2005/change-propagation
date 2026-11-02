---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/management/role/modules/role-user-list.vue' }
pattern: '^(?=[\s\S]*?<div\b[^>]*\bclass="[^"]*\brole-user-scroll\b[^"]*"[^>]*>\s*(?:<!--[\s\S]*?-->\s*)*<(?:RoleUserListHeader|role-user-list-header)\b)(?=[\s\S]*?\.role-user-scroll\s*\{[^}]*?\boverflow(?:-y)?\s*:\s*(?:[a-z-]+\s+)?(?:auto|scroll)\b)'
match: not_contains
---

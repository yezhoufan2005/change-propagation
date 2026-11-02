---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'thingspanel-backend-community/pkg/utils/password_utils.go' }
pattern: 'len\(password\) < 6'
match: not_contains
---

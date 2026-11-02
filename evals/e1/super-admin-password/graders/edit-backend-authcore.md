---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'thingspanel-backend-community/encore-api/internal/authcore/compatibility.go' }
pattern: 'len\(p\) < 6'
match: not_contains
---

---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'server/src/utils/time.ts' }
pattern: 'getFullYear'
match: not_contains
---

---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'server/src/services/report.ts' }
pattern: 'toISOString\(\)\.slice'
match: not_contains
---

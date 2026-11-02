---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'server/src/validators/user.ts' }
pattern: 'PASSWORD_MIN_LEN\s*=\s*8\b'
match: not_contains
---

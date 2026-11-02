---
type: regex
weight: 1
flags: i
target: { source: file, path: 'web/src/features/auth/RegisterForm.tsx' }
pattern: 'MIN_PASSWORD_LENGTH\s*=\s*8\b'
match: not_contains
---

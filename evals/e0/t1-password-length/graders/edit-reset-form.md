---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'web/src/features/auth/ResetPasswordForm.tsx' }
pattern: 'pwd\.length >= 8\b'
match: not_contains
---

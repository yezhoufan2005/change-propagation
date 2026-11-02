---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'thingspanel-backend-community/internal/model/users.http.go' }
pattern: 'Password +string `json:"password" validate:"required,min=6"`'
match: not_contains
---

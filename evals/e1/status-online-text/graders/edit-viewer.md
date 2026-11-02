---
type: regex
weight: 0.001
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/components/thingsvis/ThingsVisViewer.vue' }
pattern: 'is_online === 1 \? ''在线'' : ''离线'''
match: not_contains
---

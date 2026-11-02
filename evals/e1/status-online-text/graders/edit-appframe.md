---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/components/thingsvis/ThingsVisAppFrame.vue' }
pattern: 'is_online === 1 \? ''在线'' : ''离线'''
match: not_contains
---

---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/device/manage/modules/device-tag-list.vue' }
pattern: '^(?=[\s\S]*?<div class="tag-list__header"[^>]*>(?:(?!<div)[\s\S])*?</div>\s*<div class="tag-list__body"[^>]*>\s*<div v-for="[^"]*" [^>]*class="tag-list__row")(?=[\s\S]*?\.tag-list__header\s*\{[^}]*display:\s*grid;[^}]*background:\s*#f5f6f7)(?=[\s\S]*?\.tag-list__body\s*\{\s*max-height:\s*300px;\s*overflow-y:\s*auto;\s*\})'
---

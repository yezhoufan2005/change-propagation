---
type: regex
weight: 1
flags: i
target: { source: file, path: 'thingspanel-frontend-community/src/views/device/config-detail/modules/raw-payload-viewer.vue' }
pattern: '^(?![\s\S]*payload-viewer__head)(?=[\s\S]*?<div class="payload-viewer"[^>]*>\s*<div v-for="\(line, index\) in lines"[^>]*class="payload-viewer__line")(?=[\s\S]*?\.payload-viewer\s*\{\s*max-height:\s*220px;\s*overflow-y:\s*auto;[^}]*background:\s*#f5f6f7;[^}]*font-family:\s*monospace)'
---

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    payload?: string | null
    wrap?: boolean
  }>(),
  {
    payload: '',
    wrap: false
  }
)

// 能解析成 JSON 时格式化展示，否则按原文展示
const lines = computed(() => {
  const raw = props.payload ?? ''
  if (!raw.trim()) return []
  let text = raw
  try {
    text = JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    text = raw
  }
  return text.split(/\r?\n/)
})
</script>

<template>
  <div class="payload-viewer" :class="{ 'payload-viewer--wrap': wrap }">
    <div v-for="(line, index) in lines" :key="index" class="payload-viewer__line">
      <span class="payload-viewer__no">{{ index + 1 }}</span>
      <span class="payload-viewer__text">{{ line }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.payload-viewer {
  max-height: 220px;
  overflow-y: auto;
  padding: 8px 0;
  background: #f5f6f7;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
  line-height: 20px;
}

.payload-viewer__line {
  display: flex;
  white-space: pre;
}

.payload-viewer--wrap .payload-viewer__line {
  white-space: pre-wrap;
  word-break: break-all;
}

.payload-viewer__no {
  flex: 0 0 40px;
  padding-right: 8px;
  text-align: right;
  color: #a0a4ab;
  user-select: none;
}

.payload-viewer__text {
  flex: 1;
  min-width: 0;
  padding-right: 12px;
  color: #333;
}
</style>

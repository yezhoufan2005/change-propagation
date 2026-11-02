<script setup lang="ts">
import { computed } from 'vue'

defineOptions({ name: 'NoticeMessage' })

export type NoticeLevel = 'info' | 'success' | 'warning' | 'error'

const props = defineProps<{
  level: NoticeLevel
  title: string
  content?: string
  time?: string
}>()

const levelClass = computed(() => `notice-message--${props.level}`)
</script>

<template>
  <div class="notice-message" :class="levelClass">
    <div class="notice-message__title">{{ title }}</div>
    <div v-if="content" class="notice-message__content">{{ content }}</div>
    <div v-if="time" class="notice-message__time">{{ time }}</div>
  </div>
</template>

<style scoped>
.notice-message {
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 6px;
}

.notice-message--info {
  background: transparent;
  border-color: transparent;
}

.notice-message--success {
  background: rgba(24, 160, 88, 0.08);
  border-color: rgba(24, 160, 88, 0.3);
}

.notice-message--warning {
  background: rgba(240, 160, 32, 0.08);
  border-color: rgba(240, 160, 32, 0.3);
}

.notice-message--error {
  background: rgba(208, 48, 80, 0.08);
  border-color: rgba(208, 48, 80, 0.3);
}

.notice-message__title {
  font-weight: 500;
}

.notice-message__content,
.notice-message__time {
  margin-top: 4px;
  font-size: 12px;
  color: var(--n-text-color-3, #999);
}
</style>

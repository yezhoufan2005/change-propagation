<script setup lang="ts">
defineOptions({ name: 'LogLine' })

defineProps<{ level: 'debug' | 'info' | 'warning' | 'error'; text: string }>()
</script>

<template>
  <div class="log-line" :class="`log-line--${level}`">{{ text }}</div>
</template>

<style scoped>
.log-line {
  font-family: monospace;
  font-size: 12px;
}

.log-line--debug {
  color: #999;
}

.log-line--info {
  color: inherit;
}

.log-line--warning {
  color: #f0a020;
}

.log-line--error {
  color: #d03050;
}
</style>

<script setup lang="ts">
import { computed } from 'vue'

defineOptions({ name: 'MessageShareCard' })

interface LevelCount {
  level: string
  count: number
}

const props = withDefaults(defineProps<{ stats?: LevelCount[] }>(), {
  stats: () => [
    { level: 'info', count: 128 },
    { level: 'success', count: 46 },
    { level: 'warning', count: 21 },
    { level: 'error', count: 7 }
  ]
})

const SHARE_TINT: Record<string, string> = {
  success: 'rgba(24, 160, 88, 0.12)',
  warning: 'rgba(240, 160, 32, 0.12)',
  error: 'rgba(208, 48, 80, 0.12)'
}

const total = computed(() => props.stats.reduce((sum, s) => sum + s.count, 0))

const rows = computed(() =>
  props.stats.map(s => ({ ...s, percent: total.value ? Math.round((s.count / total.value) * 100) : 0 }))
)

// 卡片底色跟随占比最高的消息级别
const dominant = computed(() => [...rows.value].sort((a, b) => b.count - a.count)[0])
const cardTint = computed(() => SHARE_TINT[dominant.value?.level ?? ''] ?? 'transparent')
</script>

<template>
  <NCard :bordered="false" class="card-wrapper" :style="{ background: cardTint }" title="消息概览">
    <div v-for="row in rows" :key="row.level" class="flex-y-center justify-between py-4px">
      <span>{{ row.level }}</span>
      <span>{{ row.count }}（{{ row.percent }}%）</span>
    </div>
  </NCard>
</template>

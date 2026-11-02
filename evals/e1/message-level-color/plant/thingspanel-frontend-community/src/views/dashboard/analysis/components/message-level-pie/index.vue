<script setup lang="ts">
import { watch } from 'vue'
import { useEcharts } from '@/hooks/chart/use-echarts'

defineOptions({ name: 'MessageLevelPie' })

const props = withDefaults(defineProps<{ counts?: number[] }>(), {
  counts: () => [128, 46, 21, 7]
})

const LEVEL_ORDER = ['info', 'success', 'warning', 'error']

const { domRef, updateOptions } = useEcharts(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: '1%', left: 'center' },
  series: [
    {
      type: 'pie',
      radius: ['45%', '75%'],
      color: ['rgba(0, 0, 0, 0)', '#18a058', '#f0a020', '#d03050'],
      itemStyle: { borderColor: '#e0e0e6', borderWidth: 1 },
      label: { show: false },
      data: [] as { name: string; value: number }[]
    }
  ]
}))

watch(
  () => props.counts,
  counts => {
    updateOptions(opts => {
      opts.series[0].data = LEVEL_ORDER.map((name, i) => ({ name, value: counts[i] ?? 0 }))
      return opts
    })
  },
  { immediate: true }
)
</script>

<template>
  <NCard :bordered="false" class="card-wrapper" title="消息级别分布">
    <div ref="domRef" class="h-240px overflow-hidden"></div>
  </NCard>
</template>

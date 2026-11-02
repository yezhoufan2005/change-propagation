<script setup lang="ts">
import { computed } from 'vue'
import { NEmpty, NTag } from 'naive-ui'
import { $t } from '@/locales'
import { formatDateTime } from '@/utils/common/datetime'

defineOptions({ name: 'LoginTraceList' })

const props = withDefaults(
  defineProps<{
    logs?: Api.SystemManage.SystemLogList[]
  }>(),
  {
    logs: () => []
  }
)

type TraceRow = {
  key: string
  ip: string
  account: string
  method: string
  time: string
}

// 只保留登录相关的请求
const traces = computed<TraceRow[]>(() =>
  props.logs
    .filter(item => /login/i.test(item.path || ''))
    .map((item: any, index) => ({
      key: item.id || `${item.created_at}-${index}`,
      ip: item.ip || '--',
      account: item.username || item.email || '--',
      method: item.name || '--',
      time: formatDateTime(item.created_at) || '--'
    }))
)

const ipCount = computed(() => new Set(traces.value.map(row => row.ip)).size)
</script>

<template>
  <div style="margin-top: 16px">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px">
      <span style="font-size: 14px; font-weight: 600; color: var(--text-color)">登录记录</span>
      <NTag size="small" :bordered="false">{{ traces.length }}</NTag>
      <NTag v-if="ipCount > 1" size="small" type="warning" :bordered="false">{{ ipCount }} 个 IP</NTag>
    </div>
    <div style="height: 240px; overflow-y: auto; border: 1px solid #eee;">
      <div style="position: sticky; top: 0; z-index: 1; display: flex; padding: 8px 12px; background: #f0f0f0; font-size: 12px;">
        <span style="flex: 1">{{ $t('custom.management.ipAddress') }}</span>
        <span style="flex: 1">{{ $t('custom.management.account') }}</span>
        <span style="width: 80px">{{ $t('custom.management.requestMethod') }}</span>
        <span style="width: 160px">{{ $t('custom.management.time') }}</span>
      </div>
      <div
        v-for="row in traces"
        :key="row.key"
        style="display: flex; padding: 8px 12px; border-bottom: 1px solid #f5f5f5;"
      >
        <span style="flex: 1; min-width: 0; overflow-wrap: anywhere">{{ row.ip }}</span>
        <span style="flex: 1; min-width: 0; overflow-wrap: anywhere">{{ row.account }}</span>
        <span style="width: 80px">{{ row.method }}</span>
        <span style="width: 160px; color: var(--text-color-3)">{{ row.time }}</span>
      </div>
      <NEmpty v-if="!traces.length" size="small" :description="$t('common.nodata')" style="padding: 48px 0" />
    </div>
  </div>
</template>

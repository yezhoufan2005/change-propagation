<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'
import {
  notificationV2,
  NotificationSessionChangedError,
  registerNotificationSessionCleanup
} from '@/service/api/notification-v2'
import type * as NotificationV2 from '@/service/api/notification-v2.types'
import { describeDeliveryStatus } from '../../notification-record/workflow'

const { locale } = useI18n()
const tx = (zh: string, en: string) => (locale.value.toLowerCase().startsWith('zh') ? zh : en)
const rows = ref<NotificationV2.DeliveryView[]>([])
const loading = ref(false)
const errorText = ref('')
let controller: AbortController | null = null

const sourceText: Record<NotificationV2.SourceRef['type'], [string, string]> = {
  alarm: ['告警', 'Alarm'],
  automation: ['场景联动', 'Automation'],
  manual: ['手动发送', 'Manual'],
  test: ['测试发送', 'Test']
}

function formatTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

const rowKey = (row: NotificationV2.DeliveryView) => row.deliveryId

const columns = computed<DataTableColumns<NotificationV2.DeliveryView>>(() => [
  { title: tx('时间', 'Time'), key: 'createdAt', width: 180, render: row => formatTime(row.createdAt) },
  { title: tx('接收人', 'Recipient'), key: 'recipient', minWidth: 160, render: row => row.recipient.display },
  {
    title: tx('来源', 'Source'),
    key: 'source',
    width: 110,
    render: row => {
      const [zh, en] = sourceText[row.source.type] ?? [row.source.type, row.source.type]
      return tx(zh, en)
    }
  },
  { title: tx('尝试次数', 'Attempts'), key: 'attemptCount', width: 90 },
  {
    title: tx('状态', 'Status'),
    key: 'status',
    minWidth: 220,
    render: row => {
      const label = describeDeliveryStatus(row.dispatchStatus, row.deliveryStatus)
      return tx(label.zh, label.en)
    }
  }
])

async function load() {
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  errorText.value = ''
  try {
    const response = await notificationV2.listDeliveries({ page: 1, pageSize: 20 }, current.signal)
    if (controller === current) rows.value = response.data.items
  } catch (error) {
    if (controller !== current || current.signal.aborted || error instanceof NotificationSessionChangedError) return
    errorText.value = tx('暂时无法读取最近的发送记录。', 'Recent deliveries could not be loaded.')
  } finally {
    if (controller === current) loading.value = false
  }
}

const unregisterCleanup = registerNotificationSessionCleanup(() => {
  controller?.abort()
  controller = null
  rows.value = []
  loading.value = false
})

onMounted(load)
onBeforeUnmount(() => {
  unregisterCleanup()
  controller?.abort()
})
</script>

<template>
  <NCard size="small" :bordered="false" class="mt-12px">
    <div class="mb-8px flex items-center justify-between">
      <span class="font-600">{{ tx('最近发送', 'Recent deliveries') }}</span>
      <NButton size="small" :loading="loading" @click="load">{{ tx('刷新', 'Refresh') }}</NButton>
    </div>
    <NAlert v-if="errorText" type="error" class="mb-12px">{{ errorText }}</NAlert>
    <n-data-table
      class="recent-delivery-table"
      size="small"
      :columns="columns"
      :data="rows"
      :loading="loading"
      :max-height="280"
      :row-key="rowKey"
    />
  </NCard>
</template>

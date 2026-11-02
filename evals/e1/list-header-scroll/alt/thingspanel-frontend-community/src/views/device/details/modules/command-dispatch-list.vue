<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { NEmpty, NSpin, NTag } from 'naive-ui'
import { getCommandDataSetLogs } from '@/service/api'
import { $t } from '@/locales'
import { demoCommands, isDeviceDetailDemo } from '@/utils/device-detail-demo-data'

const props = defineProps<{ id: string }>()

type TagType = 'default' | 'success' | 'info' | 'warning' | 'error'

interface DispatchRow {
  key: string
  name: string
  status: string
  sentAt: string
}

const records = ref<any[]>([])
const loading = ref(false)

const statusMap: Record<string, { label: string; type: TagType }> = {
  '1': { label: $t('generate.sendingSuccess'), type: 'info' },
  '2': { label: $t('generate.sendingFail'), type: 'error' },
  '3': { label: $t('generate.returnSuccess'), type: 'success' },
  '4': { label: $t('generate.returnFail'), type: 'warning' }
}

const rows = computed<DispatchRow[]>(() =>
  records.value.map((item, index) => ({
    key: item.id ?? `${item.identify}-${index}`,
    name: item.identify_name || item.identify || '--',
    status: String(item.status ?? ''),
    sentAt: item.created_at
  }))
)

async function load() {
  records.value = []
  if (!props.id) return
  loading.value = true
  try {
    const { data, error } = await getCommandDataSetLogs({ device_id: props.id, page: 1, page_size: 20 })
    if (error) return
    const list = data?.value || data?.list || []
    records.value = list.length > 0 || !isDeviceDetailDemo(props.id) ? list : demoCommands()
  } finally {
    loading.value = false
  }
}

watch(() => props.id, load, { immediate: true })

const formatTime = (value?: string) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '--')
</script>

<template>
  <div class="dispatch-panel">
    <div class="dispatch-panel__title">下发记录</div>
    <NSpin :show="loading">
      <NEmpty v-if="!loading && rows.length === 0" size="small" :description="$t('common.noData')" class="py-6" />
      <div v-else class="dispatch-panel__scroll">
        <div class="dispatch-panel__head">
          <span>{{ $t('device_template.table_header.commandName') }}</span>
          <span>{{ $t('generate.status') }}</span>
          <span>{{ $t('generate.commandIssuanceTime') }}</span>
        </div>
        <div class="dispatch-panel__list">
          <div v-for="row in rows" :key="row.key" class="dispatch-panel__item">
            <span class="dispatch-panel__name">{{ row.name }}</span>
            <span>
              <NTag size="small" :type="statusMap[row.status]?.type ?? 'default'" :bordered="false">
                {{ statusMap[row.status]?.label || '--' }}
              </NTag>
            </span>
            <span class="dispatch-panel__time">{{ formatTime(row.sentAt) }}</span>
          </div>
        </div>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.dispatch-panel {
  margin-top: 16px;
}

.dispatch-panel__title {
  margin-bottom: 12px;
  font-weight: 600;
}

.dispatch-panel__scroll {
  max-height: 320px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.dispatch-panel__list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.dispatch-panel__head {
  background: #f2f3f5;
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) 120px 180px;
  gap: 12px;
  padding: 10px 12px;
  color: var(--text-color-2);
  font-size: 13px;
  font-weight: 600;
}

.dispatch-panel__item {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) 120px 180px;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-top: 1px solid rgb(226 232 240 / 85%);
  font-size: 13px;
}

.dispatch-panel__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dispatch-panel__time {
  color: var(--text-color-3);
}
</style>

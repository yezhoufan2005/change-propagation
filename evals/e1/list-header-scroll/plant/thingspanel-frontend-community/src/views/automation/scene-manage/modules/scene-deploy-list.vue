<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NEmpty, NSpin, NTag } from 'naive-ui'
import { AutomationApiError, listRuns, type Run, type RunTarget } from '@/service/api/automation-rules'
import { $t } from '@/locales'
import { describeRunStatus } from '@/utils/automation/summary'
import { formatDateTime } from '@/utils/common/datetime'

const props = defineProps<{ sceneId: string }>()

interface DeployRow {
  key: string
  name: string
  status: string
  reasonCode?: string
  deployedAt: string
}

const runs = ref<Run[]>([])
const loading = ref(false)
const failure = ref('')

// 每次执行下发到的设备各占一行
const rows = computed<DeployRow[]>(() =>
  runs.value.flatMap(run => {
    const targets: RunTarget[] = run.targets?.length
      ? run.targets
      : [{ device_id: run.device_id || run.scope_key, selected: true, status: run.status }]
    return targets.map(target => ({
      key: `${run.id}-${target.device_id}`,
      name: target.device_id || '—',
      status: target.status || run.status,
      reasonCode: target.reason_code ?? run.reason_code,
      deployedAt: run.finished_at || run.started_at
    }))
  })
)

async function load() {
  runs.value = []
  failure.value = ''
  if (!props.sceneId) return
  loading.value = true
  try {
    const result = await listRuns(props.sceneId, { limit: 20, offset: 0 })
    runs.value = result.runs ?? []
  } catch (error) {
    const apiError = error as AutomationApiError
    failure.value = apiError.message || '部署记录加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.sceneId, load, { immediate: true })

function toneOf(status: string) {
  const tone = describeRunStatus(status).tone
  if (tone === 'ok') return 'success'
  if (tone === 'bad') return 'error'
  if (tone === 'warn') return 'warning'
  return 'info'
}
</script>

<template>
  <div class="deploy-list">
    <div class="deploy-list__title">
      <span>部署列表</span>
      <NTag size="small" :bordered="false">{{ rows.length }}</NTag>
    </div>
    <div v-if="failure" class="deploy-list__failure">{{ failure }}</div>
    <NSpin :show="loading">
      <NEmpty v-if="!loading && rows.length === 0" size="small" :description="$t('common.noData')" class="py-6" />
      <div v-else class="deploy-list__body">
        <div class="deploy-list__header">
          <span>{{ $t('generate.device') }} / {{ $t('generate.group') }}</span>
          <span>{{ $t('generate.status') }}</span>
          <span>部署时间</span>
        </div>
        <div v-for="row in rows" :key="row.key" class="deploy-list__row">
          <span class="deploy-list__name">{{ row.name }}</span>
          <span>
            <NTag size="small" :type="toneOf(row.status)" :bordered="false">
              {{ describeRunStatus(row.status, row.reasonCode).label }}
            </NTag>
          </span>
          <span class="deploy-list__time">{{ formatDateTime(row.deployedAt) || '—' }}</span>
        </div>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
.deploy-list__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
}

.deploy-list__failure {
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgb(254 226 226);
  color: rgb(153 27 27);
  font-size: 13px;
}

.deploy-list__body {
  max-height: 360px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.deploy-list__header {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f5f6f7;
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) 120px 180px;
  gap: 12px;
  padding: 10px 12px;
  color: var(--text-color-2);
  font-size: 13px;
  font-weight: 600;
}

.deploy-list__row {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) 120px 180px;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-top: 1px solid rgb(226 232 240 / 85%);
  font-size: 13px;
}

.deploy-list__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.deploy-list__time {
  color: var(--text-color-3);
}
</style>

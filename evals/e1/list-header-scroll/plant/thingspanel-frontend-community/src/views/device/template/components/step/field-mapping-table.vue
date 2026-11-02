<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { telemetryApi } from '@/service/api/system-data'
import { $t } from '@/locales'

interface MappingRow {
  data_name: string
  data_identifier: string
  data_type: string
  read_write_flag: string
  unit: string
  description: string
}

const props = defineProps<{
  deviceTemplateId: string
}>()

const columns: { key: keyof MappingRow; title: string; width: number }[] = [
  { key: 'data_name', title: $t('device_template.table_header.dataName'), width: 180 },
  { key: 'data_identifier', title: $t('device_template.table_header.dataIdentifier'), width: 200 },
  { key: 'data_type', title: $t('device_template.table_header.dataType'), width: 120 },
  { key: 'read_write_flag', title: $t('device_template.table_header.readAndWriteSign'), width: 120 },
  { key: 'unit', title: $t('device_template.table_header.unit'), width: 100 },
  { key: 'description', title: $t('device_template.table_header.description'), width: 240 }
]

const rows = ref<MappingRow[]>([])

const getRows = async () => {
  if (!props.deviceTemplateId) return
  const { data, error }: any = await telemetryApi({
    page: 1,
    page_size: 100,
    device_template_id: props.deviceTemplateId
  })
  if (!error) {
    rows.value = data?.list ?? []
  }
}

watch(() => props.deviceTemplateId, getRows)
onMounted(getRows)
</script>

<template>
  <div class="mapping-scroll">
    <div class="mapping-head">
      <span v-for="col in columns" :key="col.key" class="mapping-cell" :style="{ width: `${col.width}px` }">
        {{ col.title }}
      </span>
    </div>
    <div v-for="row in rows" :key="row.data_identifier" class="mapping-row">
      <span v-for="col in columns" :key="col.key" class="mapping-cell" :style="{ width: `${col.width}px` }">
        {{ row[col.key] || '--' }}
      </span>
    </div>
    <n-empty v-if="!rows.length" size="small" class="py-16px" :description="$t('common.noData')" />
  </div>
</template>

<style scoped lang="scss">
.mapping-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid var(--border-color);
  border-radius: 6px;
}

.mapping-head {
  display: flex;
  min-width: 960px;
  background: #f5f6f7;
  color: #606266;
  font-size: 13px;
}

.mapping-row {
  display: flex;
  min-width: 960px;
  font-size: 13px;
  border-top: 1px solid var(--border-color);
}

.mapping-cell {
  flex: 0 0 auto;
  padding: 8px 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

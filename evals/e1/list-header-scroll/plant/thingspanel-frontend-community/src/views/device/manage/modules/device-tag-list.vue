<script setup lang="ts">
import { computed } from 'vue'
import { $t } from '@/locales'

const props = defineProps<{
  tags: string[]
}>()

const emit = defineEmits<{
  (e: 'update:tags', tags: string[]): void
}>()

const rows = computed(() =>
  props.tags.map((tag, index) => ({
    index: index + 1,
    name: tag
  }))
)

const removeTag = (index: number) => {
  emit(
    'update:tags',
    props.tags.filter((_, i) => i !== index)
  )
}
</script>

<template>
  <div class="tag-list">
    <div class="tag-list__header">
      <span>{{ $t('common.index') }}</span>
      <span>{{ $t('custom.devicePage.label') }}</span>
      <span class="text-right">{{ $t('common.actions') }}</span>
    </div>
    <div class="tag-list__body">
      <div v-for="(row, i) in rows" :key="`${row.name}-${i}`" class="tag-list__row">
        <span class="tag-list__index">{{ row.index }}</span>
        <span class="tag-list__name">
          <n-tag size="small" :bordered="false" type="info">{{ row.name }}</n-tag>
        </span>
        <span class="text-right">
          <n-button text type="error" size="small" @click="removeTag(i)">{{ $t('common.remove') }}</n-button>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.tag-list {
  width: 100%;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 6px;
  overflow: hidden;
}

.tag-list__header {
  display: grid;
  grid-template-columns: 64px 1fr 80px;
  padding: 8px 12px;
  font-size: 13px;
  color: #606266;
  background: #f5f6f7;
}

.tag-list__body {
  max-height: 300px;
  overflow-y: auto;
}

.tag-list__row {
  display: grid;
  grid-template-columns: 64px 1fr 80px;
  align-items: center;
  padding: 6px 12px;
  font-size: 13px;
  border-top: 1px solid var(--border-color, #f0f0f0);

  &:hover {
    background: rgb(var(--primary-color) / 4%);
  }
}

.tag-list__index {
  color: #909399;
}

.tag-list__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

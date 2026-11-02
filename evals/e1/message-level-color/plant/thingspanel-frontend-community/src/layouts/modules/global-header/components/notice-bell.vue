<script setup lang="ts">
import { ref } from 'vue'

defineOptions({ name: 'NoticeBell' })

interface NoticeItem {
  id: number
  level: 'info' | 'success' | 'warning' | 'error'
  title: string
}

const items = ref<NoticeItem[]>([])
</script>

<template>
  <NPopover trigger="click" placement="bottom-end">
    <template #trigger>
      <ButtonIcon icon="mdi:bell-outline" tooltip-content="消息" />
    </template>
    <div class="w-280px">
      <div
        v-for="item in items"
        :key="item.id"
        class="py-6px pl-8px"
        :style="{
          borderLeft: '3px solid',
          borderLeftColor:
            item.level === 'error'
              ? '#d03050'
              : item.level === 'warning'
                ? '#f0a020'
                : item.level === 'success'
                  ? '#18a058'
                  : 'transparent'
        }"
      >
        {{ item.title }}
      </div>
      <NEmpty v-if="!items.length" size="small" />
    </div>
  </NPopover>
</template>

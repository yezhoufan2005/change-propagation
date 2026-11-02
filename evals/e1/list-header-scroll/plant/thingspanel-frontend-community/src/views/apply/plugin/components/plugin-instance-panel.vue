<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NEmpty, NSpin, NTag } from 'naive-ui'
import {
  NotificationSessionChangedError,
  notificationV2,
  type NotificationInstance,
  type NotificationPlugin
} from '@/service/api/notification-v2'
import { $t } from '@/locales'

interface Props {
  plugins: NotificationPlugin[]
}

const props = defineProps<Props>()
const { locale } = useI18n()
const tx = (zh: string, en: string) => (locale.value.toLowerCase().startsWith('zh') ? zh : en)
const instances = ref<NotificationInstance[]>([])
const loading = ref(false)
const errorText = ref('')
let generation = 0

const items = computed(() =>
  instances.value.map(item => {
    const plugin = props.plugins.find(row => row.id === item.pluginRegistrationId)
    return {
      id: item.id,
      name: item.name,
      pluginName: plugin?.manifest.name || item.pluginRegistrationId,
      version: plugin?.pluginVersion || '--',
      enabled: item.enabled
    }
  })
)

async function load() {
  const current = ++generation
  loading.value = true
  errorText.value = ''
  try {
    const response = await notificationV2.listInstances({ page: 1, pageSize: 100 })
    if (current === generation) instances.value = response.data.items
  } catch (error) {
    if (current !== generation || error instanceof NotificationSessionChangedError) return
    errorText.value = tx('无法读取插件实例。', 'Could not load plugin instances.')
  } finally {
    if (current === generation) loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <NSpin :show="loading">
    <div class="instance-panel">
      <div class="instance-panel__caption">{{ tx('插件实例', 'Plugin instances') }}</div>
      <div class="instance-panel__content">
        <div class="instance-panel__title-bar">
          <span class="instance-panel__cell instance-panel__cell--wide">{{ tx('实例名称', 'Instance') }}</span>
          <span class="instance-panel__cell instance-panel__cell--wide">{{ $t('card.pluginName') }}</span>
          <span class="instance-panel__cell">{{ $t('card.version') }}</span>
          <span class="instance-panel__cell">{{ $t('generate.status') }}</span>
        </div>
        <div v-for="item in items" :key="item.id" class="instance-panel__item">
          <span class="instance-panel__cell instance-panel__cell--wide">{{ item.name }}</span>
          <span class="instance-panel__cell instance-panel__cell--wide">{{ item.pluginName }}</span>
          <span class="instance-panel__cell">{{ item.version }}</span>
          <span class="instance-panel__cell">
            <NTag size="small" :type="item.enabled ? 'success' : 'default'">
              {{ item.enabled ? tx('已启用', 'Enabled') : tx('已停用', 'Disabled') }}
            </NTag>
          </span>
        </div>
        <NEmpty
          v-if="!loading && !items.length"
          class="py-24px"
          size="small"
          :description="errorText || $t('common.noData')"
        />
      </div>
    </div>
  </NSpin>
</template>

<style lang="scss" scoped>
$panel-head-bg: #f7f8fa;

.instance-panel {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;

  &__caption {
    padding: 12px 14px;
    border-bottom: 1px solid #edf0f3;
    color: #374151;
    font-size: 14px;
    font-weight: 600;
  }

  &__content {
    max-height: 280px;
    overflow-y: auto;
  }

  &__title-bar {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    height: 40px;
    align-items: center;
    background: $panel-head-bg;
    color: #4b5563;
    font-size: 13px;
    font-weight: 600;
  }

  &__item {
    display: flex;
    height: 44px;
    align-items: center;
    border-top: 1px solid #edf0f3;
    color: #374151;

    &:hover {
      background: #f8fbff;
    }
  }

  &__cell {
    flex: 1;
    min-width: 0;
    padding: 0 14px;
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;

    &--wide {
      flex: 2;
    }
  }
}
</style>

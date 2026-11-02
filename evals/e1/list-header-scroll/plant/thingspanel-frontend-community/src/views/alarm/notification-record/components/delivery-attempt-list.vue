<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TagProps } from 'naive-ui'
import type { NotificationInstance } from '@/service/api/notification-v2'
import type * as NotificationV2 from '@/service/api/notification-v2.types'
import { describeDeliveryStatus } from '../workflow'

defineOptions({ name: 'DeliveryAttemptList' })

const props = withDefaults(
  defineProps<{
    deliveries: NotificationV2.DeliveryView[]
    instances?: NotificationInstance[]
  }>(),
  {
    instances: () => []
  }
)

const { locale } = useI18n()
const isZh = computed(() => locale.value.toLowerCase().startsWith('zh'))
const tx = (zh: string, en: string) => (isZh.value ? zh : en)

const instanceMap = computed(() => new Map(props.instances.map(instance => [instance.id, instance])))

function resultTone(delivery: NotificationV2.DeliveryView): TagProps['type'] {
  if (delivery.dispatchStatus === 'failed' || delivery.deliveryStatus === 'failed') return 'error'
  if (delivery.dispatchStatus === 'unknown' || delivery.deliveryStatus === 'unknown') return 'warning'
  if (delivery.deliveryStatus === 'delivered') return 'success'
  return 'default'
}

// 按创建时间倒序展示
const items = computed(() =>
  [...props.deliveries]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .map(delivery => {
      const instance = instanceMap.value.get(delivery.instanceId)
      const status = describeDeliveryStatus(delivery.dispatchStatus, delivery.deliveryStatus)
      return {
        deliveryId: delivery.deliveryId,
        channel: instance ? `${instance.name} · ${instance.channel}` : delivery.instanceId,
        recipient: delivery.recipient.display || '—',
        result: isZh.value ? status.zh : status.en,
        tone: resultTone(delivery),
        attemptCount: delivery.attemptCount,
        time: new Date(delivery.createdAt).toLocaleString()
      }
    })
)
</script>

<template>
  <div class="delivery-attempt-list">
    <div class="mb-8px flex items-center justify-between">
      <span class="font-600">{{ tx('投递尝试', 'Delivery attempts') }}</span>
      <span class="text-12px text-gray-500">{{ tx(`共 ${items.length} 条`, `${items.length} in total`) }}</span>
    </div>
    <div class="h-300px overflow-y-auto border border-gray-200 rounded-4px">
      <div class="sticky top-0 z-1 flex items-center bg-gray-100 px-12px py-8px text-12px text-gray-500">
        <span class="w-180px flex-none">{{ tx('通知渠道', 'Channel') }}</span>
        <span class="min-w-0 flex-1">{{ tx('投递结果', 'Result') }}</span>
        <span class="w-72px flex-none text-center">{{ tx('尝试次数', 'Attempts') }}</span>
        <span class="w-170px flex-none text-right">{{ tx('时间', 'Time') }}</span>
      </div>
      <div
        v-for="item in items"
        :key="item.deliveryId"
        class="flex items-center px-12px py-8px border-b border-gray-100"
      >
        <div class="w-180px min-w-0 flex-none pr-8px">
          <div class="truncate text-13px">{{ item.channel }}</div>
          <div class="truncate text-12px text-gray-500">{{ item.recipient }}</div>
        </div>
        <div class="min-w-0 flex-1 pr-8px">
          <NTag size="small" :type="item.tone" :bordered="false">{{ item.result }}</NTag>
        </div>
        <span class="w-72px flex-none text-center text-13px">{{ item.attemptCount }}</span>
        <span class="w-170px flex-none text-right text-12px text-gray-500">{{ item.time }}</span>
      </div>
      <div v-if="!items.length" class="py-24px">
        <NEmpty size="small" :description="tx('暂无投递记录', 'No delivery attempts')" />
      </div>
    </div>
  </div>
</template>

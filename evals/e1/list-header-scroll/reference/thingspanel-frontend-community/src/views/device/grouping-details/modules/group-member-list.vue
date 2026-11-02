<script setup lang="ts">
import { ref, watch } from 'vue'
import { NEmpty, NSpin, NTag } from 'naive-ui'
import { useLoading } from '@sa/hooks'
import { deviceListByGroup } from '@/service/api/device'
import { useRouterPush } from '@/hooks/common/router'
import { formatDateTime } from '@/utils/common/datetime'
import { $t } from '@/locales'

interface MemberItem {
  id: string
  name: string
  device_number?: string
  is_online?: number
  ts?: string
}

const props = defineProps<{
  groupId: string
}>()

const { routerPushByKey } = useRouterPush()
const { loading, startLoading, endLoading } = useLoading()
const members = ref<MemberItem[]>([])

const getMembers = async () => {
  if (!props.groupId) return
  startLoading()
  const { data, error } = await deviceListByGroup({ group_id: props.groupId, page: 1, page_size: 100 })
  members.value = !error && Array.isArray(data?.list) ? data.list : []
  endLoading()
}

const goDeviceDetails = (item: MemberItem) => {
  routerPushByKey('device_details', { query: { d_id: item.id } })
}

watch(() => props.groupId, getMembers, { immediate: true })
</script>

<template>
  <div class="member-list">
    <NSpin :show="loading">
      <div class="member-list-head">
        <span class="member-cell member-cell--name">{{ $t('custom.devicePage.deviceName') }}</span>
        <span class="member-cell">{{ $t('custom.devicePage.onlineStatus') }}</span>
        <span class="member-cell member-cell--time">{{ $t('custom.devicePage.lastPushTime') }}</span>
      </div>
      <n-scrollbar style="max-height: 300px">
        <div v-for="item in members" :key="item.id" class="member-list-row" @click="goDeviceDetails(item)">
          <span class="member-cell member-cell--name">{{ item.name || '-' }}</span>
          <span class="member-cell">
            <NTag size="small" :type="item.is_online === 1 ? 'success' : 'default'">
              {{ item.is_online === 1 ? $t('custom.devicePage.online') : $t('custom.devicePage.offline') }}
            </NTag>
          </span>
          <span class="member-cell member-cell--time">{{ formatDateTime(item.ts) || '--' }}</span>
        </div>
        <NEmpty v-if="!members.length" class="py-6" size="small" :description="$t('common.noData')" />
      </n-scrollbar>
    </NSpin>
  </div>
</template>

<style scoped lang="scss">
.member-list {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
}

.member-list-head {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 16px;
  background-color: #fafafc;
  font-weight: 500;
  border-bottom: 1px solid var(--border-color);
}

.member-list-row {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background-color: var(--primary-color-suppl);
  }
}

.member-cell {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  &--name {
    flex: 2;
  }

  &--time {
    flex: 1.5;
  }
}
</style>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { NEmpty, NSpin, NTag } from 'naive-ui'
import { fetchUserList } from '@/service/api/auth'
import { $t } from '@/locales'
import RoleUserListHeader from './role-user-list-header.vue'

defineOptions({ name: 'RoleUserList' })

const props = defineProps<{
  /** 角色id */
  roleId?: string | null
}>()

const loading = ref(false)
const userList = ref<UserManagement.User[]>([])

async function getUserList() {
  if (!props.roleId) {
    userList.value = []
    return
  }
  loading.value = true
  try {
    const { data } = await fetchUserList({ page: 1, page_size: 100, role_id: props.roleId })
    userList.value = data?.list ?? []
  } finally {
    loading.value = false
  }
}

function statusLabel(status: UserManagement.User['status']) {
  return status === 'N' ? $t('page.manage.user.status.normal') : $t('page.manage.user.status.freeze')
}

watch(() => props.roleId, getUserList, { immediate: true })
</script>

<template>
  <div class="role-user-list">
    <div class="mb-8px flex items-center justify-between">
      <span class="text-14px font-600">{{ $t('generate.user') }}</span>
      <span class="text-12px text-gray-400">{{ userList.length }}</span>
    </div>
    <NSpin :show="loading">
      <div class="role-user-scroll">
        <RoleUserListHeader />
        <div class="role-user-body">
          <div v-for="item in userList" :key="item.id" class="role-user-row">
            <span class="role-user-cell" :title="item.name || ''">{{ item.name || '--' }}</span>
            <span class="role-user-cell" :title="item.email || ''">{{ item.email || '--' }}</span>
            <span class="role-user-cell role-user-cell--status">
              <NTag v-if="item.status" size="small" :type="item.status === 'N' ? 'success' : 'error'">
                {{ statusLabel(item.status) }}
              </NTag>
            </span>
          </div>
          <NEmpty
            v-if="!loading && userList.length === 0"
            size="small"
            class="py-24px"
            :description="$t('common.nodata')"
          />
        </div>
      </div>
    </NSpin>
  </div>
</template>

<style scoped lang="scss">
.role-user-scroll {
  display: flex;
  flex-direction: column;
  max-height: 320px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.role-user-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.role-user-row {
  display: flex;
  align-items: center;
  min-height: 40px;
  border-bottom: 1px solid rgb(226 232 240 / 85%);
  transition: background-color 180ms ease;

  &:hover {
    background: rgb(239 246 255);
  }
}

.role-user-cell {
  flex: 1;
  min-width: 0;
  padding: 0 12px;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;

  &--status {
    flex: 0 0 96px;
  }
}
</style>

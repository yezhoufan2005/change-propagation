<script setup lang="ts">
import { $t } from '@/locales'

defineOptions({ name: 'RoleUserListHeader' })
</script>

<template>
  <div class="role-user-header">
    <span class="role-user-header__cell">{{ $t('page.manage.user.userName') }}</span>
    <span class="role-user-header__cell">{{ $t('page.manage.user.userEmail') }}</span>
    <span class="role-user-header__cell role-user-header__cell--status">
      {{ $t('page.manage.user.userStatus2') }}
    </span>
  </div>
</template>

<style scoped lang="scss">
.role-user-header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  height: 40px;
  background: rgb(245 246 248);
  border-bottom: 1px solid rgb(226 232 240 / 85%);

  &__cell {
    flex: 1;
    min-width: 0;
    padding: 0 12px;
    font-size: 13px;
    color: var(--text-color);
    white-space: nowrap;
  }

  &__cell--status {
    flex: 0 0 96px;
  }
}
</style>

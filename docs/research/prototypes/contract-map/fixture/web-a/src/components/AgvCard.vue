<template>
  <div class="agv-card" :class="statusColor(agv.mode)">
    <span>{{ agv.battery }}%</span>
    <task-badge :task-id="agv.taskId" @task-cancel="onCancel" />
  </div>
</template>
<script setup>
const props = defineProps({ agv: Object })
const STATUS_COLOR = { idle: 'green', charging: 'blue', error: 'red' }
function statusColor(m) { return STATUS_COLOR[m] }
</script>

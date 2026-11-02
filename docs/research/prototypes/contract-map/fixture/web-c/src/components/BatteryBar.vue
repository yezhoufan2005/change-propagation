<template>
  <div class="battery-level" :style="{ width: batteryLevel + '%' }">{{ batteryLevel }}</div>
</template>
<script setup>
defineProps({ batteryLevel: Number })
</script>
<style scoped>
.battery-level { height: 6px; }
</style>

<template>
  <tr><td>{{ MODE_LABEL[s.mode] }}</td><td><BatteryBar :battery-level="s.batteryLevel" /></td></tr>
</template>
<script setup>
import { MODE_LABEL } from '../utils/labels'
defineProps({ s: Object })
</script>

<template><div v-for="item in list">{{ item.battery_level | batteryText }}</div></template>
<script>
const statusColorMap = { idle: '#52c41a', charging: '#1890ff', error: '#f5222d' }
export default {
  mixins: [agvMixin],
  filters: { batteryText(v) { return v + '%' } },
  mounted() {
    this.client = mqtt.connect('wss://broker.local/mqtt')
    this.client.subscribe('agv/+/status')
    this.client.on('message', (topic, payload) => {
      const d = JSON.parse(payload.toString())
      this.$set(this.list, d.agv_id, { battery_level: d.battery_level, mode: d.Mode })
    })
  }
}
</script>

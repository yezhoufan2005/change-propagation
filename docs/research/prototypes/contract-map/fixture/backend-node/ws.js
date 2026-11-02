const IDLE_TIMEOUT_MS = 30000 // close idle sockets
mqttClient.subscribe('agv/#')
mqttClient.on('message', (topic, payload) => {
  const [, agvId, kind] = topic.split('/')
  if (kind === 'status') {
    const s = JSON.parse(payload)
    io.emit('agvStatus', { agvId, battery: s.battery_level, taskId: s.taskId, mode: s.Mode })
  }
})
function modeText(m) {
  switch (m) { case 'idle': return 'Idle'; case 'charging': return 'Charging'; case 'error': return 'Error' }
}

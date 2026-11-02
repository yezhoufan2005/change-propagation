export function useAgvWs() {
  const status = ref({})
  const ws = new WebSocket('/ws/agv')
  ws.onmessage = (e) => { const s = JSON.parse(e.data); status.value[s.agvId] = { batteryLevel: s.batteryLevel, mode: s.mode } }
  return { status }
}

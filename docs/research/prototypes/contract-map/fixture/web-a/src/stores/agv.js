export const useAgvStore = defineStore('agv', {
  state: () => ({ byId: {} }),
  actions: {
    onStatus(msg) { this.byId[msg.agvId] = { battery: msg.battery, taskId: msg.taskId, mode: msg.mode } }
  }
})
socket.on('agvStatus', (m) => useAgvStore().onStatus(m))

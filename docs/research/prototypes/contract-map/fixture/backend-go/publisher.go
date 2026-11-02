package agv

const (
	ModeIdle     = "idle"
	ModeCharging = "charging"
	ModeError    = "error"
)

type AGVStatus struct {
	AgvID        string  `json:"agv_id"`
	BatteryLevel float64 `json:"battery_level"`
	TaskID       string  `json:"taskId,omitempty"`
	Mode         string
}

func publishStatus(c mqtt.Client, s AGVStatus) {
	b, _ := json.Marshal(s)
	c.Publish(fmt.Sprintf("agv/%s/status", s.AgvID), 1, false, b)
}

from enum import Enum
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class Mode(str, Enum):
    IDLE = "idle"
    CHARGING = "charging"
    ERROR = "error"

class AgvStatus(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)
    agv_id: str
    battery_level: float
    task_id: str | None = None

def on_status(client, userdata, msg):
    data = AgvStatus.model_validate_json(msg.payload)
    if data.battery_level < 20:
        client.publish(f"task/{data.agv_id}/pause", "{}")
    hub.broadcast(data.model_dump(by_alias=True))

client.message_callback_add("agv/+/status", on_status)

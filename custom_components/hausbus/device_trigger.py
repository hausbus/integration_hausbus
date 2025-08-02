from typing import Any, Callable, Awaitable
from homeassistant.core import HomeAssistant, CALLBACK_TYPE
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
import voluptuous as vol
from homeassistant.components.device_automation.trigger import DEVICE_TRIGGER_BASE_SCHEMA

""" definiert individuelle TriggerEvents z.b. der Taster """
DOMAIN = "hausbus"

TRIGGER_TYPES = {"button_pressed", "button_released", "button_clicked", "button_double_clicked", "button_hold_start", "button_hold_end"}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required("type"): vol.In(TRIGGER_TYPES),
        vol.Required("subtype"): str,
    }
)

async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
  
    device_registry = async_get_device_registry(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        return []

    if device.model == "1-fach Taster":
        BUTTONS = [1]
    elif device.model == "2-fach Taster":
        BUTTONS = [1,2]
    elif device.model == "4-fach Taster":
        BUTTONS = [1,2,3,4]
    elif device.model == "6-fach Taster":
        BUTTONS = [1,2,3,4,5,6]
    elif device.model == "6-fach Taster Gira":
        BUTTONS = [1,2,3,4,5,6]
    else:
      return []
      
    return [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_id,
            "type": trigger_type,
            "subtype": f"button_{btn}",  # z.B. "button_1"
        }
        for trigger_type in TRIGGER_TYPES
        for btn in BUTTONS
    ]

async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: Callable[[dict[str, Any]], Awaitable[None]],
    trigger_info: dict[str, Any],
) -> CALLBACK_TYPE:
    """Verbindet Event-Listener mit Automatisierung."""
    event_type = f"{DOMAIN}_button_event"

    async def handle_event(event):
        if event.data.get("device_id") != config["device_id"]:
            return
        if event.data.get("type") != config["type"]:
            return
        await action({
            "platform": "device",
            "domain": DOMAIN,
            "device_id": config["device_id"],
            "type": config["type"],
        })

    return hass.bus.async_listen(event_type, handle_event)
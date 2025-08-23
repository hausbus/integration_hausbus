"""Support for events of haus-bus pushbuttons (Taster)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import HausbusDevice
from .entity import HausbusEntity

from pyhausbus.de.hausbus.homeassistant.proxy.Taster import Taster
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import EvCovered
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvFree import EvFree
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldStart import EvHoldStart
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldEnd import EvHoldEnd
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvClicked import EvClicked
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvDoubleClick import EvDoubleClick

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging
LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: HausbusConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up an event entity from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_event(channel: HausBusEvent) -> None:
        """Add event entity."""
        async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_event, "EVENTS")


class HausBusEvent(HausbusEntity, EventEntity):
    """Representation of a haus-bus event entity."""

    def __init__(self, instance_id: int, device: HausbusDevice, channel: Taster) -> None:
        """Set up event."""
        super().__init__("event", instance_id, device, channel.getName())

        self._channel = channel
        self._attr_event_types = ["button_pressed", "button_released", "button_clicked", "button_double_clicked", "button_hold_start", "button_hold_end"]

    @staticmethod
    def is_event_channel(class_id: int) -> bool:
        """Check if a class_id is a Taster."""
        return class_id == Taster.CLASS_ID

    def handle_event(self, data: Any) -> None:
        """Handle taster events from Haus-Bus."""

        eventType = {
              EvCovered: "button_pressed",
              EvFree: "button_released",
              EvHoldStart: "button_hold_start",
              EvHoldEnd: "button_hold_end",
              EvClicked: "button_clicked",
              EvDoubleClick: "button_double_clicked",
            }.get(type(data), "unknown")

        LOGGER.debug(f"sending event {eventType}")
        self._trigger_event(eventType)
        self.schedule_update_ha_state()

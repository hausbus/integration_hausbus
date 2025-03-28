"""Support for Haus-Bus switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyhausbus.de.hausbus.homeassistant.proxy.Schalter import Schalter
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.EvOff import (
    EvOff as SchalterEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.EvOn import (
    EvOn as SchalterEvOn,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.data.Status import (
    Status as SchalterStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.schalter.params.EState import EState

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_ON_STATE
from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus switch from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_switch(channel: HausbusEntity) -> None:
        """Add switch from Haus-Bus."""
        if isinstance(channel, HausbusSwitch):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_switch, SWITCH_DOMAIN)


class HausbusSwitch(HausbusEntity, SwitchEntity):
    """Representation of a Haus-Bus switch."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: Schalter,
    ) -> None:
        """Set up switch."""
        super().__init__(channel.__class__.__name__, instance_id, device)

        self._channel = channel
        self._attr_is_on = False

    @staticmethod
    def is_switch_channel(class_id: int) -> bool:
        """Check if a class_id is a switch."""
        return class_id == Schalter.CLASS_ID

    def get_hardware_status(self) -> None:
        """Request status of a switch channel from hardware."""
        self._channel.getStatus()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.off(0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        self._channel.on(0, 0)

    def switch_turn_on(self) -> None:
        """Turn off a switch channel."""
        params = {ATTR_ON_STATE: True}
        self.async_update_callback(**params)

    def switch_turn_off(self) -> None:
        """Turn off a switch channel."""
        params = {ATTR_ON_STATE: False}
        self.async_update_callback(**params)

    def handle_switch_event(self, data: Any) -> None:
        """Handle switch events from Haus-Bus."""
        if isinstance(data, SchalterEvOn):
            self.switch_turn_on()
        if isinstance(data, SchalterStatus):
            if data.getState() == EState.ON:
                self.switch_turn_on()
            else:
                self.switch_turn_off()
        if isinstance(data, (SchalterEvOff)):
            self.switch_turn_off()

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """Switch state push update."""
        state_changed = False
        if ATTR_ON_STATE in kwargs and self._attr_is_on != kwargs[ATTR_ON_STATE]:
            self._attr_is_on = kwargs[ATTR_ON_STATE]
            state_changed = True

        if state_changed:
            self.schedule_update_ha_state()

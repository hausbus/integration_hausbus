"""Support for Haus-Bus binary sensors(Taster)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyhausbus.de.hausbus.homeassistant.proxy.Taster import Taster
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.Enabled import (
    Enabled as TasterEnabled,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import (
    EvCovered as TasterCovered,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvFree import (
    EvFree as TasterFree,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.Status import (
    Status as TasterStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.EState import EState

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_ON_STATE
from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus binary sensor from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_binary_sensor(channel: HausbusEntity) -> None:
        """Add binary sensor from Haus-Bus."""
        if isinstance(channel, HausbusBinarySensor):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_binary_sensor, BINARY_SENSOR_DOMAIN)


class HausbusBinarySensor(HausbusEntity, BinarySensorEntity):
    """Representation of a Haus-Bus binary sensor."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: Taster,
    ) -> None:
        """Set up binary sensor."""
        super().__init__(channel.__class__.__name__, instance_id, device, channel.getName())

        self._channel = channel
        self._attr_is_on = False

    @staticmethod
    def is_binary_sensor_channel(class_id: int, name:str) -> bool:
        """Check if a class_id is a binary sensor."""
        return class_id == Taster.CLASS_ID and not name.startswith("Taster")

    def binary_sensor_covered(self) -> None:
        """Covered binary sensor channel."""
        LOGGER.debug("BinarySensor %s covered (%s)",self._instance_id, self._device.device_id )
        params = {ATTR_ON_STATE: True}
        self.async_update_callback(**params)

    def binary_sensor_free(self) -> None:
        """Freed binary sensor channel."""
        LOGGER.debug("BinarySensor %s free (%s)",self._instance_id, self._device.device_id )
        params = {ATTR_ON_STATE: False}
        self.async_update_callback(**params)

    def handle_binary_sensor_event(self, data: Any) -> None:
        """Handle binary sensor events from Haus-Bus."""
        if isinstance(data, TasterCovered):
            self.binary_sensor_covered()
        if isinstance(data, TasterFree):
            self.binary_sensor_free()    
        if isinstance(data, TasterStatus):
            if data.getState() == EState.PRESSED:
                self.binary_sensor_covered()
            else:
                self.binary_sensor_free()
        if isinstance(data, (TasterEnabled)):
            self.binary_sensor_covered()

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """Binary sensor state push update."""
        state_changed = False
        if ATTR_ON_STATE in kwargs and self._attr_is_on != kwargs[ATTR_ON_STATE]:
            self._attr_is_on = kwargs[ATTR_ON_STATE]
            state_changed = True

        if state_changed:
            self.schedule_update_ha_state()

"""Support for Number configuration parameters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import ATTR_ON_STATE
from .device import HausbusDevice
from .entity import HausbusEntity
from pyhausbus.ABusFeature import ABusFeature

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging
LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus number entity from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_number(channel: HausBusNumber) -> None:
        """Add HausbusNumber."""
        async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_number, NUMBER_DOMAIN)


class HausBusNumber(HausbusEntity, NumberEntity):
    """Representation of a hausbus number entity."""

    def __init__(
        self,
        entity: HausbusEntity,
    ) -> None:
        """Set up hausbus number."""
        super().__init__(f"{entity._type}_config", entity._instance_id, entity._device, f"{entity._attr_name}_testParameter")
        self.entity = entity
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 10.0
        self._attr_native_step = 1.0
        #self._attr_native_unit_of_measurement = "s"
        self._value=1
        LOGGER.debug(f"HausBusNumber created for entity {entity}")

    @property
    def native_value(self):
      return self._value

    async def async_set_native_value(self, value: float):
        LOGGER.debug(f"async_set_native_value value {value}")
        self._value = value
        self.async_write_ha_state()
        
    async def async_added_to_hass(self):
      """Ensure initial state is written."""
      await super().async_added_to_hass()
      self.async_write_ha_state()

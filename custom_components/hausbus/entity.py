"""Representation of a Haus-Bus Entity."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback

from homeassistant.helpers.entity import Entity

from .device import HausbusDevice

import logging
LOGGER = logging.getLogger(__name__)

class HausbusEntity(Entity):
    """Common base for HausBus Entities."""

    _attr_has_entity_name = True

    def __init__(
        self, channel_type: str, instance_id: int, device: HausbusDevice, channel_name: str
    ) -> None:
        """Set up channel."""
        self._type = channel_type.lower()
        self._instance_id = instance_id
        self._device = device
        self._attr_unique_id = f"{self._device.device_id}-{self._type}{self._instance_id}"
        self._attr_device_info = self._device.device_info
        self._attr_translation_key = self._type
        self._attr_name = channel_name
        self._extra_state_attributes = {}
        self._configuration = {}
        #LOGGER.debug(f"created unique {self._attr_unique_id} for device {device.device_id} channel_name {channel_name} instance_id {instance_id}")

    @property
    def extra_state_attributes(self):
      #LOGGER.debug(f"extra_state_attributes {self._extra_state_attributes}")
      return self._extra_state_attributes

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """State push update."""
        raise NotImplementedError
      
    async def async_added_to_hass(self):
      """Called when entity is added to HA."""


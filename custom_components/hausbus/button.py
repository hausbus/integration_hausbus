"""Support for UI Buttons."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from collections.abc import Callable, Coroutine


if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging
LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant,config_entry: HausbusConfigEntry,async_add_entities: AddEntitiesCallback) -> None:
    """Set up a button from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_button(channel: HausbusButton) -> None:
        """Add button entity."""
        async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_button, BUTTON_DOMAIN)


class HausbusButton(ButtonEntity):
    """Representation of a button."""

    def __init__(self,unique_id:str,name:str,callback: Callable[[],Coroutine[Any, Any, None]]) -> None:
        """Set up button."""

        self._attr_has_entity_name = True
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._callback = callback

    async def async_press(self) -> None:
        """Is called if a button is pressed."""
        LOGGER.debug(f"button pressed {self._attr_name}")
        await self._callback()

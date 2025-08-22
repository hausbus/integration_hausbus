"""The Haus-Bus integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import TypeAlias
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .gateway import HausbusGateway
from .const import DOMAIN

#, Platform.NUMBER
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH, Platform.BINARY_SENSOR, Platform.SENSOR, Platform.EVENT, Platform.COVER]

_LOGGER = logging.getLogger(__name__)


@dataclass
class HausbusConfig:
    """Class for Hausbus ConfigEntry."""

    #from .gateway import HausbusGateway  # pylint: disable=import-outside-toplevel

    gateway: HausbusGateway


HausbusConfigEntry: TypeAlias = ConfigEntry[HausbusConfig]



async def device_discovery_task(hass: HomeAssistant, gateway: HausbusGateway) -> None:
    """Device discovery is repeated every minute."""
    while True:
        # Perform device discovery
        hass.async_add_executor_job(gateway.home_server.searchDevices)
        # Wait for 60 seconds
        await asyncio.sleep(60)


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    gateway = HausbusGateway(hass, entry)
    entry.runtime_data = HausbusConfig(gateway)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    

    _LOGGER.debug("start searching devices")

    # search devices after adding all callbacks to the gateway object repeatedly
    entry.async_create_background_task(
        hass,
        target=device_discovery_task(hass, gateway),
        name="Hausbus device discovery task",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data.gateway
    gateway.home_server.removeBusEventListener(gateway)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


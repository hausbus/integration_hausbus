"""Integration for all haus-bus.de modules"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import TypeAlias
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from .gateway import HausbusGateway
from .const import DOMAIN

# , Platform.NUMBER
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH, Platform.BINARY_SENSOR, Platform.SENSOR, Platform.EVENT, Platform.COVER, Platform.BUTTON]

LOGGER = logging.getLogger(__name__)


@dataclass
class HausbusConfig:
    """Class for Hausbus ConfigEntry."""

    gateway: HausbusGateway


HausbusConfigEntry: TypeAlias = ConfigEntry[HausbusConfig]

# async def device_discovery_task(hass: HomeAssistant, gateway: HausbusGateway) -> None:
#    """Device discovery is repeated every minute."""
#    while True:
#        # Perform device discovery
#        hass.async_add_executor_job(gateway.home_server.searchDevices)
#        # Wait for 60 seconds
#        await asyncio.sleep(60)


async def async_setup_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Set up Haus-Bus integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    gateway = HausbusGateway(hass, entry)
    entry.runtime_data = HausbusConfig(gateway)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Lokale Icons für die Devices setzen
    await set_local_device_icons(hass)

    # Creates a button to manually start device discovery
    hass.async_create_task(gateway.createDiscoveryButtonAndStartDiscovery())

    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Haus-Bus integration (global services etc.)."""

    async def discover_devices(call: ServiceCall):
      entries = hass.config_entries.async_entries(DOMAIN)
      if not entries:
        raise HomeAssistantError("No Hausbus-Gateway available")

      LOGGER.debug("Search devices service called")
      gateway = entries[0].runtime_data.gateway
      gateway.home_server.searchDevices()

    hass.services.async_register(DOMAIN, "discover_devices", discover_devices)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HausbusConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data.gateway

    gateway.home_server.removeBusEventListener(gateway)
    hass.services.async_remove(DOMAIN, "discover_devices")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def set_local_device_icons(hass: HomeAssistant):
    registry: dr.DeviceRegistry = dr.async_get(hass)
    for device_entry in registry.devices.values():
        if device_entry.manufacturer == "Haus-Bus":
            # device_entry.entry_type und configuration_url kann man nicht direkt ändern
            # Stattdessen: Manuelles Override geht nur über ein DeviceUpdate
            registry.async_update_device(
                device_entry.id,
                configuration_url="/local/hausbus/icon.png"
            )

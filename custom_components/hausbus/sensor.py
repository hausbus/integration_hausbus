"""Support for Haus-Bus temperatur sensor."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING
from pyhausbus.ABusFeature import ABusFeature

from pyhausbus.de.hausbus.homeassistant.proxy.Temperatursensor import Temperatursensor
from pyhausbus.de.hausbus.homeassistant.proxy.temperatursensor.data.EvStatus import (
    EvStatus as TemperatursensorEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.temperatursensor.data.Status import (
    Status as TemperatursensorStatus,
)

from pyhausbus.de.hausbus.homeassistant.proxy.Helligkeitssensor import Helligkeitssensor
from pyhausbus.de.hausbus.homeassistant.proxy.helligkeitssensor.data.EvStatus import (
    EvStatus as HelligkeitssensorEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.helligkeitssensor.data.Status import (
    Status as HelligkeitssensorStatus,
)

from pyhausbus.de.hausbus.homeassistant.proxy.Feuchtesensor import Feuchtesensor
from pyhausbus.de.hausbus.homeassistant.proxy.feuchtesensor.data.EvStatus import (
    EvStatus as FeuchtesensorEvStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.feuchtesensor.data.Status import (
    Status as FeuchtesensorStatus,
)

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.const import LIGHT_LUX, PERCENTAGE, UnitOfTemperature

from .device import HausbusDevice
from .entity import HausbusEntity

import logging
_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HausbusConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus sensor from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_sensor(channel: HausbusEntity) -> None:
        """Add temperatur sensor from Haus-Bus."""
        if isinstance(channel, HausbusSensor):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_sensor, SENSOR_DOMAIN)


class HausbusSensor(HausbusEntity, SensorEntity):
    """Representation of a Haus-Bus sensor."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: ABusFeature,
    ) -> None:
        """Set up sensor."""
        super().__init__(channel.__class__.__name__, instance_id, device, channel.getName())

        self._channel = channel
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = None

    @staticmethod
    def is_sensor_channel(class_id: int) -> bool:
        """Check if a class_id is a sensor."""
        return class_id in (Temperatursensor.CLASS_ID, Helligkeitssensor.CLASS_ID, Feuchtesensor.CLASS_ID)

    def get_hardware_status(self) -> None:
        """Request status of a sensor channel from hardware."""
        self._channel.getStatus()


class HausbusTemperaturSensor(HausbusSensor):
    """Representation of a Haus-Bus Temperatursensor."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: Temperatursensor,
    ) -> None:
        """Set up sensor."""
        super().__init__(instance_id, device, channel)

        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_value = None

    def handle_sensor_event(self, data: Any) -> None:
        """Handle temperatur sensor events from Haus-Bus."""
        
        if isinstance(data, (TemperatursensorEvStatus,TemperatursensorStatus)):
          value = float(data.getCelsius()) + float(data.getCentiCelsius()) / 100
          _LOGGER.debug(f"Temperatur empfangen: {value} °C")
          self._attr_native_value = value
          self.schedule_update_ha_state() 


class HausbusHelligkeitsSensor(HausbusSensor):
    """Representation of a Haus-Bus HelligkeitsSensor."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: Helligkeitssensor,
    ) -> None:
        """Set up sensor."""
        super().__init__(instance_id, device, channel)

        self._attr_native_unit_of_measurement = LIGHT_LUX
        self._attr_device_class = SensorDeviceClass.ILLUMINANCE
        self._attr_native_value = None

    def handle_sensor_event(self, data: Any) -> None:
        """Handle helligkeits sensor events from Haus-Bus."""
        
        if isinstance(data, (HelligkeitssensorEvStatus,HelligkeitssensorStatus)):
          value = float(data.getBrightness())
          _LOGGER.debug(f"Helligkeit empfangen: {value} lx")
          self._attr_native_value = value
          self.schedule_update_ha_state() 

class HausbusFeuchteSensor(HausbusSensor):
    """Representation of a Haus-Bus LuftfeuchteSensor."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: Feuchtesensor,
    ) -> None:
        """Set up sensor."""
        super().__init__(instance_id, device, channel)

        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.HUMIDITY
        self._attr_native_value = None

    def handle_sensor_event(self, data: Any) -> None:
        """Handle Feuchtesensor events from Haus-Bus."""
        
        if isinstance(data, (FeuchtesensorEvStatus, FeuchtesensorStatus)):
          value = float(data.getRelativeHumidity()) + float(data.getCentiHumidity()) / 100
          _LOGGER.debug(f"Feuchtigkeit empfangen: {value} %")
          self._attr_native_value = value
          self.schedule_update_ha_state() 

"""Representation of a Haus-Bus gateway."""

from __future__ import annotations
import logging
import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, cast
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.Controller import Controller,EIndex
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import (
    Configuration,
)
from pyhausbus.Templates import Templates
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.RemoteObjects import (
    RemoteObjects,
)

import re
from pyhausbus.HausBusUtils import HOMESERVER_DEVICE_ID
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
#from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .device import HausbusDevice
from .entity import HausbusEntity
from .light import (
    Dimmer,
    HausbusDimmerLight,
    HausbusLedLight,
    HausbusLight,
    HausbusRGBDimmerLight,
    Led,
    RGBDimmer,
)
from .switch import HausbusSwitch, Schalter
#from .number import HausBusNumber
from .sensor import HausbusSensor, HausbusTemperaturSensor, Temperatursensor, HausbusHelligkeitsSensor, Helligkeitssensor, HausbusFeuchteSensor, Feuchtesensor, HausbusAnalogEingang, AnalogEingang
from .binary_sensor import HausbusBinarySensor

from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import EvCovered
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvFree import EvFree
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldStart import EvHoldStart
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldEnd import EvHoldEnd
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvClicked import EvClicked
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvDoubleClick import EvDoubleClick
from pyhausbus.de.hausbus.homeassistant.proxy.Taster import Taster

DOMAIN = "hausbus"

LOGGER = logging.getLogger(__name__)

class HausbusGateway(IBusDataListener):  # type: ignore[misc]
    """Manages a single Haus-Bus gateway."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.devices: dict[str, HausbusDevice] = {}
        self.channels: dict[str, dict[tuple[str, str], HausbusEntity]] = {}
        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)
        self._new_channel_listeners: dict[
            str, Callable[[HausbusEntity], Coroutine[Any, Any, None]]
        ] = {}
        
        # Listener f�r state_changed registrieren
        #self.hass.bus.async_listen("state_changed", self._state_changed_listener)
        
        asyncio.run_coroutine_threadsafe(self.async_delete_devices(), self.hass.loop)

    def add_device(self, device_id: str, module: ModuleId) -> None:
        """Add a new Haus-Bus Device to this gateway's device list."""
        if device_id not in self.devices:
            self.devices[device_id] = HausbusDevice(
                device_id,
                module.getFirmwareId().getTemplateId()
                + " "
                + str(module.getMajorRelease())
                + "."
                + str(module.getMinorRelease()),
                module.getName(),
                module.getFirmwareId(),
            )
            
        if device_id not in self.channels:
            self.channels[device_id] = {}

    def get_device(self, object_id: ObjectId) -> HausbusDevice | None:
        """Get the device referenced by ObjectId from the devices list."""
        return self.devices.get(str(object_id.getDeviceId()))

    def get_channel_list(
        self, object_id: ObjectId
    ) -> dict[tuple[str, str], HausbusEntity] | None:
        """Get the channel list of a device referenced by ObjectId."""
        return self.channels.get(str(object_id.getDeviceId()))

    def get_channel_id(self, object_id: ObjectId) -> tuple[str, str]:
        """Get the channel identifier from an ObjectId."""
        return (str(object_id.getClassId()), str(object_id.getInstanceId()))

    def get_channel(self, object_id: ObjectId) -> HausbusEntity | None:
        """Get channel from channel list."""
        channels = self.get_channel_list(object_id)
        if channels is not None:
            channel_id = self.get_channel_id(object_id)
            return channels.get(channel_id)
        return None

    def create_light_entity(
        self, device: HausbusDevice, instance: ABusFeature, object_id: ObjectId
    ) -> HausbusLight | None:
        """Create a light entity according to the type of instance."""
        if isinstance(instance, Dimmer):
            return HausbusDimmerLight(
                object_id.getInstanceId(),
                device,
                instance,
            )
        if isinstance(instance, Led):
            return HausbusLedLight(
                object_id.getInstanceId(),
                device,
                instance,
            )
        if isinstance(instance, RGBDimmer):
            return HausbusRGBDimmerLight(
                object_id.getInstanceId(),
                device,
                instance,
            )
        return None

    def add_light_channel(self, instance: ABusFeature, object_id: ObjectId) -> None:
        """Add a new Haus-Bus Light Channel to this gateway's channel list."""

        device = self.get_device(object_id)
        if device is not None:
            light = self.create_light_entity(device, instance, object_id)
            channel_list = self.get_channel_list(object_id)
            if light is not None and channel_list is not None:
                channel_list[self.get_channel_id(object_id)] = light
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners[LIGHT_DOMAIN](light), self.hass.loop
                ).result()
                light.get_hardware_status()
                
                #if isinstance(light, HausbusDimmerLight):
                #  LOGGER.debug(f"registering numberEntity {light._configTest} for light {light}")
                #  asyncio.run_coroutine_threadsafe(
                #    self._new_channel_listeners[NUMBER_DOMAIN](light._configTest), self.hass.loop
                #  ).result()

    def create_switch_entity(
        self, device: HausbusDevice, instance: ABusFeature, object_id: ObjectId
    ) -> HausbusSwitch | None:
        """Create a switch entity according to the type of instance."""
        if isinstance(instance, Schalter):
            return HausbusSwitch(
                object_id.getInstanceId(),
                device,
                instance,
            )
        return None

    def add_switch_channel(self, instance: ABusFeature, object_id: ObjectId) -> None:
        """Add a new Haus-Bus Switch Channel to this gateway's channel list."""

        device = self.get_device(object_id)
        if device is not None:
            switch = self.create_switch_entity(device, instance, object_id)
            channel_list = self.get_channel_list(object_id)
            if switch is not None and channel_list is not None:
                channel_list[self.get_channel_id(object_id)] = switch
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners[SWITCH_DOMAIN](switch), self.hass.loop
                ).result()
                switch.get_hardware_status()

    def create_sensor_entity(
        self, device: HausbusDevice, instance: ABusFeature, object_id: ObjectId
    ) -> HausbusSensor | None:
        """Create a sensor entity according to the type of instance."""
        if isinstance(instance, Temperatursensor):
            return HausbusTemperaturSensor(
                object_id.getInstanceId(),
                device,
                instance,
            )
        elif isinstance(instance, Helligkeitssensor):
            return HausbusHelligkeitsSensor(
                object_id.getInstanceId(),
                device,
                instance,
            )    
        elif isinstance(instance, Feuchtesensor):
            return HausbusFeuchteSensor(
                object_id.getInstanceId(),
                device,
                instance,
            )    
        elif isinstance(instance, AnalogEingang):
            return HausbusAnalogEingang(
                object_id.getInstanceId(),
                device,
                instance,
            )    
        return None

    def add_sensor_channel(self, instance: ABusFeature, object_id: ObjectId) -> None:
        """Add a new Haus-Bus sensor Channel to this gateway's channel list."""

        device = self.get_device(object_id)
        if device is not None:
            sensor = self.create_sensor_entity(device, instance, object_id)
            channel_list = self.get_channel_list(object_id)
            if sensor is not None and channel_list is not None:
                channel_list[self.get_channel_id(object_id)] = sensor
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners[SENSOR_DOMAIN](sensor), self.hass.loop
                ).result()
                sensor.get_hardware_status()

    def create_binary_sensor_entity(
        self, device: HausbusDevice, instance: ABusFeature, object_id: ObjectId
    ) -> HausbusSensor | None:
        """Create a binary sensor entity according to the type of instance."""
        if isinstance(instance, Taster):
            return HausbusBinarySensor(
                object_id.getInstanceId(),
                device,
                instance,
            )
        
        return None

    def add_binary_sensor_channel(self, instance: ABusFeature, object_id: ObjectId) -> None:
        """Add a new Haus-Bus binary sensor Channel to this gateway's channel list."""

        device = self.get_device(object_id)
        if device is not None:
            binary_sensor = self.create_binary_sensor_entity(device, instance, object_id)
            channel_list = self.get_channel_list(object_id)
            if binary_sensor is not None and channel_list is not None:
                channel_list[self.get_channel_id(object_id)] = binary_sensor
                asyncio.run_coroutine_threadsafe(
                    self._new_channel_listeners[BINARY_SENSOR_DOMAIN](binary_sensor), self.hass.loop
                ).result()
                binary_sensor.get_hardware_status()
                
    def add_channel(self, instance: ABusFeature) -> None:
        """Add a new Haus-Bus Channel to this gateways channel list."""
        object_id = ObjectId(instance.getObjectId())
        channel_list = self.get_channel_list(object_id)
        if (
            channel_list is not None
            and self.get_channel_id(object_id) not in channel_list
        ):
            if HausbusLight.is_light_channel(object_id.getClassId()):
              LOGGER.debug(f"create light channel for {instance}")
              self.add_light_channel(instance, object_id)
            elif HausbusSwitch.is_switch_channel(object_id.getClassId()):
              LOGGER.debug(f"create switch channel for {instance}")
              self.add_switch_channel(instance, object_id)
            elif HausbusBinarySensor.is_binary_sensor_channel(object_id.getClassId()):
              LOGGER.debug(f"create binary sensor channel for {instance}")
              self.add_binary_sensor_channel(instance, object_id)
            elif HausbusSensor.is_sensor_channel(object_id.getClassId()):
              LOGGER.debug(f"create sensor channel for {instance}")
              self.add_sensor_channel(instance, object_id)

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""
        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()
        deviceId = object_id.getDeviceId()
        templates = Templates.get_instance()

        # ignore messages sent from this module
        if deviceId == HOMESERVER_DEVICE_ID or deviceId == 9999 or deviceId == 12222:
            return

        if deviceId in [110, 503, 1000,1541,3422,4000,4001,4002,4003,4004,4005,4009,4096,5068,8192,8270,11581,12223,12622,13976,14896,18343,19075,20043,21336,22909,24261,25661,25874,28900,29725,3423,4006,4008]:
            return

        LOGGER.debug(f"busDataReceived with data = {data}")

        controller = Controller(object_id.getValue())

        # Bei ModuleId -> getConfiguration
        if isinstance(data, ModuleId):
          LOGGER.debug(f"got moduleId of {object_id.getDeviceId()} with data: {data}")
          self.add_device(str(object_id.getDeviceId()),data)
          controller.getConfiguration()
          return
        
        # Bei unbekanntem Gerät -> ModuleId abfragen 
        device = self.get_device(object_id)
        if device is None:
          LOGGER.debug(f"got event of unknown device {object_id.getDeviceId()} with data: {data} -> calling getModuleId")
          controller.getModuleId(EIndex.RUNNING)
          return

        # Bei Configuration -> getRemoteObjects 
        if isinstance(data, Configuration):
          LOGGER.debug(f"got configuration of {object_id.getDeviceId()} with data: {data}")
          config = cast(Configuration, data)
          device = self.get_device(object_id)
          if device is not None:
            device.set_type(config.getFCKE())
            
            # Mit der Konfiguration registrieren wir das Device bei HASS
            asyncio.run_coroutine_threadsafe(self.async_create_device_registry(device), self.hass.loop)
                
            controller.getRemoteObjects()
            return

        # Bei RemoteObjects  -> channel anlegen 
        if isinstance(data, RemoteObjects):
          LOGGER.debug(f"got remoteObjects of {object_id.getDeviceId()} with data: {data}")
            
          device = self.get_device(object_id)
          if device is not None:
            instances: list[ABusFeature] = self.home_server.getDeviceInstances(object_id.getValue(), data)
            
            # Inputs merken für die Trigger
            inputs = []
            for instance in instances:
              instanceObjectId = ObjectId(instance.getObjectId())
              name = templates.get_feature_name_from_template(device.firmware_id, device.fcke, instanceObjectId.getClassId(), instanceObjectId.getInstanceId())
              LOGGER.debug(f"name for firmwareId {device.firmware_id}, fcke: {device.fcke}, classId {instanceObjectId.getClassId()}, instanceId {instanceObjectId.getInstanceId()} is {name}")
              
              if deviceId == 22784:
                name = f"Object {instance.getObjectId()}"
              
              instance.setName(name)
              if name is not None:
                
                # Bei Tastern keinen BinaryChannel anlegen, sondern nur bei anderen Eingängen
                if not name.startswith("Taster"):
                  self.add_channel(instance)
                
                # Bei allen Taster Instanzen die Events anlegen, weil da auch ein Taster angeschlossen sein kann
                if isinstance(instance, Taster):
                  inputs.append(name)
            
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN][device.hass_device_entry.id] = {"inputs": inputs}
            LOGGER.debug(f"{inputs} inputs angemeldet {device.hass_device_entry.id} deviceId {deviceId}")
            return
        
        # https://developers.home-assistant.io/docs/core/entity/event/
        if isinstance(data, (EvCovered,EvFree,EvHoldStart,EvHoldEnd,EvClicked,EvDoubleClick)):
          name = templates.get_feature_name_from_template(device.firmware_id, device.fcke, object_id.getClassId(), object_id.getInstanceId())
          self.generate_device_trigger(data, device.hass_device_entry.id, name)
        
 
        # Alles andere wird an die jeweiligen Channel weitergeleitet      
        channel = self.get_channel(object_id)
        
        # light event handling
        if isinstance(channel, HausbusLight):
          LOGGER.debug(f" handle_light_event {channel} {data}")
          channel.handle_light_event(data)
        # switch event handling
        elif isinstance(channel, HausbusSwitch):
          LOGGER.debug(f" handle_switch_event {channel} {data}")
          channel.handle_switch_event(data)
        # binary sensor event handling
        elif isinstance(channel, HausbusBinarySensor):
          LOGGER.debug(f" handle_binary_sensor_event {channel} {data}")
          channel.handle_binary_sensor_event(data)
        # temperatur sensor event handling
        elif isinstance(channel, (HausbusTemperaturSensor, HausbusHelligkeitsSensor, HausbusFeuchteSensor, HausbusAnalogEingang)):
          LOGGER.debug(f" handle_sensor_event {channel} {data}")
          channel.handle_sensor_event(data)
        else:
          LOGGER.debug(f"nicht unterstützter channel type {channel}")

    def generate_device_trigger(self, data, hass_device_id, name):
        eventType = {
              EvCovered: "button_pressed",
              EvFree: "button_released",
              EvHoldStart: "button_hold_start",
              EvHoldEnd: "button_hold_end",
              EvClicked: "button_clicked",
              EvDoubleClick: "button_double_clicked",
            }.get(type(data), "unknown")

        LOGGER.debug(f"sending trigger {eventType} name {name} hass_device_id {hass_device_id}")
        self.hass.loop.call_soon_threadsafe(
          lambda: self.hass.bus.async_fire(
            "hausbus_button_event",
            {
              "device_id": hass_device_id,
              "type": eventType,
              "subtype": name,
            }
          )
        )

    def register_platform_add_channel_callback(
        self,
        add_channel_callback: Callable[[HausbusEntity], Coroutine[Any, Any, None]],
        platform: str,
    ) -> None:
        """Register add channel callbacks."""
        self._new_channel_listeners[platform] = add_channel_callback
    
    def extract_final_number(self, text: str) -> int | None:
      match = re.search(r"(\d+)$", text.strip())
      if match:
        return int(match.group(1))
      return None

    async def async_create_device_registry(self, device: HausbusDevice):
      device_registry = async_get_device_registry(self.hass)
      device_entry = device_registry.async_get_or_create(
        config_entry_id=self.config_entry.entry_id,
        identifiers={(DOMAIN, device.device_id)},
        manufacturer="HausBus",
        model=device.model_id,
        name=device.name
      )
      LOGGER.debug(f"hassEntryId = {device_entry.id}")
      device.setHassDeviceEntry(device_entry)

    async def async_delete_devices(self):
      device_registry = async_get_device_registry(self.hass)
      #device_registry.async_remove_device("fc90771cff9ddaaeb2568f20ec2f8711")

    #@callback
    #def _state_changed_listener(self, event):
    #    """Prüfen, ob sich die Attribute dieser Entity geändert haben"""
    #    entity_id = event.data.get("entity_id")
    #
    #   LOGGER.debug(f" event {event}")
    #
    #    for channel_name, entities in self.channels.items():  # über alle Channels
    #      for key, entity in entities.items():             # über alle Entities im Channel
    #        if entity.entity_id==entity_id:
    #            LOGGER.debug(f" entity_id 2 {entity_id} gefunden {entity}")
    #                    
    #    old_state = event.data.get("old_state")
    #    new_state = event.data.get("new_state")
    #
    #    old_attr = old_state.attributes if old_state else {}
    #    new_attr = new_state.attributes if new_state else {}
    #
        # Pr�fen, ob sich das beobachtete Attribut ge�ndert hat
        #for key in self._attributes.keys():
            #if old_attr.get(key) != new_attr.get(key):
              #LOGGER.debug(f" key {key} old_attr {old_attr.get(key)} new_attr {new_attr.get(key)}")

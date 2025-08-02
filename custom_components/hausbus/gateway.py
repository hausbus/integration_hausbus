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
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import EvCovered

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

    def add_channel(self, instance: ABusFeature) -> None:
        """Add a new Haus-Bus Channel to this gateways channel list."""
        object_id = ObjectId(instance.getObjectId())
        channel_list = self.get_channel_list(object_id)
        if (
            channel_list is not None
            and self.get_channel_id(object_id) not in channel_list
        ):
            if HausbusLight.is_light_channel(object_id.getClassId()):
                self.add_light_channel(instance, object_id)
            if HausbusSwitch.is_switch_channel(object_id.getClassId()):
                self.add_switch_channel(instance, object_id)

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""
        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()
        deviceId = object_id.getDeviceId()
        templates = Templates.get_instance()

        # ignore messages sent from this module
        if deviceId == HOMESERVER_DEVICE_ID or deviceId == 9999 or deviceId == 12222:
            return

        if deviceId in [110, 503, 1000,1541,3422,4000,4001,4002,4003,4004,4005,4009,4096,5068,8192,8270,11581,12223,12622,13976,14896,18343,19075,20043,21336,22784,22909,24261,25661,25874,28900,29725,3423,4006,4008]:
            return

        controller = Controller(object_id.getValue())

        ''' Bei ModuleId -> getConfiguration '''
        if isinstance(data, ModuleId):
          LOGGER.debug(f"got moduleId of {object_id.getDeviceId()} with data: {data}")
          self.add_device(str(object_id.getDeviceId()),data)
          controller.getConfiguration()
          return
        
        ''' Bei Configuration -> getRemoteObjects '''    
        if isinstance(data, Configuration):
          LOGGER.debug(f"got configuration of {object_id.getDeviceId()} with data: {data}")
          config = cast(Configuration, data)
          device = self.get_device(object_id)
          if device is not None:
            device.set_type(config.getFCKE())
            device_registry = await async_get_device_registry(self.hass)
            device_entry = device_registry.async_get_or_create(
              config_entry_id=self.config_entry.entry_id,
              identifiers={(DOMAIN, device.model_id)},
              manufacturer="HausBus",
              model=device.model_id,
              name=device.name,
              )
            LOGGER.debug("hassEntryId = {device_entry.id}")
            device.setHassDeviceEntry(device_entry)
                
            controller.getRemoteObjects()
            return

        ''' Bei Configuration -> channel anlegen '''    
        if isinstance(data, RemoteObjects):
          LOGGER.debug(f"got remoteObjects of {object_id.getDeviceId()} with data: {data}")
            
          device = self.get_device(object_id)
          if device is not None:
            instances: list[ABusFeature] = self.home_server.getDeviceInstances(object_id.getValue(), data)
            for instance in instances:
              instanceObjectId = ObjectId(instance.getObjectId())
              name = templates.get_feature_name_from_template(device.firmware_id, device.fcke, instanceObjectId.getClassId(), instanceObjectId.getInstanceId())
              LOGGER.debug(f"name for firmwareId {device.firmware_id}, fcke: {device.fcke}, classId {instanceObjectId.getClassId()}, instanceId {instanceObjectId.getInstanceId()} is {name}")
              instance.setName(name)
              if name is not None:
                self.add_channel(instance)
            return
        
        ''' Bei unbekanntem Gerät -> ModuleId abfragen '''
        device = self.get_device(object_id)
        if device is None:
          LOGGER.debug(f"got event of unknown device {object_id.getDeviceId()} with data: {data} -> calling getModuleId")
          controller.getModuleId(EIndex.RUNNING)
          return

        ''' Tasterevents (dazu gibt es keine Entity '''
        if isinstance(data, EvCovered):
          name = templates.get_feature_name_from_template(device.firmware_id, device.fcke, object_id.getClassId(), object_id.getInstanceId())
          buttonName = f"button_{self.extract_final_number(name)}"
          hass_device_id = device.hass_device_entry.id
          LOGGER.debug(f"got evConvered of {object_id}, name = {name}, buttonName = {buttonName}, hassDeviceId = {hass_device_id}")
          
          self.hass.bus.async_fire(
            "hausbus_button_event",
            {
              "device_id": hass_device_id,
              "type": "button_pressed", 
              "subtype": buttonName,
            }
          )
          return
 
        ''' Alles andere wird an die jeweiligen Channel weitergeleitet '''        
        channel = self.get_channel(object_id)
        # light event handling
        if isinstance(channel, HausbusLight):
          channel.handle_light_event(data)
        # switch event handling
        elif isinstance(channel, HausbusSwitch):
          channel.handle_switch_event(data)
        else:
          LOGGER.debug(f"nicht unterstützter channel type {channel}")

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

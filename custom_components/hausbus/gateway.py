"""Representation of a Haus-Bus gateway."""

from __future__ import annotations
import logging
import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, cast
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.BusDataMessage import BusDataMessage
from pyhausbus.de.hausbus.homeassistant.proxy.Controller import Controller, EIndex
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.Configuration import Configuration
from pyhausbus.Templates import Templates
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.RemoteObjects import RemoteObjects

import re
from pyhausbus.HausBusUtils import HOMESERVER_DEVICE_ID
from pyhausbus.HomeServer import HomeServer
from pyhausbus.IBusDataListener import IBusDataListener
from pyhausbus.ObjectId import ObjectId

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
# from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .device import HausbusDevice
from .entity import HausbusEntity
from .light import (Dimmer,HausbusDimmerLight,HausbusLedLight,HausbusBackLight,HausbusRGBDimmerLight,Led,LogicalButton,RGBDimmer)
from .switch import HausbusSwitch, Schalter
from .cover import HausbusCover, Rollladen
# from .number import HausBusNumber
from .sensor import HausbusTemperaturSensor, Temperatursensor, HausbusHelligkeitsSensor, Helligkeitssensor, HausbusFeuchteSensor, Feuchtesensor, HausbusAnalogEingang, AnalogEingang
from .binary_sensor import HausbusBinarySensor
from .event import HausBusEvent
from .button import HausbusButton

from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import EvCovered
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvFree import EvFree
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldStart import EvHoldStart
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldEnd import EvHoldEnd
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvClicked import EvClicked
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvDoubleClick import EvDoubleClick
from pyhausbus.de.hausbus.homeassistant.proxy.Taster import Taster
from pyhausbus.de.hausbus.homeassistant.proxy.PowerMeter import PowerMeter
from custom_components.hausbus.sensor import HausbusPowerMeter

DOMAIN = "hausbus"

LOGGER = logging.getLogger(__name__)


class HausbusGateway(IBusDataListener):  # type: ignore[misc]
    """Manages a Haus-Bus gateway."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the system."""
        self.hass = hass
        self.config_entry = config_entry
        self.devices: dict[str, HausbusDevice] = {}
        self.channels: dict[str, dict[tuple[str, str], HausbusEntity]] = {}
        self.events: dict[int, HausBusEvent] = {}
        self.home_server = HomeServer()
        self.home_server.addBusEventListener(self)
        self._new_channel_listeners: dict[
            str, Callable[[HausbusEntity], Coroutine[Any, Any, None]]
        ] = {}

        # Listener für state_changed registrieren
        # self.hass.bus.async_listen("state_changed", self._state_changed_listener)

        asyncio.run_coroutine_threadsafe(self.async_delete_devices(), self.hass.loop)

    async def createDiscoveryButtonAndSearchDevices(self):
      """Creates a Button to manually start device discovery and automatically starts discovery once"""

      async def discovery_callback():
        LOGGER.debug("searchDevices")
        self.hass.async_add_executor_job(self.home_server.searchDevices)

      _discoveryButton = HausbusButton("hausbus_discovery_button", "Discover Haus-Bus Devices", discovery_callback)
      asyncio.run_coroutine_threadsafe(self._new_channel_listeners[BUTTON_DOMAIN](_discoveryButton), self.hass.loop)

      self.hass.services.async_register(DOMAIN, "discover_devices", discovery_callback)
      await discovery_callback()

    def add_device(self, device_id: str, module: ModuleId) -> None:
        """Add a new Haus-Bus Device to this gateway's device list."""
        if device_id not in self.devices:
            self.devices[device_id] = HausbusDevice(device_id,module.getFirmwareId().getTemplateId()+" "+str(module.getMajorRelease())+"."+str(module.getMinorRelease()),module.getName(),module.getFirmwareId())

        if device_id not in self.channels:
            self.channels[device_id] = {}

    def get_device(self, object_id: ObjectId) -> HausbusDevice | None:
        """Get the device referenced by ObjectId from the devices list."""
        return self.devices.get(str(object_id.getDeviceId()))

    def get_event_entity(self, object_id: int) -> HausBusEvent | None:
        """Get the event referenced by ObjectId."""
        return self.events.get(object_id)

    def get_channel_list(self, object_id: ObjectId) -> dict[tuple[str, str], HausbusEntity] | None:
        """Get the channel list of a device referenced by ObjectId."""
        return self.channels.get(str(object_id.getDeviceId()))

    def get_channel_id(self, object_id: ObjectId) -> tuple[str, str]:
        """Get the channel identifier from an ObjectId."""
        return (str(object_id.getClassId()), str(object_id.getInstanceId()))

    def get_channel(self, object_id: ObjectId) -> HausbusEntity | None:
        """Get channel for to a ObjectId."""
        channels = self.get_channel_list(object_id)
        if channels is not None:
            channel_id = self.get_channel_id(object_id)
            return channels.get(channel_id)
        return None

    def add_channel(self, instance: ABusFeature) -> None:
        """Add a new Haus-Bus Channel to this gateway's channel list."""

        object_id = ObjectId(instance.getObjectId())
        device = self.get_device(object_id)
        channel_list = self.get_channel_list(object_id)

        if device is not None and channel_list is not None and self.get_channel_id(object_id) not in channel_list:

            # LIGHT
            if isinstance(instance, Dimmer):
              new_channel = HausbusDimmerLight(object_id.getInstanceId(), device, instance)
              new_domain = LIGHT_DOMAIN
            elif isinstance(instance, Led):
              new_channel = HausbusLedLight(object_id.getInstanceId(), device, instance)
              new_domain = LIGHT_DOMAIN
            elif isinstance(instance, LogicalButton):
              new_channel = HausbusBackLight(object_id.getInstanceId(), device, instance)
              new_domain = LIGHT_DOMAIN
            elif isinstance(instance, RGBDimmer):
              new_channel = HausbusRGBDimmerLight(object_id.getInstanceId(), device, instance)
              new_domain = LIGHT_DOMAIN
            # SWITCH
            elif isinstance(instance, Schalter):
              new_channel = HausbusSwitch(object_id.getInstanceId(), device, instance)
              new_domain = SWITCH_DOMAIN
            # COVER
            elif isinstance(instance, Rollladen):
              new_channel = HausbusCover(object_id.getInstanceId(), device, instance)
              new_domain = COVER_DOMAIN
            # SENSOR
            elif isinstance(instance, Temperatursensor):
              new_channel = HausbusTemperaturSensor(object_id.getInstanceId(), device, instance)
              new_domain = SENSOR_DOMAIN
            elif isinstance(instance, Helligkeitssensor):
              new_channel = HausbusHelligkeitsSensor(object_id.getInstanceId(), device, instance)
              new_domain = SENSOR_DOMAIN
            elif isinstance(instance, Feuchtesensor):
              new_channel = HausbusFeuchteSensor(object_id.getInstanceId(), device, instance)
              new_domain = SENSOR_DOMAIN
            elif isinstance(instance, AnalogEingang):
              new_channel = HausbusAnalogEingang(object_id.getInstanceId(), device, instance)
              new_domain = SENSOR_DOMAIN
            elif isinstance(instance, PowerMeter):
              new_channel = HausbusPowerMeter(object_id.getInstanceId(), device, instance)
              new_domain = SENSOR_DOMAIN
            # BINARY_SENSOR only for digital inputs and not for pushbuttons
            elif isinstance(instance, Taster) and not instance.getName().startswith("Taster"):
              new_channel = HausbusBinarySensor(object_id.getInstanceId(), device, instance)
              new_domain = BINARY_SENSOR_DOMAIN
            else:
              return

            LOGGER.debug(f"create {new_domain} channel for {instance}")
            channel_list[self.get_channel_id(object_id)] = new_channel
            asyncio.run_coroutine_threadsafe(self._new_channel_listeners[new_domain](new_channel), self.hass.loop).result()
            new_channel.get_hardware_status()

            # additional EventEnties for all binary inputs and pushbuttons
            if isinstance(instance, Taster) and self.get_event_entity(instance.getObjectId()) is None:
              LOGGER.debug(f"create event channel for {instance}")
              new_channel = HausBusEvent(object_id.getInstanceId(), device, instance)
              self.events[self.get_channel_id(object_id)] = new_channel
              asyncio.run_coroutine_threadsafe(self._new_channel_listeners["EVENTS"](new_channel), self.hass.loop).result()

    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""

        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()
        deviceId = object_id.getDeviceId()
        templates = Templates.get_instance()

        # ignore messages sent from this module
        if deviceId == HOMESERVER_DEVICE_ID or deviceId == 9999 or deviceId == 12222:
            return

        if deviceId in [110, 503, 1000, 1541, 3422, 4000, 4001, 4002, 4003, 4004, 4005, 4009, 4096, 5068, 8192, 8270, 11581, 12223, 12622, 13976, 14896, 18343, 19075, 20043, 21336, 22909, 24261, 25661, 25874, 28900, 3423, 4006, 4008]:
            return

        LOGGER.debug(f"busDataReceived with data = {data}")

        controller = Controller(object_id.getValue())

        # ModuleId -> getConfiguration
        if isinstance(data, ModuleId):
          LOGGER.debug(f"got moduleId of {object_id.getDeviceId()} with data: {data}")
          self.add_device(str(object_id.getDeviceId()), data)
          controller.getConfiguration()
          return

        # Bei unbekanntem Gerät -> ModuleId abfragen
        device = self.get_device(object_id)
        if device is None:
          LOGGER.debug(f"got event of unknown device {object_id.getDeviceId()} with data: {data} -> calling getModuleId")
          controller.getModuleId(EIndex.RUNNING)
          return

        # Configuration -> getRemoteObjects
        if isinstance(data, Configuration):
          LOGGER.debug(f"got configuration of {object_id.getDeviceId()} with data: {data}")
          config = cast(Configuration, data)
          device = self.get_device(object_id)
          if device is not None:
            device.set_type(config.getFCKE())

            # Mit der Konfiguration registrieren wir das Device bei HASS
            asyncio.run_coroutine_threadsafe(self.async_create_device_registry(device), self.hass.loop).result()

            controller.getRemoteObjects()
            return

        # RemoteObjects -> Channel anlegen
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
              #LOGGER.debug(f"name for firmwareId {device.firmware_id}, fcke: {device.fcke}, classId {instanceObjectId.getClassId()}, instanceId {instanceObjectId.getInstanceId()} is {name}")

              if deviceId == 22784 or deviceId == 29725:
                name = f"Object {instance.getObjectId()}"

              if name is not None:
                instance.setName(name)
                self.add_channel(instance)

                # Bei allen Taster Instanzen die Events anlegen, weil da auch ein Taster angeschlossen sein kann
                if isinstance(instance, Taster):
                  inputs.append(name)

            if inputs:
              self.hass.data.setdefault(DOMAIN, {})
              self.hass.data[DOMAIN][device.hass_device_entry.id] = {"inputs": inputs}
              LOGGER.debug(f"{inputs} inputs angemeldet {device.hass_device_entry.id} deviceId {deviceId}")
              
            return

        # Device_trigger und Events melden
        if isinstance(data, (EvCovered, EvFree, EvHoldStart, EvHoldEnd, EvClicked, EvDoubleClick)):
          name = templates.get_feature_name_from_template(device.firmware_id, device.fcke, object_id.getClassId(), object_id.getInstanceId())
          self.generate_device_trigger(data, device.hass_device_entry.id, name)
          eventEntity = self.get_event_entity(object_id.getValue())
          LOGGER.debug(f"eventEntity is {eventEntity}")
          if eventEntity is not None:
            eventEntity.handle_push_button_event(data)

        # Alles andere wird an die jeweiligen Channel weitergeleitet
        channel = self.get_channel(object_id)

        # light event handling
        if isinstance(channel, HausbusEntity):
          LOGGER.debug(f" handle_event {channel} {data}")
          channel.handle_event(data)
        else:
          LOGGER.debug(f"kein zugehöriger channel")

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

    def register_platform_add_channel_callback(self,add_channel_callback: Callable[[HausbusEntity], Coroutine[Any, Any, None]],platform: str,) -> None:
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
      # device_registry.async_remove_device("fc90771cff9ddaaeb2568f20ec2f8711")

    # @callback
    # def _state_changed_listener(self, event):
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
        # for key in self._attributes.keys():
            # if old_attr.get(key) != new_attr.get(key):
              # LOGGER.debug(f" key {key} old_attr {old_attr.get(key)} new_attr {new_attr.get(key)}")

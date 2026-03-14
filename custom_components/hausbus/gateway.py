"""Representation of a Haus-Bus gateway."""

from __future__ import annotations
import logging
import asyncio
import time
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
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import device_registry as dr

from .device import HausbusDevice
from .entity import HausbusEntity
from .light import (Dimmer, HausbusDimmerLight, HausbusLedLight, HausbusBackLight, HausbusRGBDimmerLight, Led, LogicalButton, RGBDimmer)
from .switch import HausbusSwitch, Schalter
from .cover import HausbusCover, Rollladen
# from .number import HausBusNumber
from .sensor import HausbusTemperaturSensor, Temperatursensor, HausbusBrightnessSensor, Helligkeitssensor, HausbusHumiditySensor, Feuchtesensor, HausbusAnalogEingang, AnalogEingang
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
from pyhausbus.de.hausbus.homeassistant.proxy.rFIDReader.data.EvData import EvData as RfidEvData

from custom_components.hausbus.sensor import HausbusPowerMeter, \
  HausbusRfidSensor
from pyhausbus.de.hausbus.homeassistant.proxy import ProxyFactory, \
  temperatursensor
from custom_components.hausbus.number import HausbusControl
from pyhausbus.de.hausbus.homeassistant.proxy.RFIDReader import RFIDReader

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
        self.home_server.addBusDeviceListener(self)
        self._new_channel_listeners: dict[
            str, Callable[[HausbusEntity], Coroutine[Any, Any, None]]
        ] = {}
        # to prevent duplicate channels but to allow to add channels even if it was registered before
        self.registered_channels: set[int] = set()

        # Listener für state_changed registrieren
        # self.hass.bus.async_listen("state_changed", self._state_changed_listener)

        # asyncio.run_coroutine_threadsafe(self.async_delete_devices(), self.hass.loop)

    async def createDiscoveryButtonAndStartDiscovery(self):
      """Creates a Button to manually start device discovery and starts discovery"""

      async def discovery_callback():
        LOGGER.debug("Search devices")
        self.hass.async_add_executor_job(self.home_server.searchDevices)

      self.addStandaloneButton("hausbus_discovery_button", "Discover Haus-Bus Devices", discovery_callback)
      await discovery_callback()

    def addStandaloneButton(self, uniqueId: str, name:str, callback: Callable[[], Coroutine[Any, Any, None]]):
      asyncio.run_coroutine_threadsafe(self._new_channel_listeners[BUTTON_DOMAIN](HausbusButton(uniqueId, name, callback)), self.hass.loop)

    def add_device(self, device_id: str, module: ModuleId) -> None:
        """Add a new Haus-Bus Device to this gateway's device list."""
        if device_id not in self.devices:
            self.devices[device_id] = HausbusDevice(device_id, module.getFirmwareId().getTemplateId() + " " + str(module.getMajorRelease()) + "." + str(module.getMinorRelease()), module.getName(), module.getFirmwareId())

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

    def newDeviceDetected(
        self,
        device_id: int,
        model_type: str,
        module_id: ModuleId,
        configuration: Configuration,
        channels: list[ABusFeature],
    ):
        """Handle new discovered Haus-Bus device."""

        
        LOGGER.debug(
            "newDeviceDetected: device_id %s model_type %s module_id %s configuration %s channels %s",
            device_id,
            model_type,
            module_id,
            configuration,
            channels,
        )

        self.add_device(str(device_id), module_id)
        device = self.devices.get(str(device_id))
        device.set_config(configuration)
        
        if device.is_leistungs_regler():
            model_type = "SSR Leistungsregler"
        elif device.is_rollo_modul():
            nr_schalter = sum(1 for instance in channels if isinstance(instance, Schalter))
            if nr_schalter > 6:
                model_type="8-fach Rollos"
            else:
                model_type="2-fach Rollos"
                
        device.set_model_id(model_type)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            manufacturer="HausBus",
            model=model_type,
            name=f"{model_type} {device_id}",
            sw_version=module_id.getFirmwareId().getTemplateId()
            + " "
            + str(module_id.getMajorRelease())
            + " "
            + str(module_id.getMinorRelease()),
            hw_version=module_id.getName(),
        )

        asyncio.run_coroutine_threadsafe(
            self.async_register_device(device_id, device_info, device), self.hass.loop
        ).result()

        # Inputs merken für die Trigger
        inputs = []

        for channel in channels:
            object_id = channel.getObjectId()
            if object_id not in self.registered_channels:
                self.registered_channels.add(object_id)

                new_entity = None

                # Specials
                if device.is_leistungs_regler() and isinstance(channel, Schalter) and "Rote Modul LED" not in channel.getName():
                  new_entity = HausbusControl(channel, device)
                  new_domain = NUMBER_DOMAIN
                # LIGHT
                elif isinstance(channel, Dimmer):
                  new_entity = HausbusDimmerLight(channel, device)
                  new_domain = LIGHT_DOMAIN
                elif isinstance(channel, Led):
                  new_entity = HausbusLedLight(channel, device)
                  new_domain = LIGHT_DOMAIN
                elif isinstance(channel, LogicalButton):
                  new_entity = HausbusBackLight(channel, device)
                  new_domain = LIGHT_DOMAIN
                elif isinstance(channel, RGBDimmer):
                  new_entity = HausbusRGBDimmerLight(channel, device)
                  new_domain = LIGHT_DOMAIN
                # SWITCH
                elif isinstance(channel, Schalter):
                  new_entity = HausbusSwitch(channel, device)
                  new_domain = SWITCH_DOMAIN
                # COVER
                elif isinstance(channel, Rollladen):
                  new_entity = HausbusCover(channel, device)
                  new_domain = COVER_DOMAIN
                # SENSOR
                elif isinstance(channel, Temperatursensor):
                  new_entity = HausbusTemperaturSensor(channel, device)
                  new_domain = SENSOR_DOMAIN
                elif isinstance(channel, Helligkeitssensor):
                  new_entity = HausbusBrightnessSensor(channel, device)
                  new_domain = SENSOR_DOMAIN
                elif isinstance(channel, Feuchtesensor):
                  new_entity = HausbusHumiditySensor(channel, device)
                  new_domain = SENSOR_DOMAIN
                elif isinstance(channel, AnalogEingang):
                  new_entity = HausbusAnalogEingang(channel, device)
                  new_domain = SENSOR_DOMAIN
                elif isinstance(channel, PowerMeter):
                  new_entity = HausbusPowerMeter(channel, device)
                  new_domain = SENSOR_DOMAIN
                elif isinstance(channel, RFIDReader):
                  new_entity = HausbusRfidSensor(channel, device)
                  new_domain = SENSOR_DOMAIN
                elif isinstance(channel, Taster):
                  # if not instance.getName().startswith("Taster"):
                  new_entity = HausbusBinarySensor(channel, device)
                  new_domain = BINARY_SENSOR_DOMAIN
                else:
                  LOGGER.debug("no entity created for %s", channel)
                  
                if new_entity is not None:  
                    LOGGER.debug(f"new channel {new_entity.__class__.__name__} for {channel}") 
                    channel_list = self.get_channel_list(ObjectId(object_id))
                    channel_list[self.get_channel_id(ObjectId(object_id))] = new_entity
                    asyncio.run_coroutine_threadsafe(self._new_channel_listeners[new_domain](new_entity), self.hass.loop).result()
                    LOGGER.debug("registered. Reading status...") 
                    new_entity.get_hardware_status()
                    
                    # additional EventEnties for all binary inputs and pushbuttons
                    if isinstance(channel, Taster) and self.get_event_entity(channel.getObjectId()) is None:
                      LOGGER.debug(f"create event channel for {channel}")
                      new_channel = HausBusEvent(channel, device)
                      self.events[channel.getObjectId()] = new_channel
                      asyncio.run_coroutine_threadsafe(self._new_channel_listeners["EVENTS"](new_channel), self.hass.loop).result()
                    
                    # Bei allen Taster Instanzen die Events anlegen, weil da auch ein Taster angeschlossen sein kann
                    if isinstance(channel, Taster):
                      inputs.append(channel.getName())
            else:
              LOGGER.debug(f"already registered {channel}")      

        if inputs:
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN][device.hass_device_entry_id] = {"inputs": inputs}
            LOGGER.debug(f"{inputs} inputs angemeldet {device.hass_device_entry_id} deviceId {device_id}")


    def busDataReceived(self, busDataMessage: BusDataMessage) -> None:
        """Handle Haus-Bus messages."""

        object_id = ObjectId(busDataMessage.getSenderObjectId())
        data = busDataMessage.getData()
        device_id = object_id.getDeviceId()
        device = self.get_device(object_id)
        
        # ignore messages from own server
        if self.home_server.is_internal_device(device_id):
            return


        LOGGER.debug(f"busDataReceived with data = {data} from {object_id}")

        # Device_trigger und Events melden
        eventEntity = self.get_event_entity(object_id.getValue())
        if eventEntity is not None:
          LOGGER.debug(f"eventEntity is {eventEntity}")
          eventEntity.handle_event(data)
          self.generate_device_trigger(data, device, object_id)

        # Alles andere wird an die jeweiligen Channel weitergeleitet
        channel = self.get_channel(object_id)

        # all channel events
        if isinstance(channel, HausbusEntity):
          LOGGER.debug(f" handle_event {channel} {data}")
          channel.handle_event(data)

        if isinstance(channel, HausbusRfidSensor) and isinstance(data, RfidEvData):
          LOGGER.debug(f" rfid data {channel} {data}")
          self.hass.loop.call_soon_threadsafe(lambda: self.hass.bus.async_fire("hausbus_rfid_event", {"device_id": device.hass_device_entry_id, "tag": data.getTagID()}))

        else:
          LOGGER.debug(f"kein zugehöriger channel")


    def generate_device_trigger(self, data, device: HausbusDevice, object_id: ObjectId):

        eventType = {
              EvCovered: "button_pressed",
              EvFree: "button_released",
              EvHoldStart: "button_hold_start",
              EvHoldEnd: "button_hold_end",
              EvClicked: "button_clicked",
              EvDoubleClick: "button_double_clicked",
            }.get(type(data), "unknown")

        if eventType != "unknown":
          name = Templates.get_instance().get_feature_name_from_template(device.firmware_id, device.fcke, object_id.getClassId(), object_id.getInstanceId())
          if name is not None:
            LOGGER.debug(f"sending trigger {eventType} name {name} hass_device_id {device.hass_device_entry_id}")
            self.hass.loop.call_soon_threadsafe(lambda: self.hass.bus.async_fire("hausbus_button_event", {"device_id": device.hass_device_entry_id, "type": eventType, "subtype": name}))
          else:
            LOGGER.debug(f"unknown name for event {data}")

    def register_platform_add_channel_callback(self, add_channel_callback: Callable[[HausbusEntity], Coroutine[Any, Any, None]], platform: str,) -> None:
        """Register add channel callbacks."""
        self._new_channel_listeners[platform] = add_channel_callback

    def extract_final_number(self, text: str) -> int | None:
      match = re.search(r"(\d+)$", text.strip())
      if match:
        return int(match.group(1))
      return None

    async def removeDevice(self, device_id:str):
      LOGGER.debug(f"delete device {device_id}")
      for objectIdStr, hausBusDevice in self.devices.items():
        if hausBusDevice.device_id == device_id:
          LOGGER.debug(f"found delete device {hausBusDevice}")
          del self.devices[device_id]
          del self.channels[device_id]
          to_delete = [
            objectIdInt
            for objectIdInt, hausBusEntity in self.events.items()
              if str(ObjectId(objectIdInt).getDeviceId()) == device_id
          ]

          for key in to_delete:
            del self.events[key]
          return True

      return True

    def resetDevice(self, device_id:str):
      LOGGER.debug(f"reset device {device_id}")

      for objectIdStr, hausBusDevice in self.devices.items():
        if hausBusDevice.hass_device_entry_id == device_id:
          device_id_int = int(hausBusDevice.device_id)
          LOGGER.debug(f"resetting device {device_id_int}")
          Controller.create(device_id_int, 1).reset()
          return True
        else:
          LOGGER.debug(f"passt nicht {hausBusDevice.hass_device_entry_id}")
      return False

    async def async_register_device(self, device_id: int, device_info: DeviceInfo, hausBusDevice: HausbusDevice):
        """Creates a device in the hass registry."""

        LOGGER.debug(f"register_device: {device_info}")

        device_registry = dr.async_get(self.hass)

        device = device_registry.async_get_device(
            identifiers={(DOMAIN, str(device_id))},
            connections=None,
        )
        LOGGER.debug(f"read device from registry: {device}")
        
        device_entry = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, str(device_id))},
            manufacturer=device_info.get("manufacturer"),
            model=device_info.get("model"),
            name=device_info.get("name"),
        )

        LOGGER.debug(
            "register_device: hassEntryId = %s, device_id = %s, manufacturer = %s, model = %s, name = %s",
            device_entry.id,
            str(device_id),
            device_info.get("manufacturer"),
            device_info.get("model"),
            device_info.get("name"),
        )
        
        hausBusDevice.set_hass_device_entry_id(device_entry.id)

"""Support for Haus-Bus lights."""

from __future__ import annotations

from abc import abstractmethod
import colorsys
from typing import TYPE_CHECKING, Any

from pyhausbus.ABusFeature import ABusFeature
from pyhausbus.de.hausbus.homeassistant.proxy.Dimmer import Dimmer
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOff import (
    EvOff as DimmerEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.EvOn import EvOn as DimmerEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.dimmer.data.Status import (
    Status as DimmerStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Led import Led
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.EvOff import EvOff as ledEvOff
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.EvOn import EvOn as ledEvOn
from pyhausbus.de.hausbus.homeassistant.proxy.led.data.Status import Status as ledStatus
from pyhausbus.de.hausbus.homeassistant.proxy.RGBDimmer import RGBDimmer
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.EvOff import (
    EvOff as rgbDimmerEvOff,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.EvOn import (
    EvOn as rgbDimmerEvOn,
)
from pyhausbus.de.hausbus.homeassistant.proxy.rGBDimmer.data.Status import (
    Status as rgbDimmerStatus,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_ON_STATE
from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Haus-Bus lights from a config entry."""
    gateway = config_entry.runtime_data.gateway

    async def async_add_light(channel: HausbusEntity) -> None:
        """Add light from Haus-Bus."""
        if isinstance(channel, HausbusLight):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_light, LIGHT_DOMAIN)


class HausbusLight(HausbusEntity, LightEntity):
    """Representation of a Haus-Bus light."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: ABusFeature,
    ) -> None:
        """Set up light."""
        super().__init__(channel.__class__.__name__, instance_id, device, channel.getName())

        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_hs_color = (0, 0)

    @staticmethod
    def is_light_channel(class_id: int) -> bool:
        """Check if a class_id is a light."""
        return class_id in (Dimmer.CLASS_ID, RGBDimmer.CLASS_ID, Led.CLASS_ID)

    @abstractmethod
    def get_hardware_status(self) -> None:
        """Request status of a light channel from hardware."""

    def set_light_color(self, red: int, green: int, blue: int) -> None:
        """Set the color of a light channel."""
        hue, saturation, value = colorsys.rgb_to_hsv(
            red / 100.0,
            green / 100.0,
            blue / 100.0,
        )
        params = {
            ATTR_ON_STATE: True,
            ATTR_BRIGHTNESS_PCT: value,
            ATTR_HS_COLOR: (round(hue * 360), round(saturation * 100)),
        }
        self.async_update_callback(**params)

    def set_light_brightness(self, brightness: int) -> None:
        """Set the brightness of a light channel."""
        params = {ATTR_ON_STATE: True, ATTR_BRIGHTNESS_PCT: brightness / 100}
        self.async_update_callback(**params)

    def light_turn_off(self) -> None:
        """Turn off a light channel."""
        params = {ATTR_ON_STATE: False}
        self.async_update_callback(**params)

    def handle_light_event(self, data: Any) -> None:
        """Handle light events from Haus-Bus."""
        # light off events
        if isinstance(data, (DimmerEvOff, ledEvOff, rgbDimmerEvOff)):
            self.light_turn_off()

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """Light state push update."""
        state_changed = False
        if ATTR_ON_STATE in kwargs and self._attr_is_on != kwargs[ATTR_ON_STATE]:
            self._attr_is_on = kwargs[ATTR_ON_STATE]
            state_changed = True

        if (
            ATTR_BRIGHTNESS_PCT in kwargs
            and self._attr_brightness != kwargs[ATTR_BRIGHTNESS_PCT] * 255
        ):
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS_PCT] * 255
            state_changed = True

        if ATTR_HS_COLOR in kwargs and self._attr_hs_color != kwargs[ATTR_HS_COLOR]:
            self._attr_hs_color = kwargs[ATTR_HS_COLOR]
            state_changed = True

        if state_changed:
            self.schedule_update_ha_state()


class HausbusDimmerLight(HausbusLight):
    """Representation of a Haus-Bus dimmer."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: Dimmer,
    ) -> None:
        """Set up light."""
        super().__init__(instance_id, device, channel)

        self._channel = channel
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    def get_hardware_status(self) -> None:
        """Request status of a light channel from hardware."""
        self._channel.getStatus()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.setBrightness(0, 0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)
        brightness = round(brightness * 100 // 255)
        self._channel.setBrightness(brightness, 0)

    def handle_light_event(self, data: Any) -> None:
        """Handle dimmer events from HausBus."""
        super().handle_light_event(data)
        # dimmer event handling
        if isinstance(data, DimmerEvOn):
            self.set_light_brightness(data.getBrightness())
        if isinstance(data, DimmerStatus):
            if data.getBrightness() > 0:
                self.set_light_brightness(data.getBrightness())
            else:
                self.light_turn_off()


class HausbusRGBDimmerLight(HausbusLight):
    """Representation of a Haus-Bus RGB dimmer."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: RGBDimmer,
    ) -> None:
        """Set up light."""
        super().__init__(instance_id, device, channel)

        self._channel = channel
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.HS}
        self._attr_color_mode = ColorMode.HS

    def get_hardware_status(self) -> None:
        """Request status of a light channel from hardware."""
        self._channel.getStatus()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.setColor(0, 0, 0, 0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)
        h_s = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)

        rgb = colorsys.hsv_to_rgb(h_s[0] / 360, h_s[1] / 100, brightness / 255)
        red, green, blue = tuple(round(x * 100) for x in rgb)
        self._channel.setColor(red, green, blue, 0)

    def handle_light_event(self, data: Any) -> None:
        """Handle RGB dimmer events from HausBus."""
        super().handle_light_event(data)
        # rgb dimmmer event handling
        if isinstance(data, rgbDimmerEvOn):
            self.set_light_color(
                data.getBrightnessRed(),
                data.getBrightnessGreen(),
                data.getBrightnessBlue(),
            )
        if isinstance(data, rgbDimmerStatus):
            if (
                data.getBrightnessBlue() > 0
                or data.getBrightnessGreen() > 0
                or data.getBrightnessRed() > 0
            ):
                self.set_light_color(
                    data.getBrightnessRed(),
                    data.getBrightnessGreen(),
                    data.getBrightnessBlue(),
                )
            else:
                self.light_turn_off()


class HausbusLedLight(HausbusLight):
    """Representation of a Haus-Bus LED."""

    def __init__(
        self,
        instance_id: int,
        device: HausbusDevice,
        channel: Led,
    ) -> None:
        """Set up light."""
        super().__init__(instance_id, device, channel)

        self._channel = channel
        self._attr_supported_color_modes: set[ColorMode] = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    def get_hardware_status(self) -> None:
        """Request status of a light channel from hardware."""
        self._channel.getStatus()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off action."""
        self._channel.off(0)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on action."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)
        brightness = round(brightness * 100 // 255)
        self._channel.on(brightness, 0, 0)

    def handle_light_event(self, data: Any) -> None:
        """Handle led events from HausBus."""
        super().handle_light_event(data)
        # led event handling
        if isinstance(data, ledEvOn):
            self.set_light_brightness(data.getBrightness())
        if isinstance(data, ledStatus):
            if data.getBrightness() > 0:
                self.set_light_brightness(data.getBrightness())
            else:
                self.light_turn_off()

"""Handle BeSMART Devices."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .models import WifiBox, Devices

class BesmartInterfaceDevice:
    """Class for BeSMART WiFi Box handling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, wifi_box: WifiBox, devices: Devices) -> None:
        """Initialize interface device class."""
        device_registry = dr.async_get(hass)

        device_id = (DOMAIN, entry.entry_id)
        self.wifi_box = wifi_box
        self.boiler = devices["boiler"]
        self.thermostats = devices["thermostats"]
        self.device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={device_id},
            manufacturer="Riello S.p.a.",
            name=entry.options[CONF_NAME],
            model="BeSMART",
            model_id=wifi_box,
        )
        self.device_info = DeviceInfo(identifiers={device_id})

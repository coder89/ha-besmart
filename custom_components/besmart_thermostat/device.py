"""Handle BeSMART Devices."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


class BesmartInterfaceDevice:
    """Class for BeSMART Device handling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize interface device class."""
        device_registry = dr.async_get(hass)

        device_id = (DOMAIN, entry.entry_id)
        self.device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={device_id},
            manufacturer="Signify",
            name=entry.options[CONF_NAME],
            model="config.modelname",
            model_id="config.modelid",
            sw_version="config.swversion",
            hw_version="config.hwversion",
        )
        self.device_info = DeviceInfo(identifiers={device_id})

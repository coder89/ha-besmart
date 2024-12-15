"""The besmart_thermostat integration."""

from __future__ import annotations

import logging
from http import HTTPStatus
from requests import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    Platform,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry

from .const import PLATFORMS
from .device import BesmartInterfaceDevice
from .api import BesmartClient

type BesmartConfigEntry = ConfigEntry[BesmartClient]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesmartConfigEntry,
) -> bool:
    """Set up besmart_thermostat from a config entry."""

    # 1. Create API instance
    besmart_config = entry.options
    client = BesmartClient(hass, besmart_config[CONF_USERNAME], besmart_config[CONF_PASSWORD])

    # 2. Validate the API connection (and authentication)
    try:
        wifi_boxes = await client.login()
    except HTTPError as ex:
        if ex.response.status_code == HTTPStatus.UNAUTHORIZED:
            raise ConfigEntryAuthFailed("Invalid credentials.") from ex
        raise ConfigEntryNotReady from ex
    except Exception as ex:
        raise ConfigEntryNotReady from ex

    # 3. Store an API object for your platforms to access
    entry.runtime_data = client

    # 4. Register BeSMART Controller devices for all wifi boxes
    interface_devices = []
    for wifi_box in wifi_boxes:
        devices = await client.devices(wifi_box)
        interface_devices.append(BesmartInterfaceDevice(hass, entry, wifi_box, devices))
    entry.interface_devices = interface_devices

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_config_entry_update_listener))

    return True


async def async_config_entry_update_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BesmartConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
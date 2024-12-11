"""The besmart_thermostat integration."""

from __future__ import annotations

from http import HTTPStatus
from requests import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device import (
    async_remove_stale_devices_links_keep_entity_device,
)

from .const import PLATFORMS
from .utils import BesmartClient

type BesmartConfigEntry = ConfigEntry[BesmartClient]


async def async_setup_entry(hass: HomeAssistant, entry: BesmartConfigEntry) -> bool:
    """Set up besmart_thermostat from a config entry."""

    # 1. Create API instance
    besmart_config = entry.data
    client = BesmartClient(besmart_config[CONF_USERNAME], besmart_config[CONF_PASSWORD])

    # 2. Validate the API connection (and authentication)
    try:
        await client.login()
    except HTTPError as ex:
        if ex.code == HTTPStatus.UNAUTHORIZED
            raise ConfigEntryAuthFailed("Invalid credentials.") from ex
        raise ConfigEntryNotReady from ex
    except Exception as ex:
        raise ConfigEntryNotReady from ex

    # 3. Store an API object for your platforms to access
    entry.runtime_data = client

    # async_remove_stale_devices_links_keep_entity_device(
    #     hass,
    #     entry.entry_id,
    #     entry.options[CONF_HEATER],
    # )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))

    return True


async def async_config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BesmartConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
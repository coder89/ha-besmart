# -*- coding: utf-8 -*-
"""
Support for Riello's Besmart water heater controller.
Be aware the thermostat may require more then 3 minute to refresh its states.

The thermostats support the season switch however this control will be managed with a 
different control.

version: 2
tested with home-assistant >= 0.96

"""
import logging
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.components.water_heater.const import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["schedule"]
REQUIREMENTS = ["asyncio"]

DEFAULT_NAME = "BeSMART Water Heater"
DEFAULT_TIMEOUT = 3
ENTITY_ID_FORMAT = PLATFORM_DOMAIN + ".{}"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    new_entities = []
    
    for device in config_entry.interface_devices:
        wifi_box = device.wifi_box
        new_entities.append(WaterHeater(hass, config_entry, wifi_box, device))

    if new_entities:
        async_add_entities(new_entities, update_before_add=True)


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""


# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
class WaterHeater(WaterHeaterEntity):
    """Representation of a Besmart water heater."""

    _attr_has_entity_name = True
    _attr_should_poll = True
    _default_name = "Water Heater"
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_unique_id: str

    # BeSmart work_mode
    STATE_GAS = "gas" # Normal or DHW operation
    STATE_OFF = "off" # Anti-frost operation

    DHW_TEMP_MAX = 60.0
    DHW_TEMP_MIN = 30.0
    DHW_TEMP_STEP = 1.0
    DHW_TEMP_PRECISION = 1.0

    def __init__(self, hass, config_entry, wifi_box, interface_device):
        """Initialize the thermostat."""
        self._entry_name = config_entry.options[CONF_NAME]
        self._entry_id = config_entry.entry_id
        self._wifi_box = wifi_box
        self._cl = config_entry.runtime_data
        self._current_temp = interface_device.boiler["dhw_current_temp"]
        self._current_mode = interface_device.boiler["mode"]
        self._previous_climate_active = None
        if len(interface_device.thermostats) > 0:
            self._current_unit = interface_device.thermostats[0]["unit"]
        else:
            self._current_unit = "0"
        self._tempSet = 0.0

        # link to BeSMART device
        self._attr_device_info = interface_device.device_info

        # unique_id = <deviceID>:<roomID>
        self._attr_unique_id = f"{self._entry_id}:{self._wifi_box}:water_heater"

        # name = <integrationName> Water Heater [<roomName>]
        self._attr_name = f"Water Heater"

        # entity_id = water_heater.<name>
        self._entity_id = async_generate_entity_id(self._entity_id_format, self._attr_name or self._default_name, None, hass)

        # Disable backwards compatibility for new turn_on/off methods
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def max_temp(self):
        """The maximum temperature."""
        return self.DHW_TEMP_MAX

    @property
    def min_temp(self):
        """The minimum temperature."""
        return self.DHW_TEMP_MIN

    @property
    def precision(self):
        """The temperature precision (defaults to 0.1deg C)."""
        return self.DHW_TEMP_PRECISION

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._tempSet

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.DHW_TEMP_STEP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._current_unit == "0":
            return UnitOfTemperature.CELSIUS
        else:
            return UnitOfTemperature.FAHRENHEIT

    @property
    def current_operation(self):
        """Return the current work mode."""
        if self._current_mode == "2":
            return self.STATE_OFF
        else:
            return self.STATE_GAS

    @property
    def operation_list(self):
        """Return available work modes."""
        return [self.STATE_GAS, self.STATE_OFF]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE |
            WaterHeaterEntityFeature.OPERATION_MODE
        )

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            # ATTR_MODE: self._current_state,
            # "battery_state": self._battery,
            # "frost_t": self._frostT,
            # "confort_t": self._comfT,
            # "save_t": self._saveT,
            # "season_mode": self.hvac_mode,
            # "heating_state": self._heating_state,
            "flame_status": self._flame_status,
            "outdoor_temperature": self._outdoor_temperature,
            "system_pressure": self._system_pressure,
        }

    async def async_update(self):
        """Update the data from the thermostat."""
        _LOGGER.debug("Update called")

        # Get thermostat data
        boiler = await self._cl.boiler(self._wifi_box)

        # Current operation mode
        try:
            self._current_mode = boiler.get("work_mode")
        except ValueError:
            self._current_mode = "2"

        # Extract programmed temperature
        try:
            self._tempSet = float(boiler.get("dhw_target_temp"))
        except ValueError:
            self._tempSet = 0.0

        # Extract current temperature
        try:
            self._current_temp = float(boiler.get("dhw_current_temp"))
        except ValueError:
            self._current_temp = 0.0

        # Extract flame status
        try:
            self._flame_status = float(boiler.get("flame_status"))
        except ValueError:
            self._flame_status = 0

        # Extract outdoor temperature
        try:
            self._outdoor_temperature = float(boiler.get("outdoor_probe_temp"))
        except ValueError:
            self._system_pressure = 0.0

        # Extract system pressure
        try:
            self._system_pressure = float(boiler.get("system_pressure"))
        except ValueError:
            self._system_pressure = 0.0

        # Misc
        self._current_unit = boiler.get("unit")

    async def async_turn_on(self):
        """Turn off the heater"""
        await self.async_set_operation_mode(self.STATE_GAS)

    async def async_turn_off(self):
        """Turn on the heater"""
        await self.async_set_operation_mode(self.STATE_OFF)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if not temperature:
            return

        await self._cl.setBoilerTemp(self._wifi_box, temperature)

    async def async_set_operation_mode(self, mode):
        """Set HVAC mode (comfort, home, sleep, Party, Off)."""
        if mode == self.STATE_OFF:
            devices = await self._cl.devices(self._wifi_box)
            self._previous_climate_active = any(x["mode"] != "5" and x["mode"] != "4" for x in devices["thermostats"])
            await self._cl.setBoilerMode(self._wifi_box, "2")
        elif self._previous_climate_active:
            await self._cl.setBoilerMode(self._wifi_box, "0")
        else:
            await self._cl.setBoilerMode(self._wifi_box, "1")
        _LOGGER.debug("Set operation mode=%s(%s)", str(mode))

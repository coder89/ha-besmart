# -*- coding: utf-8 -*-
"""
Support for Riello's Besmart thermostats.
Be aware the thermostat may require more then 3 minute to refresh its states.

The thermostats support the season switch however this control will be managed with a 
different control.

version: 2
tested with home-assistant >= 0.96

"""
import logging
from datetime import datetime

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_HIGH,
    DOMAIN as PLATFORM_DOMAIN,
    HVACAction,
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ID,
    CONF_UNIQUE_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_MODE,
    UnitOfTemperature,
)
from homeassistant.components.schedule import Schedule
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN
from .utils import BesmartClient

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["switch", "sensor"]
REQUIREMENTS = ["requests"]

DEFAULT_NAME = "BeSMART Thermostat"
DEFAULT_TIMEOUT = 3
ENTITY_ID_FORMAT = PLATFORM_DOMAIN + ".{}"

ATTR_MODE = "mode"
STATE_UNKNOWN = "unknown"

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE |
    ClimateEntityFeature.PRESET_MODE |
    ClimateEntityFeature.TURN_ON |
    ClimateEntityFeature.TURN_OFF
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = config_entry.runtime_data

    rooms = await hass.async_add_executor_job(client.rooms)

    new_entities = []
    new_schedules = []
    for roomKey in rooms:
        # Thermostat device
        # roomData = rooms[roomKey]
        # room_id = roomData.get("therId")
        # room_name = roomData.get("name")
        # new_entities.append(Thermostat(hass, config_entry, room_id, room_name))
        # Thermostat schedule
        schedule_conf = ({
            CONF_ID: "some_schedule_id",
            CONF_NAME: "some schedule name"
        })
        new_schedules.append(ThermostatSchedule(schedule_conf, True))

    # for new_entity in new_entities:
    #     await hass.async_add_executor_job(new_entity.update)

    # if new_entities:
    #     async_add_entities(new_entities) #, update_before_add=True)
    if new_schedules:
        async_add_entities(new_schedules) #, update_before_add=True)


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
    _LOGGER.warn("SCHEDULE REMOVING ENTRY")

class ThermostatSchedule(Schedule):
    def __init__(self, config: ConfigType, editable: bool) -> None:
        """Initialize BeSMART Thermostat schedule."""
        super().__init__(config, editable)
        self._attr_name = "test besmart schedule"

#class Boiler(WaterHeater):
#    def __init__():

    

    # min_temp	float	110°F	The minimum temperature that can be set.
    # max_temp	float	140°F	The maximum temperature that can be set.
    # current_temperature	float	None	The current temperature.
    # target_temperature	float	None	The temperature we are trying to reach.
    # target_temperature_high	float	None	Upper bound of the temperature we are trying to reach.
    # target_temperature_low	float	None	Lower bound of the temperature we are trying to reach.
    # temperature_unit	str	NotImplementedError	One of TEMP_CELSIUS, TEMP_FAHRENHEIT, or TEMP_KELVIN.
    # current_operation	string	None	The current operation mode.
    # operation_list	List[str]	None	List of possible operation modes.
    # supported_features	List[str]	NotImplementedError	List of supported features.
    # is_away_mode_on	bool	None	The current status of away mode.

    # @property
    # def should_poll(self):
    #     """Polling needed for thermostat."""
    #     _LOGGER.debug("Should_Poll called")
    #     return True
    
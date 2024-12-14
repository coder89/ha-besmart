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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN
from .utils import BesmartClient

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["schedule"]
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
    for roomKey in rooms:
        roomData = rooms[roomKey]
        room_id = roomData.get("therId")
        room_name = roomData.get("name")
        new_entities.append(Thermostat(hass, config_entry, room_id, room_name))

    for new_entity in new_entities:
        await hass.async_add_executor_job(new_entity.update)

    if new_entities:
        async_add_entities(new_entities) #, update_before_add=True)


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
    _LOGGER.warn("REMOVING ENTRY")


# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
class Thermostat(ClimateEntity):
    """Representation of a Besmart thermostat."""

    _attr_has_entity_name = True
    _attr_should_poll = True
    _default_name = "Thermostat"
    _entity_id_format = ENTITY_ID_FORMAT
    _attr_unique_id: str

    # BeSmart thModel = 5
    # BeSmart WorkMode
    AUTO = 0  # 'Auto'
    MANUAL = 1  # 'Manuale - Confort'
    ECONOMY = 2  # 'Holiday - Economy'
    PARTY = 3  # 'Party - Confort'
    IDLE = 4  # 'Spento - Antigelo'
    DHW = 5 # 'Sanitario - Domestic hot water only'

    CLIMATE_TEMP_MAX = 35.0
    CLIMATE_TEMP_STEP = 0.2
    CLIMATE_TEMP_PRECISION = 0.1

    PRESET_HA_TO_BESMART = {
        "AUTO": AUTO,
        "MANUAL": MANUAL,
        "ECO": ECONOMY,
        "PARTY": PARTY,
        "IDLE": IDLE,
        "DHW": DHW,
    }

    PRESET_BESMART_TO_HA = {
        AUTO: "AUTO",
        MANUAL: "MANUAL",
        ECONOMY: "ECO",
        PARTY: "PARTY",
        IDLE: "IDLE",
        DHW: "DHW",
    }
    PRESET_MODE_LIST = list(PRESET_HA_TO_BESMART)

    HVAC_MODE_LIST = (HVACMode.COOL, HVACMode.HEAT)
    HVAC_MODE_BESMART_TO_HA = {"1": HVACMode.HEAT, "0": HVACMode.COOL}

    # BeSmart Season
    HVAC_MODE_HA_BESMART = {HVACMode.HEAT: "1", HVACMode.COOL: "0"}

    def __init__(self, hass, config_entry, room_id, room_name):
        """Initialize the thermostat."""
        self._entry_name = config_entry.options[CONF_NAME]
        self._supported_modes = config_entry.options[CONF_MODE]
        _LOGGER.warn("self._supported_modes")
        _LOGGER.warn(self._supported_modes)
        self._entry_id = config_entry.entry_id
        self._room_id = room_id
        self._room_name = room_name
        self._cl = config_entry.runtime_data
        self._current_temp = 0
        self._current_state = self.IDLE
        self._current_operation = ""
        self._current_unit = 0
        self._tempSet = 0
        self._tempSetMark = 0
        self._heating_state = False
        self._battery = "0"
        self._frostT = 0
        self._saveT = 0
        self._comfT = 0
        self._season = "1"

        # link to BeSMART device
        self._attr_device_info = config_entry.interface_device.device_info

        # DeviceInfo(
        #     identifiers={
        #         (DOMAIN, self._attr_unique_id)
        #     },
        #     name=self._entry_name,
        #     manufacturer="Riello S.p.A.",
        #     model="BeSMART Thermostat",
        #     model_id="BeSMART Thermostat",
        #     serial_number=self._room_id,
        #     suggested_area=self._room_name,
        #     sw_version="1.0",
        #     via_device=(DOMAIN, self.api.bridgeid),
        # )

        # unique_id = <deviceID>:<roomID>
        self._attr_unique_id = f"{self._entry_id}:{self._room_id}"

        # name = <integrationName> Thermostat [<roomName>]
        self._attr_name = f"{self._room_name} Thermostat"

        # entity_id = climate.<name>
        self._entity_id = async_generate_entity_id(self._entity_id_format, self._attr_name or self._default_name, None, hass)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def hvac_action(self):
        """Current mode."""
        if self._heating_state:
            mode = self.hvac_mode
            if mode == HVACMode.HEAT:
                return HVACAction.HEATING
            else:
                return HVACAction.COOLING
        else:
            return HVACAction.IDLE
        # TODO: Return OFF if device is offline

    @property
    def hvac_mode(self):
        """Current mode."""
        return self.HVAC_MODE_BESMART_TO_HA.get(self._season)

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._supported_modes

    @property
    def max_temp(self):
        """The maximum temperature."""
        return self.CLIMATE_TEMP_MAX

    @property
    def min_temp(self):
        """The minimum temperature."""
        return self._saveT

    @property
    def precision(self):
        """The temperature precision (defaults to 0.1deg C)."""
        return self.CLIMATE_TEMP_PRECISION

    @property
    def preset_mode(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""
        return self.PRESET_BESMART_TO_HA.get(self._current_state, "IDLE")

    @property
    def preset_modes(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""
        return self.PRESET_MODE_LIST

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._tempSet

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.CLIMATE_TEMP_STEP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._current_unit == "0":
            return UnitOfTemperature.CELSIUS
        else:
            return UnitOfTemperature.FAHRENHEIT

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def update(self):
        """Update the data from the thermostat."""
        _LOGGER.debug("Update called")
        room = self._cl.roomByName(self._room_name)
        _LOGGER.debug(room)
        if not room or not room.get("error") == 0:
            return

        try:
            self._tempSet = float(room.get("tempSet"))
        except ValueError:
            self._tempSet = 0.0

        data = self._cl.roomdata(room)
        _LOGGER.debug(data)
        if not data or not data.get("error") == 0:
            return

        try:
            # from Sunday (0) to Saturday (6)
            today = datetime.today().isoweekday() % 7
            # 48 slot per day
            index = datetime.today().hour * 2 + (
                    1 if datetime.today().minute > 30 else 0
            )
            programWeek = data["programWeek"]
            # delete programWeek to have less noise on debug output
            del data["programWeek"]
            self._tempSetMark = programWeek[today][index]
        except Exception as ex:
            _LOGGER.warning(ex)
            self._tempSetMark = "2"
        try:
            self._battery =not bool(int(data.get("bat"))) #corrected to raise battery alert in ha 1=problem status false
        except ValueError:
            self._battery = "0"
        try:
            self._frostT = float(data.get("frostT"))
        except ValueError:
            self._frostT = 0.0
        try:
            self._saveT = float(data.get("saveT"))
        except ValueError:
            self._saveT = 0.0
        try:
            self._comfT = float(data.get("comfT"))
        except ValueError:
            self._comfT = 0.0
        try:
            self._current_temp = float(data.get("tempNow"))
        except ValueError:
            self._current_temp = 0.0
        self._heating_state = data.get("heating", "") == "1"
        try:
            self._current_state = int(data.get("mode"))
        except ValueError:
            self._current_temp = 0
        self._current_unit = data.get("tempUnit")
        self._season = data.get("season")

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (COOL, HEAT) if supported."""
        mode = self.HVAC_MODE_HA_BESMART.get(hvac_mode)
        if mode in self._supported_modes:
            self._cl.setSettings(self._room_name, mode)
            _LOGGER.debug("Set hvac_mode hvac_mode=%s(%s)", str(hvac_mode), str(mode))

    def set_preset_mode(self, preset_mode):
        """Set HVAC mode (comfort, home, sleep, Party, Off)."""
        mode = self.PRESET_HA_TO_BESMART.get(preset_mode, self.AUTO)
        self._cl.setRoomMode(self._room_name, mode)
        _LOGGER.debug("Set operation mode=%s(%s)", str(preset_mode), str(mode))

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        # if temperature:
            # self._cl.setRoomConfortTemp(self._room_name, temperature)
            # self._cl.setRoomFrostTemp(self._room_name, temperature)
        # if target_temp_high:
            # self._cl.setRoomConfortTemp(self._room_name, target_temp_high)
        # if target_temp_low:
            # self._cl.setRoomECOTemp(self._room_name, target_temp_low)


    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_MODE: self._current_state,
            # "battery_state": self._battery,
            # "frost_t": self._frostT,
            # "confort_t": self._comfT,
            # "save_t": self._saveT,
            # "season_mode": self.hvac_mode,
            # "heating_state": self._heating_state,
        }

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
    
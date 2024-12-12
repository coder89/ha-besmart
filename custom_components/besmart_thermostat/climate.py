# -*- coding: utf-8 -*-
"""
Support for Riello's Besmart thermostats.
Be aware the thermostat may require more then 3 minute to refresh its states.

The thermostats support the season switch however this control will be managed with a 
different control.

version: 2
tested with home-assistant >= 0.96

Configuration example:

climate:
  - platform: Besmart
    name: Besmart Thermostat
    username: USERNAME
    password: 10080
    room: Soggiorno
    scan_interval: 10

logging options:

logger:
  default: info
  logs:
    custom_components.climate.besmart_thermostat: debug
"""
import logging
from datetime import datetime

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_LOW,
    PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DEFAULT_NAME,
)
from .utils import (
    BesmartClient,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["switch", "sensor"]
REQUIREMENTS = ["requests"]

DEFAULT_TIMEOUT = 3

ATTR_MODE = "mode"
STATE_UNKNOWN = "unknown"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

SUPPORT_FLAGS = (
    SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE_RANGE | SUPPORT_TARGET_TEMPERATURE
)

def create_device(room, client) -> Thermostat:
    entry_name = config.get(CONF_NAME)
    room_name = room.get("name")
    device_name = "{} {}".format(entry_name, room_name)
    return Thermostat(device_name, room_name, client)

async def _async_setup_devices(client: BesmartClient) -> None:
    rooms = await hass.async_add_executor_job(client.rooms)
    devices = map(create_device, rooms)
    add_devices(devices)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    client = config_entry.runtime_data
    await _async_setup_devices(client)


# pylint: disable=unused-argument
async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Setup the Besmart thermostats."""
    client = BesmartClient(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
    await _async_setup_devices(client)


# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
class Thermostat(ClimateEntity):
    """Representation of a Besmart thermostat."""

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

    HVAC_MODE_LIST = (HVAC_MODE_COOL, HVAC_MODE_HEAT)
    HVAC_MODE_BESMART_TO_HA = {"1": HVAC_MODE_HEAT, "0": HVAC_MODE_COOL}

    # BeSmart Season
    HVAC_MODE_HA_BESMART = {HVAC_MODE_HEAT: "1", HVAC_MODE_COOL: "0"}

    def __init__(self, name, room, client):
        """Initialize the thermostat."""
        self._name = name
        self._room_name = room
        self._cl = client
        self._current_temp = 0
        self._current_state = self.IDLE
        self._current_operation = ""
        self._current_unit = 0
        self._tempSetMark = 0
        self._heating_state = False
        self._battery = "0"
        self._frostT = 0
        self._saveT = 0
        self._comfT = 0
        self._season = "1"
        self.update()

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def hvac_action(self):
        """Current mode."""
        if self._heating_state:
            mode = self.hvac_mode
            if mode == HVAC_MODE_HEAT:
                return CURRENT_HVAC_HEAT
            else:
                return CURRENT_HVAC_COOL
        else:
            return CURRENT_HVAC_OFF

    @property
    def hvac_mode(self):
        """Current mode."""
        return self.HVAC_MODE_BESMART_TO_HA.get(self._season)

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (COOL, HEAT)."""
        mode = self.HVAC_MODE_HA_BESMART.get(hvac_mode)
        # self._cl.setSettings(self._room_name, mode)
        _LOGGER.debug("Set hvac_mode hvac_mode=%s(%s)", str(hvac_mode), str(mode))

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self.HVAC_MODE_LIST

    @property
    def max_temp(self):
        """TODO The maximum temperature."""
        return 69.0

    @property
    def min_temp(self):
        """TODO The minimum temperature."""
        return 5.1

    @property
    def precision(self):
        """TODO The temperature precision (defaults to 0.1deg C)."""
        return 0.1

    @property
    def preset_mode(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""
        return self.PRESET_BESMART_TO_HA.get(self._current_state, "IDLE")

    @property
    def preset_modes(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""
        return self.PRESET_MODE_LIST

    def set_preset_mode(self, preset_mode):
        """Set HVAC mode (comfort, home, sleep, Party, Off)."""
        mode = self.PRESET_HA_TO_BESMART.get(preset_mode, self.AUTO)
        # self._cl.setRoomMode(self._room_name, mode)
        _LOGGER.debug("Set operation mode=%s(%s)", str(preset_mode), str(mode))

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._comfT

    @property
    def target_temperature_high(self):
        return self.CLIMATE_TEMP_MAX

    @property
    def target_temperature_low(self):
        return self._saveT

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.CLIMATE_TEMP_STEP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._current_unit == "0":
            return TEMP_CELSIUS
        else:
            return TEMP_FAHRENHEIT

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)

        _LOGGER.warn(
            "temperature Frost: {} Eco: {} Conf: {}".format(
                temperature, target_temp_low, target_temp_high
            )
        )
        _LOGGER.warn(dir(kwargs))

        # if temperature:
            # self._cl.setRoomConfortTemp(self._room_name, temperature)
            # self._cl.setRoomFrostTemp(self._room_name, temperature)
        # if target_temp_high:
            # self._cl.setRoomConfortTemp(self._room_name, target_temp_high)
        # if target_temp_low:
            # self._cl.setRoomECOTemp(self._room_name, target_temp_low)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Polling needed for thermostat."""
        _LOGGER.debug("Should_Poll called")
        return True

    def update(self):
        """Update the data from the thermostat."""
        _LOGGER.debug("Update called")
        data = self._cl.roomByName(self._room_name)
        _LOGGER.debug(data)
        if data and data.get("error") == 0:
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
                self._frostT = 5.0
            try:
                self._saveT = float(data.get("saveT"))
            except ValueError:
                self._saveT = 16.0

            try:
                self._comfT = float(data.get("comfT"))
            except ValueError:
                self._comfT = 20.0
            try:
                self._current_temp = float(data.get("tempNow"))
            except ValueError:
                self._current_temp = 20.0

            self._heating_state = data.get("heating", "") == "1"
            try:
                self._current_state = int(data.get("mode"))
            except ValueError:
                self._current_temp = 0
            self._current_unit = data.get("tempUnit")
            self._season = data.get("season")

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

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

    @property
    def should_poll(self):
        """Polling needed for thermostat."""
        _LOGGER.debug("Should_Poll called")
        return True
    
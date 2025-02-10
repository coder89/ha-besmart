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

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    DOMAIN as PLATFORM_DOMAIN,
    HVACAction,
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_MODE,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["schedule"]
REQUIREMENTS = ["requests", "asyncio"]

DEFAULT_NAME = "BeSMART Thermostat"
DEFAULT_TIMEOUT = 3
ENTITY_ID_FORMAT = PLATFORM_DOMAIN + ".{}"

ATTR_MODE = "mode"
STATE_UNKNOWN = "unknown"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    new_entities = []
    
    for device in config_entry.interface_devices:
        wifi_box = device.wifi_box
        for thermostat in device.thermostats:
            room_id = thermostat.get("id")
            room_name = thermostat.get("name")
            new_entities.append(Thermostat(hass, config_entry, wifi_box, room_id, room_name, device.device_info))

    if new_entities:
        async_add_entities(new_entities, update_before_add=True)


async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""


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
    # BeSmart mode
    AUTO = 0  # 'Auto'
    MANUAL = 1  # 'Manuale - Confort'
    ECONOMY = 2  # 'Holiday - Economy'
    PARTY = 3  # 'Party - Confort'
    IDLE = 4  # 'Spento - Antigelo'
    DHW = 5 # 'Sanitario - Domestic hot water only'

    CLIMATE_TEMP_MAX = 35.0
    CLIMATE_TEMP_MIN = 3.0
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
    PRESET_MODE_LIST = PRESET_MODE_LIST = list(p for p in PRESET_HA_TO_BESMART if p != "DHW")

    HVAC_MODE_BESMART_TO_HA = {
        "1": HVACMode.HEAT,
        "0": HVACMode.COOL,
    }

    # BeSmart Season
    HVAC_MODE_HA_BESMART = {
        HVACMode.HEAT: "1",
        HVACMode.COOL: "0",
    }

    def __init__(self, hass, config_entry, wifi_box, room_id, room_name, device_info):
        """Initialize the thermostat."""
        self._entry_name = config_entry.options[CONF_NAME]
        self._supported_modes = config_entry.options[CONF_MODE] + [HVACMode.OFF]
        self._entry_id = config_entry.entry_id
        self._wifi_box = wifi_box
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
        self._attr_device_info = device_info

        # unique_id = <deviceID>:<roomID>
        self._attr_unique_id = f"{self._entry_id}:{self._room_id}"

        # name = <integrationName> Thermostat [<roomName>]
        self._attr_name = f"{self._room_name} Thermostat"

        # entity_id = climate.<name>
        self._entity_id = async_generate_entity_id(self._entity_id_format, self._attr_name or self._default_name, None, hass)

        # Disable backwards compatibility for new turn_on/off methods
        self._enable_turn_on_off_backwards_compatibility = False

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
        elif self._current_state == self.DHW:
            return HVACAction.OFF
        else:
            return HVACAction.IDLE

    @property
    def hvac_mode(self):
        """Current mode."""
        if self._current_state == self.DHW:
            return HVACMode.OFF
        return self.HVAC_MODE_BESMART_TO_HA.get(self._season)

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self._supported_modes

    @property
    def max_temp(self):
        """The maximum temperature."""
        if self._tempSetMark == "2":
            return self.CLIMATE_TEMP_MAX
        elif self._tempSetMark == "1":
            return self._comfT - self.CLIMATE_TEMP_STEP
        elif self._tempSetMark == "0":
            return self._saveT - self.CLIMATE_TEMP_STEP

    @property
    def min_temp(self):
        """The minimum temperature."""
        if self._tempSetMark == "2":
            return self._saveT + self.CLIMATE_TEMP_STEP
        elif self._tempSetMark == "1":
            return self._frostT + self.CLIMATE_TEMP_STEP
        elif self._tempSetMark == "0":
            return self.CLIMATE_TEMP_MIN

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
        if self._tempSetMark == "2":
            return self._comfT
        elif self._tempSetMark == "1":
            return self._saveT
        elif self._tempSetMark == "0":
            return self._frostT

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
        if self._current_state == self.DHW:
            return (
                ClimateEntityFeature.TURN_ON |
                ClimateEntityFeature.TURN_OFF
            )

        return (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.PRESET_MODE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_MODE: self._current_state,
            "setpoint_OT": self._setpoint_OT,
            "updating_temp": self._tempSet != self.target_temperature
            # "battery_state": self._battery,
            # "frost_t": self._frostT,
            # "confort_t": self._comfT,
            # "save_t": self._saveT,
            # "season_mode": self.hvac_mode,
            # "heating_state": self._heating_state,
        }

    async def async_update(self):
        """Update the data from the thermostat."""
        _LOGGER.debug("Update called")

        # Get thermostat data
        thermostat = await self._cl.thermostat(self._wifi_box, self._room_id)

        try:
            self._tempSet = float(thermostat.get("target_temp"))
        except ValueError:
            self._tempSet = 0.0

        # Current mode
        try:
            self._current_state = int(thermostat.get("mode"))
        except ValueError:
            self._current_state = 0
        
        if self._current_state == self.AUTO:
            # Extract current program step
            try:
                # from Sunday (0) to Saturday (6)
                today = datetime.today().isoweekday() % 7
                # 48 slot per day
                index = datetime.today().hour * 2 + (
                        1 if datetime.today().minute > 30 else 0
                )
                programWeek = thermostat["program"]
                # delete programWeek to have less noise on debug output
                del thermostat["program"]
                self._tempSetMark = programWeek[today][index]
            except Exception as ex:
                _LOGGER.warning(ex)
                self._tempSetMark = "2"

            # Extract manual toggle for ECO (night) mode
            try:
                # advance option is used for switching to the ECO mode (automatically disables at holiday_end_time)
                if thermostat.get("advance") == "1":
                    self._holiday_end_time = int(thermostat["holiday_end_time"])
                    self._tempSetMark = "1"
            except Exception as ex:
                _LOGGER.warning(ex)
                self._holiday_end_time = None
        elif self._current_state == self.MANUAL or self._current_state == self.PARTY:
            self._tempSetMark = "2"
        elif self._current_state == self.ECONOMY:
            self._tempSetMark = "1"
        elif self._current_state == self.IDLE:
            self._tempSetMark = "0"

        # Extract programmed temperatures
        try:
            self._frostT = float(thermostat.get("frost_temp"))
        except ValueError:
            self._frostT = 0.0
        try:
            self._saveT = float(thermostat.get("economy_temp"))
        except ValueError:
            self._saveT = 0.0
        try:
            self._comfT = float(thermostat.get("comfort_temp"))
        except ValueError:
            self._comfT = 0.0

        # Extract current temperature
        try:
            self._current_temp = float(thermostat.get("current_temp"))
        except ValueError:
            self._current_temp = 0.0

        # Current heating state
        self._heating_state = thermostat.get("heating_status", "") == "1"

        # central_heating_thermostat_OT_set_point
        self._setpoint_OT = float(thermostat.get("central_heating_thermostat_OT_set_point"))

        # Misc
        try:
            self._battery = not bool(int(thermostat.get("battery_power")))
        except ValueError:
            self._battery = False
        self._current_unit = thermostat.get("unit")
        self._season = thermostat.get("season")

    async def async_turn_on(self):
        await self.async_set_preset_mode(self.PRESET_BESMART_TO_HA.get(self.AUTO))

    async def async_turn_off(self):
        await self.async_set_preset_mode("DHW")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (COOL, HEAT) if supported."""
        season = self.HVAC_MODE_HA_BESMART.get(hvac_mode)
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode in self._supported_modes:
            current_hvac_mode = self.hvac_mode
            if season != None and self._season != season:
                await self._cl.setThermostatSeason(self._room_name, season)
            if current_hvac_mode == HVACMode.OFF:
                await self.async_turn_on()
            _LOGGER.debug("Set hvac_mode hvac_mode=%s(%s)", str(hvac_mode), str(season))

    async def async_set_preset_mode(self, preset_mode):
        """Set HVAC mode (comfort, home, sleep, Party, Off)."""
        mode = self.PRESET_HA_TO_BESMART.get(preset_mode, self.AUTO)
        await self._cl.setThermostatMode(self._wifi_box, self._room_id, mode)
        _LOGGER.debug("Set operation mode=%s(%s)", str(preset_mode), str(mode))

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if not temperature:
            return
        
        _LOGGER.debug(f"setting new temp {self._tempSetMark} {self._room_name} {temperature}")
        if self._tempSetMark == "2":
            await self._cl.setThermostatTemp(self._wifi_box, self._room_id, temperature, self._tempSetMark)
        elif self._tempSetMark == "1":
            await self._cl.setThermostatTemp(self._wifi_box, self._room_id, temperature, self._tempSetMark)
        elif self._tempSetMark == "0":
            await self._cl.setThermostatTemp(self._wifi_box, self._room_id, temperature, self._tempSetMark)

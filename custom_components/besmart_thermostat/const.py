"""Constants for the BeSMART Thermostat."""

from homeassistant.const import Platform
from homeassistant.components.schedule.const import DOMAIN as SCHEDULE_DOMAIN

DOMAIN = "besmart_thermostat"

PLATFORMS = [Platform.CLIMATE, SCHEDULE_DOMAIN]

DEFAULT_NAME = "BeSMART Thermostat"

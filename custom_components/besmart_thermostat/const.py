"""Constants for the BeSMART Thermostat."""

from homeassistant.const import Platform

DOMAIN = "besmart_thermostat"

PLATFORMS: list[Platform] = [Platform.CLIMATE]

DEFAULT_NAME = "BeSMART Thermostat"

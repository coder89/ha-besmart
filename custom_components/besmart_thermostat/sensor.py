import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the battery sensor platform."""
    if DOMAIN not in hass.data or not hass.data[DOMAIN]:
        _LOGGER.error("No climate entities found in hass.data[%s]", DOMAIN)
        return

    new_entities = []
    for device in config_entry.interface_devices:
        for thermostat in device.thermostats:
            room_id = thermostat.get("id")
            room_name = thermostat.get("name")
            unique_id = f"{config_entry.entry_id}:{room_id}"
            climate_entity = hass.data[DOMAIN].get(unique_id)
            if climate_entity:
                new_entities.append(
                    BatterySensor(climate_entity, room_name, device.device_info)
                )
            else:
                _LOGGER.warning("Climate entity not found for unique_id %s", unique_id)

    if new_entities:
        async_add_entities(new_entities, update_before_add=True)


class BatterySensor(SensorEntity):
    """Representation of a BeSMART thermostat battery sensor (percentage)."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "battery"

    def __init__(self, climate_entity, room_name, device_info):
        """Initialize the battery sensor."""
        self._climate_entity = climate_entity
        self._attr_unique_id = f"{climate_entity.unique_id}_battery"
        self._attr_name = f"{room_name} Thermostat Battery"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Return the battery level as percentage."""
        if not self._climate_entity or not self._climate_entity.extra_state_attributes:
            return None

        battery_low = self._climate_entity.extra_state_attributes.get("battery_low")

        if battery_low is True:
            return 10          # Low battery
        if battery_low is False:
            return 100         # Good battery

        return None            # Unknown

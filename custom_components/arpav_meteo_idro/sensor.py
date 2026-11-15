"""Sensors for Arpa Veneto Weather component."""
from datetime import datetime

from homeassistant.components.sensor import SensorEntity

from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_HYDRO, SENSOR_TYPES
from .entity import ArpavWeatherEntity
from .hydro_sensor import async_setup_hydro_entities

# the coordinator fetches the data: entities never update in parallel
PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up ARPA Veneto sensors from a config entry."""
    coordinator = config_entry.runtime_data.coordinator

    if config_entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HYDRO:
        await async_setup_hydro_entities(hass, config_entry, coordinator, async_add_entities)
        return

    # create a sensor for each sensor type in SENSOR_TYPES
    sensors = []
    for sensor_type in SENSOR_TYPES:
        sensors.append(ArpaVenetoSensor(coordinator, config_entry, sensor_type))
    async_add_entities(sensors)

class ArpaVenetoSensor(ArpavWeatherEntity, SensorEntity):
    """Representation of an ARPA Veneto sensor."""

    def __init__(self, coordinator, config_entry, sensor_type):
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self.station_id = config_entry.data.get("station_id")
        self.station_name = config_entry.data.get("station_name")
        self.sensor_type = sensor_type
        sensor = SENSOR_TYPES[sensor_type]
        self._attr_device_class = sensor.get("device_class") # type: ignore
        self._attr_state_class = sensor.get("state_class") # type: ignore
        self._attr_native_unit_of_measurement = sensor.get("unit")

        self._attr_unique_id = f"arpav_{sensor_type}_{self.station_id}"

        self._attr_translation_key = sensor_type
        self._attr_translation_placeholders = {"station_name": self.station_name}

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.sensor_type == "precipitation_probability":
            forecasts = self.coordinator.data["forecast"]

            # Find forecast with datetime closest to now
            now = datetime.now()
            nearest = min(forecasts, key=lambda forecast: abs(forecast["datetime"] - now))

            def get_attr(entry, key):
                value = entry.get(key)
                return value if value is not None else ""

            return get_attr(nearest, "precipitation_probability")

        return self.coordinator.data["sensors"].get(self.sensor_type)

    @property
    def extra_state_attributes(self):
        """Return additional attributes, including where the value comes from."""
        attributes = {
            "station_id": self.station_id,
            "last_update": self.coordinator.data["sensors"].get("last_update"),
        }

        # the entities of a single station are fed by different networks
        provenance = self.coordinator.data.get("sources", {}).get(self.sensor_type)
        if provenance:
            attributes.update(provenance.as_attributes())

        return attributes

    async def async_update(self):
        """Update the sensor state."""
        await self.coordinator.async_request_refresh()

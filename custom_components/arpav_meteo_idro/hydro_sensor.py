# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Sensors of the ARPAV hydrometric stations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import hydro
from .const import DOMAIN, HYDRO_ATTRIBUTION
from .hydro_coordinator import HydroCoordinator, HydroStationState


@dataclass(frozen=True, kw_only=True)
class HydroSensorDescription(SensorEntityDescription):
    """Describe a hydrometric sensor."""

    value_fn: Callable[[HydroStationState], Any]


def _reading(state: HydroStationState) -> hydro.HydroReading | None:
    return state.reading


SENSORS: tuple[HydroSensorDescription, ...] = (
    HydroSensorDescription(
        key="level",
        translation_key="hydro_level",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        value_fn=lambda s: s.reading.level if s.reading else None,
    ),
    HydroSensorDescription(
        key="observed_at",
        translation_key="hydro_observed_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.reading.observed_at if s.reading else None,
    ),
    HydroSensorDescription(
        key="status",
        translation_key="hydro_status",
        device_class=SensorDeviceClass.ENUM,
        options=hydro.BANDS,
        value_fn=lambda s: s.reading.band if s.reading else hydro.BAND_MISSING,
    ),
    HydroSensorDescription(
        key="trend",
        translation_key="hydro_trend",
        device_class=SensorDeviceClass.ENUM,
        options=hydro.TRENDS,
        value_fn=lambda s: s.reading.trend if s.reading else None,
    ),
    HydroSensorDescription(
        key="level_change",
        translation_key="hydro_level_change",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        value_fn=lambda s: s.reading.change if s.reading else None,
    ),
)


def level_unique_id(station_id: str) -> str:
    """Return the unique ID of the level sensor of a station (used by the archive)."""
    return f"{DOMAIN}_hydro_{station_id}_level"


async def async_setup_hydro_entities(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: HydroCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensors of every selected station."""
    async_add_entities(
        HydroSensor(coordinator, meta, description)
        for meta in coordinator.stations
        for description in SENSORS
    )


class HydroSensor(CoordinatorEntity[HydroCoordinator], SensorEntity):
    """A sensor of a hydrometric station."""

    entity_description: HydroSensorDescription
    _attr_has_entity_name = True
    _attr_attribution = HYDRO_ATTRIBUTION

    def __init__(self, coordinator: HydroCoordinator, meta: dict,
                 description: HydroSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._station_id = meta["id"]
        self._attr_unique_id = f"{DOMAIN}_hydro_{self._station_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"hydro_{self._station_id}")},
            name=meta.get("name") or f"ARPAV {self._station_id}",
            manufacturer="ARPAV",
            model="Hydrometric station",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{hydro.XML_BASE}/{meta.get('link') or ''}",
        )

    @property
    def _state(self) -> HydroStationState | None:
        return (self.coordinator.data or {}).get(self._station_id)

    @property
    def available(self) -> bool:
        """The status is always meaningful; the others need a reading."""
        if not super().available or self._state is None:
            return False
        if self.entity_description.key == "status":
            return True
        return self.native_value is not None

    @property
    def native_value(self):
        """Return the value of the sensor."""
        state = self._state
        return None if state is None else self.entity_description.value_fn(state)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose provenance on every sensor, thresholds and position on the status."""
        state = self._state
        if state is None:
            return None
        reading = state.reading
        attributes: dict[str, Any] = {
            "station_id": self._station_id,
            "sensor_id": state.series.sensor_id if state.series else None,
            "source": "arpav_hydrometric_station",
            "source_url": f"{hydro.XML_BASE}/{state.meta.get('link') or ''}",
            "source_observed_at": reading.observed_at.isoformat() if reading and reading.observed_at else None,
        }
        if self.entity_description.key == "status":
            g1, g2, g3 = reading.thresholds if reading else (None, None, None)
            axis = hydro.chart_axis((g1, g2, g3))
            attributes.update({
                # normalized chart scale: G1 at 60% and G3 at 90% of the height
                "chart_min_m": axis[0] if axis else None,
                "chart_max_m": axis[1] if axis else None,
                # the essentials in one place, for tables that list every station
                "station_name": state.meta.get("name"),
                "level_m": reading.level if reading else None,
                "level_change_m": reading.change if reading else None,
                "trend": reading.trend if reading else None,
                "guardia1_m": g1,
                "guardia2_m": g2,
                "guardia3_m": g3,
                "quality": reading.quality if reading else hydro.QUALITY_MISSING,
                "age_minutes": reading.age_minutes if reading else None,
                "last_sample_valid": reading.last_sample_valid if reading else None,
                "display_order": state.order,
                "topology_status": "candidate",
                "latitude": state.meta.get("latitude"),
                "longitude": state.meta.get("longitude"),
                "fetch_error": state.error,
                "acquisition_status": state.acquisition_status,
                "last_successful_acquisition": state.fetched_at.isoformat() if state.fetched_at else None,
                "next_retry_at": state.next_retry_at.isoformat() if state.next_retry_at else None,
            })
        return attributes

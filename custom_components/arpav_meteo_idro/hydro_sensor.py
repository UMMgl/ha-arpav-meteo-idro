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
from homeassistant.const import EntityCategory, UnitOfLength, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import hydro
from .const import DOMAIN
from .entity import ArpavHydroEntity
from .hydro_coordinator import HydroCoordinator, HydroStationState
from .hydro_topology import station_key, topology_evidence


ATTR_SAMPLES_24H = "samples_24h"


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
        # the time is also an attribute of every sensor: rarely needed as an entity
        entity_registry_enabled_default=False,
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
        # the trend sensor already says where the level is going
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        value_fn=lambda s: s.reading.change if s.reading else None,
    ),
)


def _flow_sample(state: HydroStationState) -> hydro.HydroSample | None:
    return hydro.last_valid_sample(state.flow)


# created only for the stations whose file holds a PORTATA series (see below)
FLOW_SENSOR = HydroSensorDescription(
    key="flow",
    translation_key="hydro_flow",
    device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    state_class=SensorStateClass.MEASUREMENT,
    native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_SECOND,
    suggested_display_precision=2,
    value_fn=lambda s: sample.value if (sample := _flow_sample(s)) else None,
)


def _publishes_flow(coordinator: HydroCoordinator, station_id: str) -> bool:
    state = (coordinator.data or {}).get(station_id)
    return state is not None and state.flow is not None


def level_unique_id(station_id: str) -> str:
    """Return the unique ID of the level sensor of a station (used by the archive)."""
    return f"{DOMAIN}_hydro_{station_id}_level"


async def async_setup_hydro_entities(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: HydroCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the sensors of every selected station."""
    entities = [
        HydroSensor(coordinator, meta, description)
        for meta in coordinator.stations
        for description in SENSORS
    ]
    async_add_entities(entities)

    # about half of the stations publish a discharge: no permanently empty sensor for the others,
    # and a station unreadable at setup (or publishing later) gets it on a later refresh
    with_flow: set[str] = set()

    @callback
    def add_flow_sensors() -> None:
        new = [meta for meta in coordinator.stations
               if meta["id"] not in with_flow and _publishes_flow(coordinator, meta["id"])]
        if new:
            with_flow.update(meta["id"] for meta in new)
            async_add_entities(HydroSensor(coordinator, meta, FLOW_SENSOR) for meta in new)

    add_flow_sensors()
    entry.async_on_unload(coordinator.async_add_listener(add_flow_sensors))


class HydroSensor(ArpavHydroEntity, SensorEntity):
    """A sensor of a hydrometric station."""

    entity_description: HydroSensorDescription
    coordinator: HydroCoordinator
    # up to ~144 points of history: useful to charts, useless (and heavy) in the database
    _unrecorded_attributes = frozenset({ATTR_SAMPLES_24H})

    def __init__(self, coordinator: HydroCoordinator, meta: dict,
                 description: HydroSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, meta)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_hydro_{self._station_id}_{description.key}"

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
        series = state.series
        observed_at = reading.observed_at if reading else None
        if self.entity_description.key == "flow":
            # the discharge is a series of its own, with its own ID and time
            series = state.flow
            sample = hydro.last_valid_sample(series)
            observed_at = sample.observed_at if sample else None
        attributes: dict[str, Any] = {
            "station_id": self._station_id,
            "sensor_id": series.sensor_id if series else None,
            "source": "arpav_hydrometric_station",
            "source_url": hydro.station_url(state.meta.get("link"), self._station_id),
            "source_observed_at": observed_at.isoformat() if observed_at else None,
        }
        if self.entity_description.key == "level":
            # every sample of the last 24 h (10 minutes apart), for ApexCharts
            attributes[ATTR_SAMPLES_24H] = hydro.recent_samples(state.series)
        if self.entity_description.key == "status":
            g1, g2, g3 = reading.thresholds if reading else (None, None, None)
            axis = hydro.chart_axis((g1, g2, g3))
            # ARPAV thresholds always win; the user ceiling only fills the gap
            ceiling = None if axis else self.coordinator.axis_ceilings.get(station_key(self._station_id))
            evidence = topology_evidence(self.coordinator.river, self._station_id)
            order_source = "topology" if evidence else "selection"
            attributes.update({
                # normalized chart scale: G1 at 60% and G3 at 90% of the height
                "chart_min_m": axis[0] if axis else None,
                "chart_max_m": axis[1] if axis else ceiling,
                "axis_ceiling_source": "user" if ceiling is not None else None,
                # the essentials in one place, for tables that list every station
                "station_name": hydro.normalize_name(state.meta.get("name") or "") or None,
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
                "display_order_source": order_source,
                "topology_status": "verified" if evidence else "candidate",
                "latitude": state.meta.get("latitude"),
                "longitude": state.meta.get("longitude"),
                "fetch_error": state.error,
                "acquisition_status": state.acquisition_status,
                "last_successful_acquisition": state.fetched_at.isoformat() if state.fetched_at else None,
                "next_retry_at": state.next_retry_at.isoformat() if state.next_retry_at else None,
            })
            if evidence:
                attributes.update({
                    "topology_source_url": evidence.source_url,
                    "topology_source_reference": evidence.source_reference,
                    "topology_verified_on": evidence.verified_on,
                    "topology_confidence": evidence.confidence,
                })
        return attributes

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Diagnostics of the config entries (weather location and hydrometric river)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .hydro_coordinator import HydroCoordinator

# whatever locates the user: the coordinates, the municipality and the nearest
# weather station of the weather entry (the entry title is built from them)
TO_REDACT = {
    "latitude",
    "longitude",
    "station_latitude",
    "station_longitude",
    "station_id",
    "station_name",
    "comune_id",
    "comune_name",
    "title",
}


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _coordinator_status(coordinator) -> dict[str, Any]:
    """Return what every coordinator shares: whether and when it last worked."""
    last_exception = coordinator.last_exception
    return {
        "last_update_success": coordinator.last_update_success,
        "last_update_success_time": _iso(getattr(coordinator, "last_update_success_time", None)),
        "update_interval": str(coordinator.update_interval),
        "last_exception": (
            f"{type(last_exception).__name__}: {last_exception}" if last_exception else None
        ),
    }


def _hydro_stations(coordinator: HydroCoordinator) -> list[dict[str, Any]]:
    """Return the selected stations with the outcome of their last fetch."""
    states = coordinator.data or {}
    stations = []
    for meta in coordinator.stations:
        state = states.get(meta["id"])
        reading = state.reading if state else None
        stations.append({
            "meta": dict(meta),
            "acquisition_status": state.acquisition_status if state else None,
            "last_fetch_error": state.error if state else None,
            "consecutive_failures": state.consecutive_failures if state else None,
            "last_successful_acquisition": _iso(state.fetched_at) if state else None,
            "next_retry_at": _iso(state.next_retry_at) if state else None,
            "band": reading.band if reading else None,
            "quality": reading.quality if reading else None,
            "observed_at": _iso(reading.observed_at) if reading else None,
            "age_minutes": reading.age_minutes if reading else None,
        })
    return stations


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a config entry, without anything that locates the user."""
    coordinator = entry.runtime_data.coordinator
    result: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": _coordinator_status(coordinator),
    }

    if isinstance(coordinator, HydroCoordinator):
        result["entry_type"] = "hydro"
        result["stations"] = _hydro_stations(coordinator)
    else:
        data = coordinator.data or {}
        sensors = data.get("sensors") or {}
        result["entry_type"] = "weather"
        result["data"] = {
            "sensors_with_value": sorted(key for key, value in sensors.items() if value is not None),
            "sensors_without_value": sorted(key for key, value in sensors.items() if value is None),
            "forecast_entries": len(data.get("forecast") or []),
        }

    return async_redact_data(result, TO_REDACT)

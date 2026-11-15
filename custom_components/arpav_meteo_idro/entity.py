# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Base entities shared by the platforms of the integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import hydro
from .const import DOMAIN, HYDRO_ATTRIBUTION


class ArpavWeatherEntity(CoordinatorEntity[DataUpdateCoordinator]):
    """An entity of a weather location: one service device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device of the weather location."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="Arpa Veneto Weather",
            entry_type=DeviceEntryType.SERVICE,
        )


class ArpavHydroEntity(CoordinatorEntity):
    """An entity of a hydrometric station: one service device per station."""

    _attr_has_entity_name = True
    _attr_attribution = HYDRO_ATTRIBUTION

    def __init__(self, coordinator, meta: dict) -> None:
        """Initialize the entity for the station described by ``meta``."""
        super().__init__(coordinator)
        self._station_id = meta["id"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"hydro_{self._station_id}")},
            name=meta.get("name") or f"ARPAV {self._station_id}",
            manufacturer="ARPAV",
            model="Hydrometric station",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{hydro.XML_BASE}/{meta.get('link') or ''}",
        )

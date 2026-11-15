# SPDX-License-Identifier: Apache-2.0
"""Coordinator of the ARPAV hydrometric stations of a config entry."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import hydro
from .const import (
    CONF_HYDRO_RIVER,
    CONF_HYDRO_STALE_MINUTES,
    CONF_HYDRO_STATIONS,
    CONF_HYDRO_TREND_THRESHOLD,
    CONF_HYDRO_TREND_THRESHOLD_DEFAULT,
    CONF_HYDRO_UPDATE_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


@dataclass
class HydroStationState:
    """The latest known state of a station."""

    meta: dict
    order: int
    data: hydro.HydroStationData | None = None
    series: hydro.HydroSeries | None = None
    reading: hydro.HydroReading | None = None
    fetched_at: datetime | None = None
    error: str | None = None


async def async_fetch_document(session: aiohttp.ClientSession, url: str) -> bytes:
    """Download an ARPAV XML document."""
    async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
        response.raise_for_status()
        return await response.read()


async def async_fetch_registry(hass: HomeAssistant) -> list[hydro.HydroStation]:
    """Download and parse the hydrometric station registry."""
    session = async_get_clientsession(hass)
    return hydro.parse_registry(await async_fetch_document(session, hydro.REGISTRY_URL))


def station_meta(station: hydro.HydroStation) -> dict:
    """Return what is stored in the config entry about a station."""
    return {
        "id": station.station_id,
        "name": station.name,
        "place": station.place,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "link": station.link,
    }


class HydroCoordinator(DataUpdateCoordinator[dict[str, HydroStationState]]):
    """Fetch the files of the selected stations and evaluate their level."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.river = entry.data.get(CONF_HYDRO_RIVER)
        self.stations: list[dict] = list(entry.options.get(CONF_HYDRO_STATIONS, []))
        self.trend_threshold = (entry.options.get(
            CONF_HYDRO_TREND_THRESHOLD, CONF_HYDRO_TREND_THRESHOLD_DEFAULT)) / 100
        self.stale_minutes = entry.options.get(CONF_HYDRO_STALE_MINUTES) or 0
        self._session = async_get_clientsession(hass)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_hydro_{self.river}",
            update_interval=timedelta(minutes=CONF_HYDRO_UPDATE_MINUTES),
        )

    async def _async_update_data(self) -> dict[str, HydroStationState]:
        """Fetch every station; a failing station keeps its previous data."""
        previous = self.data or {}
        results = await asyncio.gather(
            *(self._async_fetch_station(meta) for meta in self.stations),
            return_exceptions=True,
        )

        now = dt_util.utcnow()
        states: dict[str, HydroStationState] = {}
        failures = 0
        for order, (meta, result) in enumerate(zip(self.stations, results, strict=True)):
            station_id = meta["id"]
            state = HydroStationState(meta=meta, order=(order + 1) * 10)
            old = previous.get(station_id)

            if isinstance(result, BaseException):
                failures += 1
                _LOGGER.debug("Unable to update station %s: %s", station_id, result)
                if old is not None:
                    state.data, state.series, state.fetched_at = old.data, old.series, old.fetched_at
                state.error = str(result) or type(result).__name__
            else:
                state.data = result
                state.series = result.level_series(meta.get("sensor_id"))
                state.fetched_at = now

            stale = self.stale_minutes or hydro.default_stale_minutes(state.series)
            # re-evaluated even on failure: an old reading must turn stale
            state.reading = hydro.evaluate(state.series, now, stale, self.trend_threshold)
            states[station_id] = state

        if self.stations and failures == len(self.stations) and not previous:
            raise UpdateFailed("no ARPAV hydrometric station could be read")
        return states

    async def _async_fetch_station(self, meta: dict) -> hydro.HydroStationData:
        url = f"{hydro.XML_BASE}/{meta.get('link') or f'{int(meta['id']):04d}.xml'}"
        document = await async_fetch_document(self._session, url)
        return hydro.parse_station(document)

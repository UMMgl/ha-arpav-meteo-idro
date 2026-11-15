# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Coordinator of the ARPAV hydrometric stations of a config entry."""

from __future__ import annotations

import asyncio
import logging
import random
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
MAX_CONCURRENT_STATIONS = 5
POLL_INTERVAL = timedelta(minutes=CONF_HYDRO_UPDATE_MINUTES)
MAX_RETRY_DELAY = timedelta(minutes=30)


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
    acquisition_status: str = "ok"
    consecutive_failures: int = 0
    next_retry_at: datetime | None = None


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
        self._station_requests = asyncio.Semaphore(MAX_CONCURRENT_STATIONS)
        self.archive_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_hydro_{self.river}",
            update_interval=POLL_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, HydroStationState]:
        """Update due stations independently and re-evaluate retained observations."""
        previous = self.data or {}
        states = await asyncio.gather(*(
            self._async_update_station(meta, (index + 1) * 10, previous.get(meta["id"]))
            for index, meta in enumerate(self.stations)
        ))
        if states and all(state.acquisition_status == "fetch_error" for state in states) and not previous:
            raise UpdateFailed("no ARPAV hydrometric station could be read")
        return {state.meta["id"]: state for state in states}

    async def _async_update_station(
        self, meta: dict, order: int, previous: HydroStationState | None,
    ) -> HydroStationState:
        """Fetch a station when due and retain the last usable observation on failure."""
        state = HydroStationState(meta=meta, order=order)
        if previous is not None:
            state.data = previous.data
            state.series = previous.series
            state.fetched_at = previous.fetched_at
            state.consecutive_failures = previous.consecutive_failures
            state.next_retry_at = previous.next_retry_at

        if state.next_retry_at and dt_util.utcnow() < state.next_retry_at:
            state.acquisition_status = "backoff"
            state.error = previous.error if previous else None
        else:
            try:
                async with self._station_requests:
                    data = await self._async_fetch_station(meta)
            except (aiohttp.ClientError, TimeoutError, hydro.HydroParseError) as err:
                state.acquisition_status = "fetch_error"
                state.error = str(err) or type(err).__name__
            else:
                series = data.level_series(meta.get("sensor_id"))
                state.acquisition_status = _acquisition_status(series, previous)
                if state.acquisition_status == "ok":
                    state.data, state.series = data, series
                    state.fetched_at = dt_util.utcnow()
                elif state.series is None:
                    state.data, state.series = data, series

            if state.acquisition_status == "ok":
                state.consecutive_failures = 0
                state.next_retry_at = None
            else:
                state.consecutive_failures += 1
                # Let the first failure retry at the normal polling cadence.
                if state.consecutive_failures > 1:
                    delay = POLL_INTERVAL * 2 ** min(state.consecutive_failures - 1, 3)
                    # jitter of the retry time, not a security use of randomness
                    delay *= random.uniform(1.0, 1.2)  # nosec B311
                    state.next_retry_at = dt_util.utcnow() + min(delay, MAX_RETRY_DELAY)
                _LOGGER.debug("ARPAV station %s: %s (%s)", meta["id"], state.acquisition_status, state.error)

        stale = self.stale_minutes or hydro.default_stale_minutes(state.series)
        state.reading = hydro.evaluate(state.series, dt_util.utcnow(), stale, self.trend_threshold)
        return state

    async def _async_fetch_station(self, meta: dict) -> hydro.HydroStationData:
        url = hydro.station_url(meta.get("link"), meta["id"])
        document = await async_fetch_document(self._session, url)
        return hydro.parse_station(document)


def _acquisition_status(series: hydro.HydroSeries | None, previous: HydroStationState | None) -> str:
    """Describe whether the response has a usable, current series."""
    if series is None:
        return "no_level_series"
    latest = next((sample for sample in reversed(series.samples) if sample.value is not None), None)
    if latest is None:
        return "no_valid_samples"
    if previous and previous.reading and previous.reading.observed_at:
        if latest.observed_at < previous.reading.observed_at:
            return "older_observation"
    return "ok"

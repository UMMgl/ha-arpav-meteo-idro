# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Fill missing long-term level statistics from complete hourly ARPAV observations."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics, statistics_during_period
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import hydro
from .const import DOMAIN
from .hydro_coordinator import HydroCoordinator
from .hydro_sensor import level_unique_id

_LOGGER = logging.getLogger(__name__)


def _metadata(entity_id: str) -> StatisticMetaData:
    """Return metadata matching the ones the recorder keeps for a level sensor."""
    return StatisticMetaData(
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=False,
        name=None,
        source="recorder",
        statistic_id=entity_id,
        unit_class="distance",
        unit_of_measurement=UnitOfLength.METERS,
    )


async def async_import_hydro_history(hass: HomeAssistant, coordinator: HydroCoordinator) -> dict[str, dict]:
    """Import the hourly statistics of every station.

    Return, per level sensor, how many hours were written and the period.
    """
    if "recorder" not in hass.config.components:
        _LOGGER.warning("The recorder is not enabled: the hydrometric history cannot be archived")
        return {}
    if not coordinator.data:
        await coordinator.async_request_refresh()

    async with coordinator.archive_lock:
        return await _async_fill_missing_hours(hass, coordinator)


async def _async_fill_missing_hours(
    hass: HomeAssistant, coordinator: HydroCoordinator,
) -> dict[str, dict]:
    """Read existing hours and queue only complete hours the recorder is missing."""
    recorder = get_instance(hass)
    registry = er.async_get(hass)
    one_hour = timedelta(hours=1)
    cut = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - one_hour
    candidates = {}
    for station_id, state in (coordinator.data or {}).items():
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, level_unique_id(station_id))
        if entity_id is not None:
            candidates[entity_id] = (station_id, hydro.hourly_statistics(
                state.series, before=cut, complete_hours_only=True,
            ))

    starts = [row["start"] for _, rows in candidates.values() for row in rows]
    existing = {}
    if starts:
        existing = await recorder.async_add_executor_job(
            statistics_during_period, hass, min(starts), max(starts) + one_hour,
            set(candidates), "hour", None, {"mean"},
        )

    report = {}
    for entity_id, (station_id, rows) in candidates.items():
        present = {row["start"] for row in existing.get(entity_id, ())}
        missing = [row for row in rows if row["start"].timestamp() not in present]
        report[entity_id] = {
            "station_id": station_id,
            "hours": len(missing),
            "from": missing[0]["start"].isoformat() if missing else None,
            "to": missing[-1]["start"].isoformat() if missing else None,
        }
        if missing:
            async_import_statistics(hass, _metadata(entity_id), missing)

    total = sum(item["hours"] for item in report.values())
    if total:
        # A following manual or scheduled import must see the rows just queued.
        await recorder.async_block_till_done()
    _LOGGER.info("Hydrometric history: %s hourly statistics imported into %s level sensors",
                 total, sum(1 for item in report.values() if item["hours"]))
    return report

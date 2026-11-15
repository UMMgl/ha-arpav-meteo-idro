# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Completion of the long-term statistics of the hydrometric level sensors.

Every station file holds the last ~2-3 days of readings. Once a day (and at
start-up, and on demand through a service) the hourly mean/min/max are rebuilt
from those readings and imported into the statistics of the level sensor of
the station. Hours missed while Home Assistant was down or the download failed
are filled in; hours already present are overwritten with values computed from
every ARPAV reading of the hour. Writing the same hour twice overwrites it, so
the import is idempotent.

Only hours that ended at least an hour ago are written, so an hour the
recorder is still compiling is never touched.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.recorder.models import StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics
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


async def async_import_hydro_history(hass: HomeAssistant, coordinator: HydroCoordinator) -> int:
    """Import the hourly statistics of every station; return how many hours."""
    if "recorder" not in hass.config.components:
        _LOGGER.debug("The recorder is not enabled: nothing to archive")
        return 0
    if not coordinator.data:
        await coordinator.async_request_refresh()

    registry = er.async_get(hass)
    cut = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    imported = 0
    for station_id, state in (coordinator.data or {}).items():
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, level_unique_id(station_id))
        if entity_id is None:
            continue
        statistics = hydro.hourly_statistics(state.series, before=cut)
        if not statistics:
            continue
        async_import_statistics(hass, _metadata(entity_id), statistics)
        imported += len(statistics)
        _LOGGER.debug("Imported %s hourly statistics into %s", len(statistics), entity_id)
    return imported

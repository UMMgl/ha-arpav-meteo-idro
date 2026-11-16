# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Guards of the hydrometric history import that need no recorder."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

from custom_components.arpav_meteo_idro import hydro_statistics  # noqa: E402


def _hass(components):
    return SimpleNamespace(config=SimpleNamespace(components=set(components)))


def _coordinator(data):
    return SimpleNamespace(data=data, archive_lock=asyncio.Lock(), async_request_refresh=AsyncMock())


async def test_import_without_recorder_is_skipped(caplog):
    """Without the recorder nothing is fetched or written, and the user is told."""
    coordinator = _coordinator({})
    with caplog.at_level(logging.WARNING), \
            patch.object(hydro_statistics, "_async_fill_missing_hours", AsyncMock()) as fill:
        assert await hydro_statistics.async_import_hydro_history(_hass([]), coordinator) == {}

    assert "recorder is not enabled" in caplog.text
    coordinator.async_request_refresh.assert_not_awaited()
    fill.assert_not_awaited()


async def test_import_refreshes_an_empty_coordinator_first():
    """An import before the first poll asks the coordinator for data, then fills the gaps."""
    coordinator = _coordinator({})
    report = {"sensor.level": {"station_id": "1", "hours": 0, "from": None, "to": None}}
    with patch.object(hydro_statistics, "_async_fill_missing_hours", AsyncMock(return_value=report)) as fill:
        result = await hydro_statistics.async_import_hydro_history(_hass(["recorder"]), coordinator)

    assert result == report
    coordinator.async_request_refresh.assert_awaited_once()
    fill.assert_awaited_once()


async def test_import_with_data_does_not_refresh():
    """A coordinator that already holds data is not refreshed again."""
    coordinator = _coordinator({"1": object()})
    with patch.object(hydro_statistics, "_async_fill_missing_hours", AsyncMock(return_value={})):
        await hydro_statistics.async_import_hydro_history(_hass(["recorder"]), coordinator)

    coordinator.async_request_refresh.assert_not_awaited()

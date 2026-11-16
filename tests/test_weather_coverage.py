# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Branches of ``weather.py`` the end-to-end tests do not reach.

The ARPAV payloads are served by ``FakeSession`` (no network); the entity is
built on a stand-in coordinator so each property can be read in isolation.
"""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

import aiohttp  # noqa: E402

from custom_components.arpav_meteo_idro import weather  # noqa: E402

from .helpers import FakeSession, load_json  # noqa: E402


def _entity(data, options=None):
    """Return a weather entity reading ``data`` from a stand-in coordinator."""
    entry = SimpleNamespace(
        entry_id="entry",
        data={"comune_name": "Padova (Pd)", "comune_id": "c1", "station_name": "Legnaro", "station_id": "s1"},
        options=options or {},
    )
    return weather.ArpaVenetoWeatherEntity(SimpleNamespace(data=data), entry)


async def test_get_forecast_keeps_only_the_zone_of_the_padua_plain():
    """Only the bulletins of zone 13 are returned."""
    session = FakeSession({"bollettini_meteo_giornate": [
        {"zonaid": 13, "id": 1}, {"zonaid": 7, "id": 2}, {"zonaid": 13, "id": 3}]})
    assert await weather.async_get_forecast(session) == [{"zonaid": 13, "id": 1}, {"zonaid": 13, "id": 3}]
    assert session.requests == [f"{weather.API_BASE}/bollettini_meteo_giornate"]


async def test_get_forecast_http_error_is_raised():
    """An error status is not swallowed."""
    session = FakeSession({"bollettini_meteo_giornate": ([], 500)})
    with pytest.raises(aiohttp.ClientResponseError):
        await weather.async_get_forecast(session)


async def test_get_current_conditions_returns_the_first_row_or_nothing():
    """The first meteogram row is returned, an empty answer gives an empty dict."""
    rows = load_json("arpav_meteogrammi_tabella.json")["data"]
    session = FakeSession({"meteo_meteogrammi_tabella": rows})
    assert await weather.async_get_current_conditions(session, "902") == rows[0]
    assert session.requests == [f"{weather.API_BASE}/meteo_meteogrammi_tabella?codseqst=902"]

    assert await weather.async_get_current_conditions(FakeSession({"meteo_meteogrammi_tabella": []}), "902") == {}


async def test_get_current_conditions_http_error_is_raised():
    """An error status is not swallowed."""
    session = FakeSession({"meteo_meteogrammi_tabella": ([], 503)})
    with pytest.raises(aiohttp.ClientResponseError):
        await weather.async_get_current_conditions(session, "902")


def test_datetime_encoder():
    """Datetimes are written as ISO strings, anything else is not serialisable."""
    stamp = datetime(2026, 11, 16, 12, 30)
    assert json.dumps({"at": stamp}, cls=weather.DateTimeEncoder) == '{"at": "2026-11-16T12:30:00"}'
    with pytest.raises(TypeError):
        json.dumps({"bad": object()}, cls=weather.DateTimeEncoder)


def test_precipitation_and_condition_come_from_the_sensors():
    """Precipitation and condition mirror the coordinator readings."""
    entity = _entity({"sensors": {"precipitation": 2.4, "condition": "rainy"}})
    assert entity.native_precipitation == 2.4
    assert entity.condition == "rainy"
    assert entity.native_condition == "rainy"
    assert entity.state == "rainy"

    empty = _entity({"sensors": {}})
    assert empty.native_precipitation is None
    assert empty.native_condition is None


async def test_daily_forecast_without_any_range_drops_the_minimum():
    """A day whose only half-day has no range keeps the maximum and has no minimum."""
    forecast = {
        "datetime": datetime(2026, 11, 16, 12),
        "type": "twice_daily",
        "is_daytime": True,
        "native_temperature": 18,
        "native_templow": None,
    }
    entity = _entity({"sensors": {}, "forecast": [forecast]})

    daily = await entity.async_forecast_daily()

    assert len(daily) == 1
    assert daily[0]["native_temperature"] == 18
    assert "native_templow" not in daily[0]
    assert daily[0]["type"] == "daily"
    assert daily[0]["datetime"] == "2026-11-16"
    assert entity._attr_available is True

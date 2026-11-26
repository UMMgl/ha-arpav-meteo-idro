# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Tests of the METAR client and decoder, on recorded AWC payloads (no network)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl")  # the package needs Home Assistant, which runs on POSIX only
pytest.importorskip("homeassistant")

import aiohttp  # noqa: E402

from custom_components.arpav_meteo_idro import http_limits, metar  # noqa: E402

from .helpers import FakeSession, load_json  # noqa: E402


def _patch_session(routes):
    session = FakeSession(routes)
    return session, patch.object(metar, "async_get_clientsession", lambda hass: session)


def _distance(lat, lon):
    return abs(lat - 45.4) + abs(lon - 11.9)


async def test_fetch_stations_keeps_metar_sites_nearest_reporting_first():
    """TAF-only, position-less and id-less entries are dropped; non reporting ones go last."""
    reports = [r for r in load_json("metar_reports.json") if r["icaoId"] == "LIPZ"]
    _, patcher = _patch_session({"stationinfo": load_json("metar_stationinfo.json"), "/metar": reports})
    with patcher:
        stations = await metar.async_fetch_stations(None, 45.4, 11.9, _distance)

    assert [s.icao for s in stations] == ["LIPZ", "LIPU", "LIPT"]
    assert stations[0].reporting
    assert not stations[1].reporting
    assert stations[2].name == "LIPT"  # no site name: the code is used
    assert "not reporting" in stations[1].label
    assert "not reporting" not in stations[0].label
    assert stations[0].label.startswith("LIPZ - Venice/Tessera (")


async def test_reporting_check_failure_assumes_all_reporting():
    """When the report lookup fails the list is still usable."""
    _, patcher = _patch_session({"stationinfo": load_json("metar_stationinfo.json"),
                                 "/metar": aiohttp.ClientError("boom")})
    with patcher:
        stations = await metar.async_fetch_stations(None, 45.4, 11.9, _distance)
    assert stations
    assert all(s.reporting for s in stations)


async def test_reporting_icaos_empty_list_does_no_request():
    """No aerodromes, no request."""
    session, patcher = _patch_session({})
    with patcher:
        assert await metar._async_reporting_icaos(None, []) == set()
    assert session.requests == []


async def test_fetch_observation_decodes_report():
    """A report becomes values converted to the units of Home Assistant."""
    _, patcher = _patch_session({"/metar": load_json("metar_reports.json")[:1]})
    with patcher:
        observation = await metar.async_fetch_observation(None, "LIPZ")

    assert observation.icao == "LIPZ"
    assert observation.name == "METAR LIPZ"
    assert observation.observed_at == "2026-08-18T10:20:00+00:00"
    assert observation.cloud_coverage == 50  # SCT is the most covering layer: 4 oktas
    assert observation.values["visibility"] == pytest.approx(9.66, abs=0.01)
    assert observation.values["pressure"] == 1015.0
    assert observation.values["wind_speed"] == pytest.approx(18.52)
    assert observation.values["native_wind_bearing"] == 250
    assert "wind_bearing" in observation.values
    assert 50 < observation.values["humidity"] < 60
    assert observation.raw.startswith("METAR LIPZ")


async def test_fetch_observation_variable_wind_has_no_bearing():
    """VRB wind direction is not a number: no bearing."""
    _, patcher = _patch_session({"/metar": load_json("metar_reports.json")[1:]})
    with patcher:
        observation = await metar.async_fetch_observation(None, "LIPU")
    assert "wind_bearing" not in observation.values
    assert observation.values["wind_speed"] == pytest.approx(5.56)


@pytest.mark.parametrize("payload", [[], aiohttp.ClientError("down"), TimeoutError()])
async def test_fetch_observation_failures_return_none(payload):
    """An optional source never raises: no data, no problem."""
    _, patcher = _patch_session({"/metar": payload})
    with patcher:
        assert await metar.async_fetch_observation(None, "LIPZ") is None


def test_is_current():
    """Reports older than the maximum age, or undated, are not current."""
    now = datetime.now(UTC)
    fresh = metar.MetarObservation("X", observed_at=(now - timedelta(minutes=30)).isoformat())
    stale = metar.MetarObservation("X", observed_at=(now - timedelta(hours=5)).isoformat())
    naive = metar.MetarObservation(
        "X", observed_at=(now - timedelta(minutes=5)).replace(tzinfo=None).isoformat())
    assert fresh.is_current
    assert naive.is_current
    assert not stale.is_current
    assert not metar.MetarObservation("X").is_current
    assert not metar.MetarObservation("X", observed_at="garbage").is_current


@pytest.mark.parametrize(("weather", "cover", "is_day", "expected"), [
    ("TSRA", 100, True, "lightning-rainy"),
    ("TS", 100, True, "lightning"),
    ("-SN", None, True, "snowy"),
    ("SNRA", None, True, "snowy-rainy"),
    ("FZRA", None, True, "snowy-rainy"),
    ("GR", None, True, "hail"),
    ("+RA", 100, True, "pouring"),
    ("-DZ", 100, True, "rainy"),
    ("BR", 0, True, "fog"),
    (None, 0, True, "sunny"),
    (None, 0, False, "clear-night"),
    (None, 25, True, "partlycloudy"),
    (None, 75, True, "cloudy"),
    (None, None, True, None),
])
def test_condition(weather, cover, is_day, expected):
    """Present weather wins over the cloud cover."""
    observation = metar.MetarObservation("X", weather=weather, cloud_coverage=cover)
    assert metar.condition(observation, is_day) == expected


def test_condition_without_observation():
    """No report, no condition."""
    assert metar.condition(None, True) is None


def test_cloud_coverage():
    """Layers decide the cover; explicit clear tokens mean clear; nothing means not observed."""
    assert metar._cloud_coverage([{"cover": "ovc"}, {"cover": "FEW"}], "") == 100
    assert metar._cloud_coverage([{"cover": "??"}], "METAR X NCD") == 0
    assert metar._cloud_coverage([], "METAR X CAVOK") == 0
    assert metar._cloud_coverage(None, "METAR X 9999") is None


@pytest.mark.parametrize(("value", "expected"), [
    (None, None), ("abc", None), ("6+", 9.66), (1, 1.61), ("0.5", 0.8),
])
def test_visibility_km(value, expected):
    """Statute miles become km, a trailing + is kept as a lower bound."""
    result = metar._visibility_km(value)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, abs=0.01)


def test_relative_humidity():
    """Magnus-Tetens humidity, bounded to 0..100."""
    assert metar._relative_humidity(None, 1) is None
    assert metar._relative_humidity(10, None) is None
    assert metar._relative_humidity("x", 1) is None
    assert metar._relative_humidity(20, 20) == 100
    assert 0 <= metar._relative_humidity(30, -20) <= 20


def test_observed_at_fallbacks():
    """The report time wins, obsTime is the fallback, otherwise None."""
    assert metar._observed_at({"reportTime": "2026-08-18T11:00:00.000Z"}) == "2026-08-18T11:00:00+00:00"
    assert metar._observed_at({"reportTime": "bad", "obsTime": 1787050800}).startswith("2026-08-1")
    assert metar._observed_at({"obsTime": "bad"}) is None
    assert metar._observed_at({}) is None


async def test_oversized_metar_responses_are_unusable_answers(monkeypatch):
    """A body over the limit is handled like a failed request, never a crash."""
    monkeypatch.setattr(http_limits, "MAX_JSON_RESPONSE_BYTES", 10)
    routes = {"stationinfo": load_json("metar_stationinfo.json"), "/metar": load_json("metar_reports.json")}

    # the report of an aerodrome is optional: no observation, no exception
    _, patcher = _patch_session(routes)
    with patcher:
        assert await metar.async_fetch_observation(None, "LIPZ") is None

    # the "which aerodromes are reporting" lookup falls back to "all of them"
    _, patcher = _patch_session(routes)
    with patcher:
        assert await metar._async_reporting_icaos(None, ["LIPZ", "LIPU"]) == {"LIPZ", "LIPU"}

    # the list of aerodromes is needed by the config flow: the error reaches it
    _, patcher = _patch_session(routes)
    with patcher, pytest.raises(http_limits.ResponseTooLargeError):
        await metar.async_fetch_stations(None, 45.4, 11.9, _distance)

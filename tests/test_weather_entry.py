# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""A weather location end to end: coordinator, weather entity, sensors and services.

The ARPAV and METAR endpoints are served from recorded payloads under
``tests/fixtures`` (no network): timestamps are shifted to the present because
the integration compares them with the clock.
"""

import copy
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

import aiohttp  # noqa: E402
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402
from homeassistant.setup import async_setup_component  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.arpav_meteo_idro import coordinator as coord  # noqa: E402
from custom_components.arpav_meteo_idro import const, metar  # noqa: E402
from custom_components.arpav_meteo_idro.const import DOMAIN  # noqa: E402
from custom_components.arpav_meteo_idro.provenance import Provenance  # noqa: E402
from custom_components.arpav_meteo_idro.thresholds import DayThresholds, NightThresholds  # noqa: E402

from .helpers import FakeSession, load_json  # noqa: E402

FMT = "%Y-%m-%dT%H:%M:%S"
STATION = "s1"
UNIQUE_WEATHER = "weather.arpav_c1_s1"


def _arpav_now():
    """Return the current time as ARPAV writes it: fixed UTC+1, no offset."""
    return (datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None, microsecond=0)


def _shifted(payload, field, newest):
    """Return a copy of a recorded payload whose newest ``field`` is ``newest``."""
    payload = copy.deepcopy(payload)
    items = payload["data"]
    stamps = {}
    for index, item in enumerate(items):
        try:
            stamps[index] = datetime.strptime(item[field], FMT)
        except (KeyError, ValueError):
            continue
    delta = newest - max(stamps.values())
    for index, stamp in stamps.items():
        items[index][field] = (stamp + delta).strftime(FMT)
    return payload


def _forecast_payload():
    payload = load_json("arpav_forecast.json")
    today = datetime.now().date()
    for entry, offset in zip(payload["data"], (0, 0, 1, 2), strict=True):
        entry["scadenza"] = str(today + timedelta(days=offset))
    return payload


def _air_quality_payload():
    stamp = _arpav_now().strftime(FMT)
    return {"data": [
        {"PARAMETRO": "PM10", "DATA_ORA": stamp, "MEDIA": 22, "STAZIONE": "Mandria", "DATA": stamp},
        {"PARAMETRO": "PM10", "DATA_ORA": "2020-01-01T00:00:00", "MEDIA": 99, "STAZIONE": "Mandria"},
        {"PARAMETRO": "PM2.5", "DATA_ORA": stamp, "MEDIA": 12, "STAZIONE": "Mandria", "DATA": stamp},
        {"PARAMETRO": "O3", "DATA_ORA": stamp, "MEDIA": 80, "STAZIONE": "Mandria", "DATA": stamp},
        {"PARAMETRO": "NO2", "DATA_ORA": stamp, "MEDIA": 5, "STAZIONE": "Mandria"},
    ]}


def _metar_payload():
    reports = load_json("metar_reports.json")[:1]
    reports[0]["reportTime"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return reports


def _routes():
    now = _arpav_now()
    return {
        "meteo_meteogrammi_tabella": _shifted(load_json("arpav_meteogrammi_tabella.json"), "dataora",
                                             now - timedelta(minutes=5)),
        "bollettini_meteo_simboli_en": _forecast_payload(),
        "aria_valori_orari": _air_quality_payload(),
        "meteo_meteogrammi?rete=MGRAMMIBRI": load_json("arpav_brightness_network.json"),
        # the shared fixture also holds malformed rows, which sort after valid timestamps
        "meteo_brillanza_tabella?codseqst=902": {"data": [
            {"dataora": (now - timedelta(hours=1)).strftime(FMT), "valore": "21.0"},
            {"dataora": (now - timedelta(hours=2)).strftime(FMT), "valore": "20.0"}]},
        "meteo_brillanza_tabella": {"data": []},
        "aviationweather.gov": _metar_payload(),
    }


@pytest.fixture
def api():
    """Serve the recorded ARPAV and METAR payloads to every aiohttp session."""
    session = FakeSession(_routes())
    with patch.object(aiohttp, "ClientSession", lambda *a, **k: session):
        yield session


def _entry(options=None):
    return MockConfigEntry(
        domain=DOMAIN,
        data={"comune_name": "Padova (Pd)", "comune_id": "c1", "zone_id": 13, "zone_name": "Pianura",
              "station_name": "Legnaro", "station_id": STATION,
              "station_latitude": 45.34, "station_longitude": 11.95},
        options=options or {},
    )


async def _setup(hass, api, options=None):
    entry = _entry(options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity_id(hass, domain, unique_id):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


async def test_setup_exposes_weather_and_sensors(enable_custom_integrations, hass, api):
    """Station readings feed the weather entity and one sensor per type."""
    entry = await _setup(hass, api)

    weather = hass.states.get(_entity_id(hass, "weather", UNIQUE_WEATHER))
    assert weather.state == "rainy"  # precipitation overrides everything
    attrs = weather.attributes
    assert attrs["temperature"] == 30.5
    assert attrs["humidity"] == 55
    assert attrs["pressure"] == 1013.2
    assert attrs["wind_speed"] == 9.0
    assert attrs["wind_bearing"] == "E"
    assert attrs["visibility"] == 9.0
    assert attrs["uv_index"] == 2
    assert attrs["condition_source_rule"] == "precipitation"
    assert attrs["forecast_today_description"] in {"Poco nuvoloso", "Rovesci", "Sereno", "?"}
    assert "METAR" not in attrs["attribution"]

    sensor = hass.states.get(_entity_id(hass, "sensor", f"arpav_temperature_{STATION}"))
    assert sensor.state == "30.5"
    assert sensor.attributes["station_id"] == STATION
    assert sensor.attributes["source"] == "station"
    hourly = hass.states.get(_entity_id(hass, "sensor", f"arpav_precipitation_hourly_{STATION}"))
    assert float(hourly.state) == 2.4
    cumulative = hass.states.get(_entity_id(hass, "sensor", f"arpav_precipitation_cumulative_1h_{STATION}"))
    assert float(cumulative.state) == 0.6
    day = hass.states.get(_entity_id(hass, "sensor", f"arpav_precipitation_cumulative_24h_{STATION}"))
    assert float(day.state) == 1.6
    probability = hass.states.get(_entity_id(hass, "sensor", f"arpav_precipitation_probability_{STATION}"))
    assert probability.attributes["source"] == "forecast"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_weather_forecasts(enable_custom_integrations, hass, api):
    """Daily forecasts merge the half-days, twice daily ones are passed through."""
    entry = await _setup(hass, api)
    entity_id = _entity_id(hass, "weather", UNIQUE_WEATHER)

    async def forecasts(kind):
        response = await hass.services.async_call(
            "weather", "get_forecasts", {"entity_id": entity_id, "type": kind},
            blocking=True, return_response=True)
        return response[entity_id]["forecast"]

    daily = await forecasts("daily")
    assert len(daily) == 3
    assert daily[0]["temperature"] >= 30
    assert daily[0]["templow"] <= 18
    assert daily[1]["temperature"] == 31
    assert "templow" not in daily[1]
    assert daily[2].get("condition") is None

    twice = await forecasts("twice_daily")
    assert len(twice) == 2
    assert {f["is_daytime"] for f in twice} == {True, False}

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_optional_attributes_air_quality_and_metar(enable_custom_integrations, hass, api):
    """Raw data, air quality and an aerodrome are exposed when configured."""
    entry = await _setup(hass, api, {
        const.CONF_EXPOSE_FORECAST_JSON: True,
        const.CONF_EXPOSE_FORECAST_RAW: True,
        const.CONF_EXPOSE_SENSORS_RAW: True,
        const.CONF_AIR_QUALITY: {const.CONF_PM10_STATION: "1", const.CONF_PM25_STATION: "2",
                                 const.CONF_OZONE_STATION: "3"},
        const.CONF_OBSERVATIONS: {const.CONF_METAR_STATION: "LIPZ"},
    })

    attrs = hass.states.get(_entity_id(hass, "weather", UNIQUE_WEATHER)).attributes
    assert "METAR by NOAA" in attrs["attribution"]
    assert attrs["cloud_coverage"] == 50
    assert json.loads(attrs["forecast"])
    assert json.loads(attrs["raw_forecast"])["data"]
    assert attrs["raw_TARIA"]
    assert "ghi" in attrs
    assert len(attrs["sensors_raw"]) >= 9

    for key, expected in (("pm10", "22"), ("pm25", "12"), ("ozone", "80")):
        state = hass.states.get(_entity_id(hass, "sensor", f"arpav_{key}_{STATION}"))
        assert state.state == expected
        assert state.attributes["source"] == "air_quality_station"

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("infer", [
    const.CONF_INFER_CONDITION_FROM_SENSORS_WITH_CUSTOM_THRESHOLDS,
    const.CONF_INFER_CONDITION_DISABLED,
])
async def test_infer_condition_modes(enable_custom_integrations, hass, api, infer):
    """Custom thresholds are used; a disabled inference leaves the condition unset."""
    entry = await _setup(hass, api, {
        const.CONF_INFER_CONDITION: infer, const.CONF_INFER_CONDITION_DAY_CLEAR_THRESHOLD: 0.9,
        const.CONF_ARCHIVE_BRIGHTNESS: True,
    })
    data = entry.runtime_data.coordinator.data
    if infer == const.CONF_INFER_CONDITION_DISABLED:
        assert "condition" not in data["sensors"]
    else:
        assert data["sensors"]["condition"] == "rainy"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_services(enable_custom_integrations, hass, api):
    """refresh_data, archive_brightness and their validation."""
    assert await async_setup_component(hass, "homeassistant", {})
    entry = await _setup(hass, api)

    await hass.services.async_call(DOMAIN, "refresh_data", {}, blocking=True)
    await hass.services.async_call(DOMAIN, "refresh_data", {"entry_id": entry.entry_id}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "refresh_data", {"entry_id": "nope"}, blocking=True)

    # no recorder in this test: nothing to import, but the call goes through
    await hass.services.async_call(DOMAIN, "archive_brightness", {"entry_id": entry.entry_id}, blocking=True)
    with (
        patch("custom_components.arpav_meteo_idro.async_archive_brightness",
              AsyncMock(side_effect=aiohttp.ClientError("down"))),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(DOMAIN, "archive_brightness", {}, blocking=True)

    # the entity can also be refreshed explicitly
    await hass.services.async_call(
        "homeassistant", "update_entity",
        {"entity_id": _entity_id(hass, "sensor", f"arpav_humidity_{STATION}")}, blocking=True)

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_station_fetch_is_an_update_failure(enable_custom_integrations, hass, api):
    """A non-200 answer is reported as UpdateFailed, by every endpoint."""
    entry = await _setup(hass, api)
    coordinator = entry.runtime_data.coordinator

    for key, call in (
        ("meteo_meteogrammi_tabella", lambda: coordinator.fetch_station_data(STATION)),
        ("aria_valori_orari", lambda: coordinator.fetch_air_quality_data("1", "PM10")),
        ("bollettini_meteo_simboli_en", lambda: coord._fetch_forecast_data(13)),
        ("meteo_meteogrammi?rete=MGRAMMIBRI", lambda: coordinator.get_night_sky_brightness(45.3, 11.9)),
        ("meteo_brillanza_tabella?codseqst=902", lambda: coordinator._fetch_station_brightness("902")),
    ):
        original = api.routes[key]
        api.routes[key] = ({}, 500)
        with pytest.raises(UpdateFailed):
            await call()
        api.routes[key] = original

    assert await hass.config_entries.async_unload(entry.entry_id)


# --- sky classification ----------------------------------------------------

DAY = datetime(2026, 8, 18, 12, 0, tzinfo=coord.timezone(timedelta(hours=1)))
NIGHT = datetime(2026, 8, 18, 1, 0, tzinfo=coord.timezone(timedelta(hours=1)))
LAT, LON = 45.34, 11.95


@pytest.fixture
async def coordinator(enable_custom_integrations, hass, api):
    """Load a coordinator, to call the classification directly."""
    entry = await _setup(hass, api)
    yield entry.runtime_data.coordinator
    await hass.config_entries.async_unload(entry.entry_id)


async def _classify(coordinator, dt, sensors, **kwargs):
    return await coordinator.classify_sky(
        LAT, LON, dt, sensors, DayThresholds(), NightThresholds(), **kwargs)


@pytest.mark.parametrize(("sensors", "expected", "rule"), [
    ({"precipitation": 1, "temperature": -1}, "snowy", "precipitation"),
    ({"precipitation": 1, "temperature": 3}, "snowy-rainy", "precipitation"),
    ({"precipitation": 25, "temperature": 15}, "pouring", "precipitation"),
    ({"precipitation": 1, "temperature": 15}, "rainy", "precipitation"),
    ({"precipitation": 1}, "rainy", "precipitation"),
    ({"visibility": 0.5}, "fog", "visibility"),
    ({"visibility": 1.5, "humidity": 100}, "fog", "visibility"),
    ({"wind_speed": 45}, "windy", "wind"),
])
async def test_classify_overrides(coordinator, sensors, expected, rule):
    """Precipitation, visibility and wind override the sky."""
    condition, provenance = await _classify(coordinator, DAY, sensors)
    assert condition == expected
    assert provenance.rule == rule
    assert provenance.name is None or isinstance(provenance.name, str)


async def test_classify_override_uses_provenance_of_the_value(coordinator):
    """The value that decided keeps its own source."""
    sources = {"wind_speed": Provenance(source="metar", name="METAR X")}
    condition, provenance = await _classify(coordinator, DAY, {"wind_speed": 45}, sources=sources)
    assert (condition, provenance.source, provenance.name, provenance.rule) == ("windy", "metar", "METAR X", "wind")


@pytest.mark.parametrize(("ghi", "expected"), [(950, "sunny"), (550, "partlycloudy"), (100, "cloudy")])
async def test_classify_day_from_radiation(coordinator, ghi, expected):
    """The share of the clear-sky irradiance decides the day sky."""
    coordinator.day_condition = const.CONF_DAY_CONDITION_RADIATION
    condition, provenance = await _classify(coordinator, DAY, {"ghi": ghi})
    assert condition == expected
    assert provenance.rule == "solar_radiation"


async def test_classify_day_without_radiation_is_unknown(coordinator):
    """No pyranometer, no observed condition."""
    condition, provenance = await _classify(coordinator, DAY, {})
    assert (condition, provenance.source) == ("unknown", "unknown")


FORECAST = [
    {"datetime": datetime(2026, 8, 18, 8), "type": "twice_daily", "condition": "sunny"},
    {"datetime": datetime(2026, 8, 18, 17), "type": "twice_daily", "condition": "cloudy"},
    {"datetime": datetime(2026, 8, 18, 12), "type": "daily", "condition": "rainy"},
    {"datetime": datetime(2026, 8, 18, 12), "type": "daily", "condition": None},
]
OBSERVATION = metar.MetarObservation("LIPZ", observed_at="2026-08-18T10:00:00+00:00", cloud_coverage=100)


@pytest.mark.parametrize(("mode", "ghi", "observation", "expected", "source"), [
    (const.CONF_DAY_CONDITION_UNKNOWN, 900, OBSERVATION, "unknown", "unknown"),
    (const.CONF_DAY_CONDITION_FORECAST, 900, OBSERVATION, "sunny", "forecast"),
    (const.CONF_DAY_CONDITION_METAR, None, OBSERVATION, "cloudy", "metar"),
    (const.CONF_DAY_CONDITION_METAR, None, None, "sunny", "forecast"),
    (const.CONF_DAY_CONDITION_RADIATION_OR_METAR, 950, OBSERVATION, "sunny", "station"),
    (const.CONF_DAY_CONDITION_RADIATION_OR_METAR, None, OBSERVATION, "cloudy", "metar"),
    (const.CONF_DAY_CONDITION_RADIATION_OR_METAR, None, None, "unknown", "unknown"),
])
async def test_classify_day_modes(coordinator, mode, ghi, observation, expected, source):
    """Each day mode, with its fallbacks."""
    coordinator.day_condition = mode
    sensors = {} if ghi is None else {"ghi": ghi}
    with patch.object(coordinator, "async_metar_observation", AsyncMock(return_value=observation)):
        condition, provenance = await _classify(coordinator, DAY, sensors, forecast=FORECAST)
    assert (condition, provenance.source) == (expected, source)


@pytest.mark.parametrize(("mode", "brightness", "observation", "expected", "source"), [
    (const.CONF_NIGHT_CONDITION_UNKNOWN, 21, None, "unknown", "unknown"),
    (const.CONF_NIGHT_CONDITION_FORECAST, 21, None, "clear-night", "forecast"),
    (const.CONF_NIGHT_CONDITION_METAR, 21, OBSERVATION, "cloudy", "metar"),
    (const.CONF_NIGHT_CONDITION_METAR, 21, None, "clear-night", "forecast"),
    (const.CONF_NIGHT_CONDITION_BRIGHTNESS, 25, None, "clear-night", "sky_brightness_station"),
    (const.CONF_NIGHT_CONDITION_BRIGHTNESS, 19.5, None, "partlycloudy", "sky_brightness_station"),
    (const.CONF_NIGHT_CONDITION_BRIGHTNESS, 15, None, "cloudy", "sky_brightness_station"),
    (const.CONF_NIGHT_CONDITION_BRIGHTNESS, None, None, "unknown", "unknown"),
    (const.CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST, None, None, "clear-night", "forecast"),
    (const.CONF_NIGHT_CONDITION_BRIGHTNESS_OR_FORECAST, 25, None, "clear-night", "sky_brightness_station"),
])
async def test_classify_night_modes(coordinator, mode, brightness, observation, expected, source):
    """Each night mode, with its fallbacks."""
    coordinator.night_condition = mode
    reading = None if brightness is None else coord.SkyBrightnessReading(brightness, "Padova", "2026-08-18T01:00:00+01:00")
    with (
        patch.object(coordinator, "async_metar_observation", AsyncMock(return_value=observation)),
        patch.object(coordinator, "get_night_sky_brightness", AsyncMock(return_value=reading)),
        patch.object(coord, "moon_illumination", lambda _dt: 0),  # no moon offset
    ):
        condition, provenance = await _classify(coordinator, NIGHT, {}, forecast=FORECAST)
    assert (condition, provenance.source) == (expected, source)


async def test_forecast_condition_without_forecast_is_unknown(coordinator):
    """No bulletin, no condition."""
    condition, provenance = coordinator._forecast_condition(DAY, None)
    assert (condition, provenance.source) == ("unknown", "unknown")
    assert coordinator._nearest_forecast(DAY, [{"condition": None}]) is None


async def test_night_sky_brightness_reading(coordinator):
    """The nearest station with a usable, recent reading wins; station names come from the network."""
    reading = await coordinator.get_night_sky_brightness(LAT, LON)
    assert reading.station_name == "Good Station"
    assert reading.value == 21.0
    assert reading.observed_at.endswith("+01:00")


@pytest.mark.parametrize("readings", [
    {"data": []},
    {"data": [{"dataora": "2020-01-01T00:00:00", "valore": "21"}]},  # too old
    {"data": [{"dataora": "bad", "valore": "21"}]},
    {"data": [{"dataora": "2999-01-01T00:00:00", "valore": "nope"}]},
    {"data": [{"dataora": "2999-01-01T00:00:00", "valore": "0"}]},
])
async def test_station_brightness_unusable_readings(coordinator, readings, api):
    """No data, stale, malformed or zero readings are not usable."""
    api.routes["meteo_brillanza_tabella?codseqst=902"] = readings
    assert await coordinator._fetch_station_brightness("902") is None
    assert await coordinator._fetch_station_brightness(None) is None


async def test_no_usable_brightness_anywhere(coordinator, api):
    """When no nearby station has a reading the answer is None."""
    api.routes["meteo_brillanza_tabella?codseqst=902"] = {"data": []}
    assert await coordinator.get_night_sky_brightness(LAT, LON) is None


async def test_metar_observation_is_cached_and_expires(coordinator):
    """No station, no report; fetched reports are reused for a while and dropped when stale."""
    coordinator.metar_station = None
    assert await coordinator.async_metar_observation() is None

    coordinator.metar_station = "LIPZ"
    fresh = metar.MetarObservation("LIPZ", observed_at=datetime.now(UTC).isoformat(), cloud_coverage=0)
    with patch.object(metar, "async_fetch_observation", AsyncMock(return_value=fresh)) as fetch:
        assert await coordinator.async_metar_observation() is fresh
        assert await coordinator.async_metar_observation() is fresh
        assert fetch.await_count == 1  # the second call is within the minimum interval

        coordinator._metar_fetched_at = datetime.now(UTC) - timedelta(hours=1)
        fetch.return_value = None  # the aerodrome stopped answering: keep the last report
        assert await coordinator.async_metar_observation() is fresh

        coordinator._metar_observation = metar.MetarObservation(
            "LIPZ", observed_at=(datetime.now(UTC) - timedelta(hours=5)).isoformat())
        assert await coordinator.async_metar_observation() is None


# --- helpers ---------------------------------------------------------------

def test_values_from_observation():
    """Every ARPAV measurement type maps to the sensor values it feeds."""
    f = coord._values_from_observation
    assert f({"tipo": "TARIA_2", "valore": "3.5"}) == {"temperature": 3.5}
    assert f({"tipo": "UMID", "valore": "55"}) == {"humidity": 55}
    assert f({"tipo": "VISIB", "valore": "1500"}) == {"visibility": 1.5}
    assert f({"tipo": "PRESS", "valore": "1000"}) == {"pressure": 1000.0}
    assert f({"tipo": "PREC", "valore": "0.4"}) == {"precipitation": 0.4}
    assert f({"tipo": "DVENTO", "valore": "180"})["wind_bearing"] == "S"
    assert f({"tipo": "VVENTO", "valore": "10"}) == {"wind_speed": 36.0}
    assert f({"tipo": "BFOGL", "valore": "7"}) == {"leaf_wetness": 7.0}
    assert f({"tipo": "RADSOL", "valore": "0.9", "unitnm": "MJ/m2"}) == {"uv_index": 2, "ghi": 250}
    assert f({"tipo": "RADSOL", "valore": "500", "unitnm": "w/m2"}) == {"uv_index": 1, "ghi": 500}
    assert f({"tipo": "RADSOL", "valore": "500", "unitnm": "kWh"}) == {}
    assert f({"tipo": "XYZ", "valore": "1"}) == {}
    assert f({"tipo": "TARIA", "valore": None}) == {}
    assert f({"valore": "1"}) == {}


def test_fill_missing_values_only_fills_gaps():
    """An aerodrome completes the station data, never overrides it."""
    sensors = {"temperature": 20.0, "pressure": None}
    sources = {}
    observation = metar.MetarObservation(
        "LIPZ", observed_at="t", values={"temperature": 25.0, "pressure": 1010.0, "visibility": None})
    coord._fill_missing_values(sensors, sources, observation)
    assert sensors == {"temperature": 20.0, "pressure": 1010.0}
    assert sources["pressure"].source == "metar"
    assert "temperature" not in sources


def test_measured_temperature_extremes():
    """Extremes are those of the last day reported; unreadable values are skipped."""
    items = [
        {"dataora": "2026-08-17T10:00:00", "valore": "40"},
        {"dataora": "2026-08-18T05:00:00", "valore": "17.2"},
        {"dataora": "2026-08-18T14:00:00", "valore": "30.5"},
        {"dataora": "2026-08-18T15:00:00", "valore": "bad"},
        {"dataora": None, "valore": "1"},
    ]
    assert coord._measured_temperature_extremes(items) == {"date": "2026-08-18", "min": 17.2, "max": 30.5}
    assert coord._measured_temperature_extremes([]) is None
    assert coord._measured_temperature_extremes([{"dataora": "2026-08-18T05:00:00", "valore": None}]) is None


def test_arpav_isoformat():
    """ARPAV times get their fixed offset; garbage is returned unchanged."""
    assert coord._arpav_isoformat("2026-08-18T14:00:00") == "2026-08-18T14:00:00+01:00"
    assert coord._arpav_isoformat(None) is None
    assert coord._arpav_isoformat("bad") == "bad"


def test_cumulate_since():
    """Only the data points after the limit are summed."""
    data = [{"dataora": "2026-08-18T14:00:00", "valore": "0.2"},
            {"dataora": "2026-08-18T10:00:00", "valore": "1.0"}]
    since = datetime(2026, 8, 18, 12, 0, tzinfo=coord.timezone(timedelta(hours=1)))
    assert coord._cumulate_since(data, since) == 0.2


def test_geometry_and_astronomy():
    """Distances and moon illumination are sane."""
    assert coord.haversine(45.0, 11.0, 45.0, 11.0) == 0
    assert coord.haversine(45.0, 11.0, 46.0, 11.0) == pytest.approx(111.2, abs=0.5)
    places = [{"latitudine": 46.0, "longitudine": 11.0, "n": "far"},
              {"latitudine": 45.1, "longitudine": 11.0, "n": "near"}]
    assert coord.find_nearest_location(places, 45.0, 11.0)["n"] == "near"
    assert [p["n"] for p in coord.sort_locations_by_distance(places, 45.0, 11.0)] == ["near", "far"]
    assert coord.mj_to_wm2(3.6) == 1000
    assert 0 <= coord.moon_illumination(DAY) <= 100
    assert coord.moon_illumination(datetime(2026, 8, 28, tzinfo=UTC)) > 90  # full moon, 28 Aug 2026
    assert coord.moon_illumination(datetime(2026, 8, 12, tzinfo=UTC)) < 5  # new moon, 12 Aug 2026


def test_forecast_helpers():
    """Forecast bulletin fields are parsed defensively."""
    assert coord._get_forecast_condition("b6.png") == "pouring"
    assert coord._get_forecast_condition("a1") == "sunny"
    assert coord._get_forecast_condition("nope") is None
    assert coord._get_forecast_temperature_dict({"temperatura": "10/20"}) == {
        "native_templow": 10.0, "native_temperature": 20.0}
    assert coord._get_forecast_temperature_dict({"temperatura": "15"}) == {"native_temperature": 15.0}
    assert coord._get_forecast_temperature_dict({"temperatura": ""}) == {"tempmiss": True}
    assert coord._parse_precipitation_prob("") is None
    assert coord._parse_precipitation_prob("40%") == 40
    assert coord._get_forecast_type("") == "daily"
    assert coord._get_forecast_type("night/morning") == "twice_daily"
    assert coord._get_forecast_type("other") is None
    assert coord._get_forecast_daytime_dict("") == {"is_daytime": True}
    assert coord._get_forecast_daytime_dict("night/morning") == {"is_daytime": False}
    assert coord._get_forecast_datetime("2026-08-18", "afternoon/evening").hour == 16
    assert coord._get_forecast_datetime("2026-08-18", "").hour == 12
    with pytest.raises(ValueError):
        coord._get_forecast_datetime("2026-08-18", "weekend")

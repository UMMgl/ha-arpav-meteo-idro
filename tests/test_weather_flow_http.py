# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Weather config flow over the Home Assistant shared session (quality: inject-websession).

The ARPAV and METAR endpoints are served by ``aioclient_mock``: the helpers and the
flows must read through the session that Home Assistant owns, without ever closing it.
"""

import re
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

import aiohttp  # noqa: E402
from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers.aiohttp_client import async_get_clientsession  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402
from yarl import URL  # noqa: E402
from custom_components.arpav_meteo_idro import config_flow as flow  # noqa: E402
from custom_components.arpav_meteo_idro.const import (  # noqa: E402
    API_BASE,
    CONF_AIR_QUALITY,
    CONF_INFER_CONDITION,
    CONF_INFER_CONDITION_FROM_SENSORS,
    CONF_METAR_STATION,
    CONF_OBSERVATIONS,
    DOMAIN,
)

from .helpers import load_json  # noqa: E402

ZONE_NAMES_URL = re.compile(re.escape(f"{API_BASE}/bollettini_meteo_simboli_en"))
COMUNI_URL = re.compile(re.escape(f"{API_BASE}/meteo_comuni"))
STATIONS_URL = re.compile(re.escape(f"{API_BASE}/meteo_meteogrammi"))
AIR_URL = re.compile(re.escape(f"{API_BASE}/aria_elenco_stazioni"))
STATIONINFO_URL = re.compile(r"https://aviationweather\.gov/api/data/stationinfo")
METAR_URL = re.compile(r"https://aviationweather\.gov/api/data/metar")

ZONE_NAMES = {"data": [
    {"zonaid": 2, "zona": "Pedemontana"},
    {"zonaid": 1, "zona": "Pianura centrale"},
    {"zonaid": 1, "zona": "Pianura centrale (duplicate)"},
]}
COMUNI = {"data": [
    {"id": "c2", "comune": "Vicenza", "provincia": "VICENZA", "zonaid": 2},
    {"id": "c1", "comune": "Padova", "provincia": "PADOVA", "zonaid": 1},
]}
STATIONS = {"data": [
    {"codseqst": "s2", "nome_stazione": "Valdagno", "provincia": "VICENZA", "latitudine": 45.64, "longitudine": 11.3},
    {"codseqst": "s1", "nome_stazione": "Legnaro", "provincia": "PADOVA", "latitudine": 45.34, "longitudine": 11.95},
]}
AIR = {"data": [
    {"CODSEQST": "a2", "NOME_STAZIONE": "Mandria", "RETE": "Urbana"},
    {"CODSEQST": "a1", "NOME_STAZIONE": "Arcella", "RETE": "Urbana"},
]}


def _serve(mock, skip=()):
    """Serve the lists the weather flow reads, but the ones in ``skip`` (the first mock wins)."""
    routes = {
        ZONE_NAMES_URL: ZONE_NAMES,
        COMUNI_URL: COMUNI,
        STATIONS_URL: STATIONS,
        AIR_URL: AIR,
        STATIONINFO_URL: load_json("metar_stationinfo.json"),
        METAR_URL: [r for r in load_json("metar_reports.json") if r["icaoId"] == "LIPZ"],
    }
    for url, payload in routes.items():
        if url not in skip:
            mock.get(url, json=payload)
    return mock


@pytest.fixture
def arpav(aioclient_mock):
    """Serve the ARPAV lists the weather flow reads."""
    return _serve(aioclient_mock)


# --- helpers ---------------------------------------------------------------

async def test_helpers_parse_the_arpav_lists(hass, arpav):
    """Each helper reads its endpoint through the shared session and sorts the result."""
    assert await flow.fetch_zone_names(hass) == {1: "Pianura centrale", 2: "Pedemontana"}

    names, to_zone, zones = await flow.fetch_zones(hass)
    assert names == {"c1": "Padova (Padova)", "c2": "Vicenza (Vicenza)"}
    assert to_zone == {"c1": 1, "c2": 2}
    assert zones == {2: "Zona 2", 1: "Zona 1"}

    names, stations = await flow.fetch_stations(hass)
    assert names == {"s1": "Legnaro (Padova)", "s2": "Valdagno (Vicenza)"}
    assert stations["s1"]["latitudine"] == 45.34

    names, stations = await flow.fetch_stations_air(hass, "25")
    assert names == {"a1": "Arcella - Urbana", "a2": "Mandria - Urbana"}
    assert set(stations) == {"a1", "a2"}
    assert any(URL(str(call[1])).query.get("cod_parametro") == "25" for call in arpav.mock_calls)


async def test_helpers_leave_the_shared_session_open(hass, arpav):
    """The session belongs to Home Assistant: the helpers must never close it."""
    session = async_get_clientsession(hass)

    await flow.fetch_zone_names(hass)
    await flow.fetch_zones(hass)
    await flow.fetch_stations(hass)
    await flow.fetch_stations_air(hass, "7")

    assert not session.closed
    assert async_get_clientsession(hass) is session


@pytest.mark.parametrize("helper", [
    lambda hass: flow.fetch_zone_names(hass),
    lambda hass: flow.fetch_zones(hass),
    lambda hass: flow.fetch_stations(hass),
    lambda hass: flow.fetch_stations_air(hass, "7"),
])
async def test_helpers_raise_on_http_errors(hass, aioclient_mock, helper):
    """An error status is raised, for the flow to turn into cannot_connect."""
    aioclient_mock.get(re.compile(re.escape(API_BASE)), status=500)
    with pytest.raises(aiohttp.ClientResponseError):
        await helper(hass)


async def test_helpers_raise_on_network_errors(hass, aioclient_mock):
    """A network failure propagates as an aiohttp error."""
    aioclient_mock.get(re.compile(re.escape(API_BASE)), exc=aiohttp.ClientError("down"))
    with pytest.raises(aiohttp.ClientError):
        await flow.fetch_stations(hass)


# --- config flow, end to end over the mocked endpoints ---------------------

async def test_weather_flow_end_to_end(enable_custom_integrations, hass, arpav):
    """Municipality → zone → station, reading everything over aioclient_mock."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "weather"})
    assert result["step_id"] == "weather"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1"})
    assert result["step_id"] == "zone"
    assert result["description_placeholders"] == {"selected_comune": "Padova (Padova)"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1", "zone_id": 1})
    assert result["step_id"] == "station"

    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station_id": "s1"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["zone_name"] == "Pianura centrale"
    assert result["data"]["station_longitude"] == 11.95
    assert result["result"].unique_id == "1_s1"


@pytest.mark.parametrize("failure", [{"status": 503}, {"exc": aiohttp.ClientError("down")}, {"exc": TimeoutError()}])
async def test_weather_flow_aborts_on_network_errors(enable_custom_integrations, hass, aioclient_mock, failure):
    """No answer from ARPAV: the flow aborts with cannot_connect and creates nothing."""
    aioclient_mock.get(COMUNI_URL, **failure)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "weather"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_weather_flow_aborts_on_unexpected_payload(enable_custom_integrations, hass, aioclient_mock):
    """A list without the expected keys is treated like an unreachable service."""
    aioclient_mock.get(COMUNI_URL, json={"data": [{"unexpected": True}]})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "weather"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_weather_flow_aborts_when_zone_names_fail(enable_custom_integrations, hass, aioclient_mock):
    """The zone names are read after the municipality is chosen: a failure there aborts too."""
    _serve(aioclient_mock, skip=(ZONE_NAMES_URL,))
    aioclient_mock.get(ZONE_NAMES_URL, status=500)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "weather"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


# --- options flow ----------------------------------------------------------

ANSWERS = {CONF_INFER_CONDITION: CONF_INFER_CONDITION_FROM_SENSORS, CONF_OBSERVATIONS: {}, CONF_AIR_QUALITY: {}}


def _entry(hass, *, coordinates=True, options=None):
    data = {"comune_id": "c1", "comune_name": "Padova (Pd)", "zone_id": 1, "zone_name": "Pianura centrale",
            "station_id": "s1", "station_name": "Legnaro (Pd)"}
    if coordinates:
        data |= {"station_latitude": 45.34, "station_longitude": 11.95}
    entry = MockConfigEntry(domain=DOMAIN, unique_id="1_s1", data=data, options=options or {})
    entry.add_to_hass(hass)
    return entry


async def test_options_list_air_and_metar_stations(enable_custom_integrations, hass, arpav):
    """The form offers the air quality stations and the aerodromes read over the session."""
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], ANSWERS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert any(URL(str(call[1])).host == "aviationweather.gov" for call in arpav.mock_calls)
    assert sum(URL(str(call[1])).path.endswith("/aria_elenco_stazioni") for call in arpav.mock_calls) == 3


async def test_options_keep_a_configured_aerodrome_selectable(enable_custom_integrations, hass, arpav):
    """The saved aerodrome stays in the list when the lookup no longer returns it."""
    entry = _entry(hass, options={CONF_OBSERVATIONS: {CONF_METAR_STATION: "LIXX"}})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    metar_field = result["data_schema"].schema[CONF_OBSERVATIONS].schema.schema[CONF_METAR_STATION]
    assert "LIXX" in metar_field.container


async def test_options_survive_a_metar_failure(enable_custom_integrations, hass, aioclient_mock):
    """The METAR list is optional: a failure leaves only the "None" choice."""
    _serve(aioclient_mock, skip=(STATIONINFO_URL,))
    aioclient_mock.get(STATIONINFO_URL, exc=aiohttp.ClientError("down"))
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    metar_field = result["data_schema"].schema[CONF_OBSERVATIONS].schema.schema[CONF_METAR_STATION]
    assert list(metar_field.container) == ["None"]


async def test_options_without_usable_coordinates_skip_metar(enable_custom_integrations, hass, aioclient_mock):
    """No coordinates, or unreadable ones, mean no aerodrome lookup at all."""
    arpav = _serve(aioclient_mock, skip=(STATIONS_URL,))
    entry = _entry(hass, coordinates=False)
    arpav.get(STATIONS_URL, json={"data": [{"codseqst": "s1", "nome_stazione": "Legnaro", "provincia": "PD"}]})

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    entry = MockConfigEntry(domain=DOMAIN, unique_id="1_s9", data={
        "station_id": "s9", "station_latitude": "north", "station_longitude": "east"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert not any(URL(str(call[1])).path.endswith("/stationinfo") for call in arpav.mock_calls)


async def test_options_fill_in_missing_coordinates(enable_custom_integrations, hass, arpav):
    """Entries created before the coordinates were stored get them from ARPAV on save."""
    entry = _entry(hass, coordinates=False)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(result["flow_id"], ANSWERS)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["station_latitude"] == 45.34
    assert entry.data["station_longitude"] == 11.95


async def test_options_network_error_aborts(enable_custom_integrations, hass, aioclient_mock):
    """Air quality lists that cannot be read abort the options flow."""
    aioclient_mock.get(AIR_URL, exc=aiohttp.ClientError("down"))
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

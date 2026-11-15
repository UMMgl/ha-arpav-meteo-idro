# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Config and options flow tests of a weather location (quality: config-flow-test-coverage)."""

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

import aiohttp  # noqa: E402
from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.arpav_meteo_idro.const import (  # noqa: E402
    CONF_AIR_QUALITY,
    CONF_INFER_CONDITION,
    CONF_INFER_CONDITION_FROM_SENSORS,
    CONF_INFER_CONDITION_FROM_SENSORS_WITH_CUSTOM_THRESHOLDS,
    CONF_OBSERVATIONS,
    DOMAIN,
)

FLOW = "custom_components.arpav_meteo_idro.config_flow"
COMUNI = ({"c1": "Padova (Pd)", "c2": "Vicenza (Vi)"}, {"c1": "z1", "c2": "z2"}, {"z1": "Zona z1", "z2": "Zona z2"})
ZONES = {"z1": "Pianura centrale", "z2": "Pedemontana"}
STATIONS = ({"s1": "Legnaro (Pd)"}, {"s1": {"codseqst": "s1", "latitudine": 45.34, "longitudine": 11.95}})


@pytest.fixture
def arpav_lists():
    """Mock the ARPAV lists used by the weather flow."""
    with (
        patch(f"{FLOW}.fetch_zones", AsyncMock(return_value=COMUNI)),
        patch(f"{FLOW}.fetch_zone_names", AsyncMock(return_value=ZONES)),
        patch(f"{FLOW}.fetch_stations", AsyncMock(return_value=STATIONS)),
    ):
        yield


async def _start_weather(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "weather"})


async def test_weather_flow_creates_entry(enable_custom_integrations, hass, arpav_lists):
    """Municipality → zone → station creates a weather location."""
    result = await _start_weather(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "weather"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1"})
    assert result["step_id"] == "zone"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1", "zone_id": "z1"})
    assert result["step_id"] == "station"

    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station_id": "s1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["station_id"] == "s1"
    assert result["data"]["zone_id"] == "z1"
    assert result["data"]["station_latitude"] == 45.34
    assert result["result"].unique_id == "z1_s1"


async def test_weather_flow_rejects_duplicates(enable_custom_integrations, hass, arpav_lists):
    """The same zone and station cannot be configured twice."""
    MockConfigEntry(domain=DOMAIN, unique_id="z1_s1", data={"station_id": "s1"}).add_to_hass(hass)
    result = await _start_weather(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1", "zone_id": "z1"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"station_id": "s1"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"


@pytest.mark.parametrize("failing", ["fetch_zones", "fetch_zone_names", "fetch_stations"])
async def test_weather_flow_aborts_when_arpav_is_unreachable(enable_custom_integrations, hass, arpav_lists, failing):
    """A network error at any step aborts cleanly with cannot_connect."""
    with patch(f"{FLOW}.{failing}", AsyncMock(side_effect=aiohttp.ClientError("down"))):
        result = await _start_weather(hass)
        if result["type"] is FlowResultType.FORM:
            result = await hass.config_entries.flow.async_configure(result["flow_id"], {"comune_id": "c1"})
        if result["type"] is FlowResultType.FORM:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"comune_id": "c1", "zone_id": "z1"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "cannot_connect"


def _weather_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="z1_s1", data={
        "comune_id": "c1", "comune_name": "Padova (Pd)", "zone_id": "z1", "zone_name": "Pianura centrale",
        "station_id": "s1", "station_name": "Legnaro (Pd)", "station_latitude": 45.34, "station_longitude": 11.95})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def option_lists():
    """Mock the lists of the weather options flow."""
    with (
        patch(f"{FLOW}.fetch_stations_air", AsyncMock(return_value=({"a1": "Padova - urbana"}, {}))),
        patch(f"{FLOW}.metar.async_fetch_stations", AsyncMock(return_value=[])),
    ):
        yield


async def test_weather_options(enable_custom_integrations, hass, option_lists):
    """The options are saved; the custom thresholds open a second step."""
    entry = _weather_entry(hass)
    answers = {CONF_INFER_CONDITION: CONF_INFER_CONDITION_FROM_SENSORS, CONF_OBSERVATIONS: {}, CONF_AIR_QUALITY: {}}

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], answers)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_INFER_CONDITION] == CONF_INFER_CONDITION_FROM_SENSORS

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**answers, CONF_INFER_CONDITION: CONF_INFER_CONDITION_FROM_SENSORS_WITH_CUSTOM_THRESHOLDS})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "thresholds"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_weather_options_abort_when_arpav_is_unreachable(enable_custom_integrations, hass):
    """The options flow aborts cleanly when the air quality lists cannot be read."""
    entry = _weather_entry(hass)
    with patch(f"{FLOW}.fetch_stations_air", AsyncMock(side_effect=aiohttp.ClientError("down"))):
        result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "cannot_connect"

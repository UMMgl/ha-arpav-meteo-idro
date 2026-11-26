# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Branches left uncovered after the Silver work: archives, services, flows, sensors.

Everything is served from the recorded fixtures through ``aioclient_mock``.
"""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402

from custom_components.arpav_meteo_idro import hydro  # noqa: E402
from custom_components.arpav_meteo_idro.const import (  # noqa: E402
    CONF_ARCHIVE_BRIGHTNESS,
    CONF_HYDRO_ARCHIVE,
    DOMAIN,
)
from custom_components.arpav_meteo_idro.hydro_sensor import SENSORS, HydroSensor  # noqa: E402

from .test_gold_ha import _setup, arpav  # noqa: E402, F401
from .test_hydro_ha import _entry  # noqa: E402
from .test_weather_entry import _setup as _setup_weather  # noqa: E402
from .test_weather_entry import api  # noqa: E402, F401


async def test_hydro_archive_runs_on_setup(
    enable_custom_integrations, hass, arpav, freezer, caplog,  # noqa: F811
):
    """An entry with the archive on schedules it, and a failure is only logged."""
    with patch("custom_components.arpav_meteo_idro.async_import_hydro_history",
               AsyncMock(side_effect=HomeAssistantError("no recorder"))) as archive:
        await _setup(hass, freezer, **{CONF_HYDRO_ARCHIVE: True})
    archive.assert_awaited()
    assert "Unable to archive the hydrometric history" in caplog.text


async def test_hydro_archive_success_is_silent(
    enable_custom_integrations, hass, arpav, freezer, caplog,  # noqa: F811
):
    """A successful archive run on startup logs no warning."""
    with patch("custom_components.arpav_meteo_idro.async_import_hydro_history",
               AsyncMock(return_value={})) as archive:
        await _setup(hass, freezer, **{CONF_HYDRO_ARCHIVE: True})
    archive.assert_awaited()
    assert "Unable to archive" not in caplog.text


async def test_brightness_archive_failure_is_only_logged(
    enable_custom_integrations, hass, api, caplog,  # noqa: F811
):
    """A weather entry never fails its setup because the brightness archive does."""
    with patch("custom_components.arpav_meteo_idro.async_archive_brightness",
               AsyncMock(side_effect=aiohttp.ClientError("down"))) as archive:
        entry = await _setup_weather(hass, api, {CONF_ARCHIVE_BRIGHTNESS: True})
    archive.assert_awaited()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert "Unable to archive the night sky brightness" in caplog.text
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_brightness_archive_success_on_setup(
    enable_custom_integrations, hass, api, caplog,  # noqa: F811
):
    """A successful brightness archive on startup logs no warning."""
    with patch("custom_components.arpav_meteo_idro.async_archive_brightness",
               AsyncMock(return_value=3)) as archive:
        entry = await _setup_weather(hass, api, {CONF_ARCHIVE_BRIGHTNESS: True})
    archive.assert_awaited()
    assert "Unable to archive" not in caplog.text
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_hydro_archive_action_rejects_a_weather_entry(
    enable_custom_integrations, hass, api,  # noqa: F811
):
    """The hydrometric archive action refuses an entry of another type."""
    entry = await _setup_weather(hass, api)
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN, "archive_hydro_history", {"entry_id": entry.entry_id}, blocking=True)
    assert raised.value.translation_key == "wrong_entry_type"
    assert raised.value.translation_placeholders == {"entry_id": entry.entry_id}
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_hydro_config_flow_aborts_when_the_registry_is_unreachable(
    enable_custom_integrations, hass, aioclient_mock,
):
    """The river step aborts when the ARPAV station registry cannot be read."""
    aioclient_mock.get(hydro.REGISTRY_URL, exc=aiohttp.ClientError("down"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "hydro"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_hydro_options_flow_aborts_when_the_registry_is_unreachable(
    enable_custom_integrations, hass, aioclient_mock,
):
    """The options flow aborts when the ARPAV station registry cannot be read."""
    aioclient_mock.get(hydro.REGISTRY_URL, exc=TimeoutError())
    entry = _entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_hydro_flows_abort_when_the_registry_is_oversized(
    enable_custom_integrations, hass, arpav, monkeypatch,  # noqa: F811
):
    """A registry over the limit is handled like an unreachable one, by both flows."""
    monkeypatch.setattr(hydro, "MAX_XML_BYTES", 1000)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "hydro"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    entry = _entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_hydro_options_flow_requires_a_station(
    enable_custom_integrations, hass, arpav,  # noqa: F811
):
    """Saving the options with no station is refused."""
    entry = _entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"stations": [], "trend_threshold_cm": 5, "stale_minutes": 0, "archive_history": False})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_stations"}


async def test_hydro_sensor_without_station_data(
    enable_custom_integrations, hass, arpav, freezer,  # noqa: F811
):
    """A sensor whose station vanished from the coordinator data is unavailable and bare."""
    entry = await _setup(hass, freezer)
    coordinator = entry.runtime_data.coordinator
    meta = coordinator.stations[0]
    level = next(d for d in SENSORS if d.key == "level")
    sensor = HydroSensor(coordinator, meta, level)

    assert sensor.available
    assert sensor.extra_state_attributes is not None

    coordinator.async_set_updated_data({})
    await hass.async_block_till_done()
    assert not sensor.available
    assert sensor.native_value is None
    assert sensor.extra_state_attributes is None

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_hydro_{meta['id']}_level")
    assert hass.states.get(entity_id).state == "unavailable"

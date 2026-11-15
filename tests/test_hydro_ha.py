# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Home Assistant tests for the hydrometric stations (config flow, sensors, history)."""

import asyncio
import pathlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.components.recorder.statistics import async_import_statistics, statistics_during_period  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.arpav_meteo_idro import hydro, hydro_coordinator, hydro_statistics  # noqa: E402
from custom_components.arpav_meteo_idro.const import (  # noqa: E402
    CONF_ENTRY_TYPE,
    CONF_HYDRO_ARCHIVE,
    CONF_HYDRO_RIVER,
    CONF_HYDRO_STALE_MINUTES,
    CONF_HYDRO_STATIONS,
    CONF_HYDRO_TREND_THRESHOLD,
    DOMAIN,
    ENTRY_TYPE_HYDRO,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
REGISTRY = (FIXTURES / "stazioni_idro.xml").read_bytes()
# the fixtures were captured with the last reading at 08:00 solar time
NOW = datetime(2026, 11, 15, 7, 20, tzinfo=UTC)


def _meta(station_id, name, place, lat, lon):
    return {"id": station_id, "name": name, "place": place, "latitude": lat, "longitude": lon,
            "link": f"{int(station_id):04d}.xml"}


STATIONS = [
    _meta("333", "Bacchiglione a Vicenza", "Vicenza", 45.55, 11.55),
    _meta("334", "Bacchiglione a Padova Voltabarozzo", "Padova Voltabarozzo", 45.38, 11.90),
    _meta("287", "Bacchiglione a Bovolenta", "Bovolenta", 45.27, 11.93),
]


@pytest.fixture
def arpav(aioclient_mock):
    """Serve the ARPAV fixtures."""
    aioclient_mock.get(hydro.REGISTRY_URL, content=REGISTRY)
    for name in ("0287.xml", "0333.xml", "0334.xml", "0595.xml"):
        aioclient_mock.get(f"{hydro.XML_BASE}/{name}", content=(FIXTURES / name).read_bytes())
    return aioclient_mock


def _entry(**options):
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="hydro_bacchiglione",
        title="Bacchiglione (ARPAV)",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: "Bacchiglione"},
        options={CONF_HYDRO_STATIONS: STATIONS, CONF_HYDRO_TREND_THRESHOLD: 5,
                 CONF_HYDRO_STALE_MINUTES: 0, CONF_HYDRO_ARCHIVE: False, **options},
    )


async def test_config_flow_creates_ordered_entry(enable_custom_integrations, hass, arpav):
    """Menu → river → stations with an explicit upstream-first order."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {"weather", "hydro"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "hydro"})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "hydro"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"river": "Bacchiglione"})
    assert result["step_id"] == "hydro_stations"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"stations": ["287", "333"], "display_order": "x, 1"})
    assert result["errors"] == {"display_order": "invalid_order"}

    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stations": ["287", "333", "276"], "display_order": "276, 333"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: "Bacchiglione"}
    assert [s["id"] for s in result["options"][CONF_HYDRO_STATIONS]] == ["276", "333", "287"]


async def test_sensors_from_real_files(enable_custom_integrations, hass, arpav, freezer):
    """Each station gets level, time, status, trend and change sensors."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    level_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_level")
    status_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_status")
    assert level_id and status_id

    assert float(hass.states.get(level_id).state) == pytest.approx(1.46)
    status = hass.states.get(status_id)
    assert status.state == "below_g1"
    assert status.attributes["guardia3_m"] == 7.0
    assert status.attributes["display_order"] == 30
    assert status.attributes["latitude"] == 45.27
    assert (status.attributes["chart_min_m"], status.attributes["chart_max_m"]) == (2.5, 7.5)

    # Voltabarozzo publishes no thresholds
    volta = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_334_status")
    assert hass.states.get(volta).state == "no_thresholds"
    assert hass.states.get(volta).attributes["guardia1_m"] is None
    assert hass.states.get(volta).attributes["chart_max_m"] is None

    trend = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_trend")
    assert hass.states.get(trend).state in hydro.TRENDS


async def test_old_reading_is_stale(enable_custom_integrations, hass, arpav, freezer):
    """A reading older than the limit is reported as stale, without a trend."""
    freezer.move_to(NOW + timedelta(hours=5))
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    status_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_status")
    assert hass.states.get(status_id).state == "stale"


async def test_backfill_fills_only_missing_complete_hours(
    recorder_mock, enable_custom_integrations, hass, arpav, freezer,
):
    """Keep existing stats and skip partial hours even when retried."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_level")
    series = coordinator.data["287"].series
    partial = hydro.hourly_statistics(series)[0]["start"]
    complete = hydro.hourly_statistics(series, complete_hours_only=True)
    existing, missing = (row["start"] for row in complete[:2])
    assert partial < existing

    async_import_statistics(hass, hydro_statistics._metadata(entity_id), [
        {"start": existing, "mean": 5.0, "min": 4.0, "max": 6.0},
    ])
    await recorder_mock.async_block_till_done()

    report = await hydro_statistics.async_import_hydro_history(hass, coordinator)
    stats = await recorder_mock.async_add_executor_job(
        statistics_during_period, hass, partial, missing + timedelta(hours=1),
        {entity_id}, "hour", None, {"mean"},
    )
    assert {row["start"]: row["mean"] for row in stats[entity_id]} == {
        existing.timestamp(): 5.0,
        missing.timestamp(): complete[1]["mean"],
    }
    assert report[entity_id]["hours"] > 0
    repeat = await hydro_statistics.async_import_hydro_history(hass, coordinator)
    assert all(item["hours"] == 0 for item in repeat.values())


async def test_hydro_keeps_last_valid_on_unusable_response(
    enable_custom_integrations, hass, arpav, freezer,
):
    """Retain the observation and age it while polling healthy stations."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    initial = coordinator.data["287"]
    healthy = {key: state.data for key, state in coordinator.data.items() if key != "287"}
    older_series = replace(initial.series, samples=initial.series.samples[:-1])
    responses = iter([
        replace(initial.data, series=[]),
        replace(initial.data, series=[replace(
            initial.series, samples=[replace(initial.series.samples[-1], value=None, raw=">>")],
        )]),
        replace(initial.data, series=[older_series]),
        initial.data,
    ])

    async def fetch(meta):
        if meta["id"] == "287":
            return next(responses)
        return healthy[meta["id"]]

    with (
        patch.object(coordinator, "_async_fetch_station", side_effect=fetch) as mocked,
        patch("custom_components.arpav_meteo_idro.hydro_coordinator.random.uniform", return_value=1.1),
    ):
        for minutes, expected in [(5, "no_level_series"), (10, "no_valid_samples")]:
            freezer.move_to(NOW + timedelta(minutes=minutes))
            await coordinator.async_refresh()
            state = coordinator.data["287"]
            assert state.acquisition_status == expected
            assert state.reading.level == initial.reading.level
            assert state.reading.observed_at == initial.reading.observed_at
            assert state.fetched_at == initial.fetched_at

        retry_at = coordinator.data["287"].next_retry_at
        assert retry_at == NOW + timedelta(minutes=21)
        freezer.move_to(NOW + timedelta(minutes=15))
        calls = mocked.await_count
        await coordinator.async_refresh()
        assert coordinator.data["287"].acquisition_status == "backoff"
        assert mocked.await_count == calls + len(healthy)
        assert coordinator.data["333"].fetched_at == NOW + timedelta(minutes=15)

        freezer.move_to(NOW + timedelta(hours=2))
        await coordinator.async_refresh()
        state = coordinator.data["287"]
        assert state.acquisition_status == "older_observation"
        assert state.reading.observed_at == initial.reading.observed_at
        assert state.reading.band == "stale"

        freezer.move_to(state.next_retry_at)
        await coordinator.async_refresh()
        recovered = coordinator.data["287"]
        assert recovered.acquisition_status == "ok"
        assert recovered.next_retry_at is None
        assert recovered.consecutive_failures == 0
        assert recovered.reading.band == "stale"


async def test_hydro_limits_concurrency_and_keeps_partial_success(
    enable_custom_integrations, hass, arpav, freezer,
):
    """Keep the request limit even when one station times out."""
    freezer.move_to(NOW)
    data = hydro.parse_station((FIXTURES / "0287.xml").read_bytes())
    stations = [dict(STATIONS[0], id=str(index)) for index in range(1, 9)]
    entry = _entry(**{CONF_HYDRO_STATIONS: stations})
    entry.add_to_hass(hass)
    active = maximum = 0

    async def fetch(_coordinator, meta):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(0)
            if meta["id"] == "1":
                raise TimeoutError
            return replace(data, station_id=meta["id"])
        finally:
            active -= 1

    with patch.object(hydro_coordinator.HydroCoordinator, "_async_fetch_station", fetch):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data.coordinator
        assert maximum == hydro_coordinator.MAX_CONCURRENT_STATIONS
        assert coordinator.data["1"].acquisition_status == "fetch_error"
        assert coordinator.data["2"].reading.level == 1.46


async def test_weather_entries_are_untouched(hass):
    """An entry without entry_type is still a weather location."""
    from custom_components.arpav_meteo_idro import _is_hydro

    weather = MockConfigEntry(domain=DOMAIN, data={"station_id": "1"})
    assert not _is_hydro(weather)
    assert _is_hydro(_entry())


async def test_archive_action_returns_a_report(
    recorder_mock, enable_custom_integrations, hass, arpav, freezer,
):
    """The action answers how many hours it wrote, per level sensor."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        DOMAIN, "archive_hydro_history", {"entry_id": entry.entry_id}, blocking=True, return_response=True)
    assert response["imported_hours"] > 0
    assert len(response["sensors"]) == len(STATIONS)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Home Assistant tests for the hydrometric stations (config flow, sensors, history)."""

import asyncio
import pathlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import aiohttp
import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.components.recorder.statistics import async_import_statistics, statistics_during_period  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import entity_registry as er, issue_registry as ir  # noqa: E402
from homeassistant.helpers.aiohttp_client import async_get_clientsession  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.arpav_meteo_idro import (  # noqa: E402
    LEGACY_ORDER_OPTION,
    LEGACY_ORDER_REPAIR,
    async_migrate_entry,
    http_limits,
    hydro,
    hydro_coordinator,
    hydro_statistics,
)
from custom_components.arpav_meteo_idro.const import (  # noqa: E402
    CONF_ENTRY_TYPE,
    CONF_HYDRO_ARCHIVE,
    CONF_HYDRO_AXIS_CEILING,
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
    # an entry saved by 0.15.x is at version 1.1; the migration tests start from it
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="hydro_bacchiglione",
        title="Bacchiglione (ARPAV)",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: "Bacchiglione"},
        options={CONF_HYDRO_STATIONS: STATIONS, CONF_HYDRO_TREND_THRESHOLD: 5,
                 CONF_HYDRO_STALE_MINUTES: 0, CONF_HYDRO_ARCHIVE: False, **options},
    )


async def test_config_flow_orders_the_stations_by_the_river_profile(enable_custom_integrations, hass, arpav):
    """Menu → river → stations: no order field, the verified profile orders the entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    assert set(result["menu_options"]) == {"weather", "hydro"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "hydro"})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "hydro"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"river": "Bacchiglione"})
    assert result["step_id"] == "hydro_stations"
    assert [field.schema for field in result["data_schema"].schema] == ["stations"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"stations": []})
    assert result["errors"] == {"base": "no_stations"}

    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stations": ["287", "333", "276"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: "Bacchiglione"}
    assert [s["id"] for s in result["options"][CONF_HYDRO_STATIONS]] == ["276", "333", "287"]
    assert LEGACY_ORDER_OPTION not in result["options"]
    assert (result["result"].version, result["result"].minor_version) == (1, 2)


async def test_config_flow_uses_automatic_profile_for_brenta(enable_custom_integrations, hass, arpav):
    """Apply the Brenta profile on first setup."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "hydro"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"river": "Brenta"})
    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HYDRO_STATIONS: ["646", "374", "329", "629"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert LEGACY_ORDER_OPTION not in result["options"]
    assert [s["id"] for s in result["options"][CONF_HYDRO_STATIONS]] == ["374", "629", "329", "646"]


async def _status_attributes(hass, station_id):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_{station_id}_status")
    return hass.states.get(entity_id).attributes


@pytest.mark.parametrize("order_options", [{LEGACY_ORDER_OPTION: "287, 334, 333"}, {LEGACY_ORDER_OPTION: ""}],
                         ids=["manual-order", "cleared-order"])
async def test_migration_drops_the_manual_order(
    enable_custom_integrations, hass, arpav, freezer, order_options,
):
    """An entry with a saved order switches to the verified profile and loses its Repairs issue."""
    freezer.move_to(NOW)
    entry = _entry(stations=list(reversed(STATIONS)), **order_options)
    entry.add_to_hass(hass)
    assert (entry.version, entry.minor_version) == (1, 1)
    # the issue the 0.15.5 setup created
    issue_id = f"{LEGACY_ORDER_REPAIR}_{entry.entry_id}"
    ir.async_create_issue(hass, DOMAIN, issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING,
                          translation_key=LEGACY_ORDER_REPAIR)
    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (1, 2)
    assert LEGACY_ORDER_OPTION not in entry.options
    # everything else is kept
    assert entry.options[CONF_HYDRO_TREND_THRESHOLD] == 5
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    # Vicenza, Voltabarozzo, Bovolenta: the profile order, not the saved one
    assert [meta["id"] for meta in entry.runtime_data.coordinator.stations] == ["333", "334", "287"]
    attributes = await _status_attributes(hass, "287")
    assert attributes["display_order"] == 30
    assert attributes["display_order_source"] == "topology"
    assert attributes["topology_status"] == "verified"
    assert attributes["topology_source_reference"] == "Tavola 05"
    assert attributes["topology_confidence"] == "high"


async def test_migration_of_an_entry_without_a_saved_order(enable_custom_integrations, hass, arpav, freezer):
    """An entry of 0.15.4 or older (no order option at all) also moves to the profile."""
    freezer.move_to(NOW)
    entry = _entry(stations=list(reversed(STATIONS)))
    assert LEGACY_ORDER_OPTION not in entry.options
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (1, 2)
    assert LEGACY_ORDER_OPTION not in entry.options
    assert [meta["id"] for meta in entry.runtime_data.coordinator.stations] == ["333", "334", "287"]
    assert (await _status_attributes(hass, "287"))["display_order_source"] == "topology"


async def test_migration_keeps_stations_outside_the_profile_after_the_profiled_ones(
    enable_custom_integrations, hass, arpav, freezer,
):
    """Unprofiled stations follow the profiled ones, in the order they were selected."""
    freezer.move_to(NOW)
    extra = [_meta("999", "Bacchiglione new gauge", "New", 45.1, 11.7),
             _meta("998", "Bacchiglione other gauge", "Other", 45.0, 11.6)]
    for station in extra:
        arpav.get(f"{hydro.XML_BASE}/{station['link']}", exc=aiohttp.ClientError)
    entry = _entry(stations=[extra[0], STATIONS[2], extra[1], STATIONS[0]],
                   **{LEGACY_ORDER_OPTION: "998, 999, 287"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (1, 2)
    assert [meta["id"] for meta in entry.runtime_data.coordinator.stations] == ["333", "287", "999", "998"]
    profiled = await _status_attributes(hass, "287")
    assert (profiled["display_order"], profiled["display_order_source"]) == (20, "topology")
    outside = await _status_attributes(hass, "998")
    assert (outside["display_order"], outside["display_order_source"]) == (40, "selection")
    assert outside["topology_status"] == "candidate"


async def test_a_river_without_a_profile_uses_the_selection_order(enable_custom_integrations, hass, arpav, freezer):
    """No profile: the whole entry is shown in the order of selection."""
    freezer.move_to(NOW)
    entry = _entry(stations=list(reversed(STATIONS)))
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_HYDRO_RIVER: "An unprofiled river"})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [meta["id"] for meta in entry.runtime_data.coordinator.stations] == ["287", "334", "333"]
    assert (await _status_attributes(hass, "333"))["display_order_source"] == "selection"


async def test_migration_of_a_weather_entry_only_bumps_the_version(enable_custom_integrations, hass):
    """The weather entries have nothing to drop."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="z1_s1", data={"station_id": "s1"},
                            options={"update_interval": 5})
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry)
    assert (entry.version, entry.minor_version) == (1, 2)
    assert entry.options == {"update_interval": 5}


async def test_migration_refuses_an_entry_of_a_newer_version(enable_custom_integrations, hass):
    """A downgrade must not rewrite an entry saved by a newer release."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO},
                            options={LEGACY_ORDER_OPTION: "1"})
    entry.add_to_hass(hass)
    assert not await async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert entry.options == {LEGACY_ORDER_OPTION: "1"}


async def test_an_entry_already_at_1_2_is_left_untouched(enable_custom_integrations, hass):
    """The migration runs once: a migrated entry keeps whatever it holds."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=2, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO},
                            options={LEGACY_ORDER_OPTION: "1"})
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry)
    assert (entry.version, entry.minor_version) == (1, 2)
    assert entry.options == {LEGACY_ORDER_OPTION: "1"}


async def test_options_flow_has_no_order_field(enable_custom_integrations, hass, arpav, freezer):
    """The options form offers the stations and the other options, not the order."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "hydro_options"
    assert LEGACY_ORDER_OPTION not in [field.schema for field in result["data_schema"].schema]


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
    assert hass.states.get(volta).attributes["chart_min_m"] is None
    assert hass.states.get(volta).attributes["axis_ceiling_source"] is None

    trend = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_trend")
    assert hass.states.get(trend).state in hydro.TRENDS


async def test_level_sensor_exposes_unrecorded_samples(enable_custom_integrations, hass, arpav, freezer):
    """Only the level sensor carries the 24 h samples, and the Recorder must skip them."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    level_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_level")
    samples = hass.states.get(level_id).attributes["samples_24h"]
    assert 100 <= len(samples) <= hydro.MAX_RECENT_SAMPLES
    assert samples[-1][1] == pytest.approx(1.46)
    assert datetime.fromisoformat(samples[-1][0]) == datetime(2026, 11, 15, 7, 0, tzinfo=UTC)

    for key in ("status", "trend", "level_change", "observed_at"):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_{key}")
        if entity_id and hass.states.get(entity_id):
            assert "samples_24h" not in hass.states.get(entity_id).attributes

    from custom_components.arpav_meteo_idro.hydro_sensor import HydroSensor  # noqa: PLC0415
    assert "samples_24h" in HydroSensor._unrecorded_attributes  # noqa: SLF001


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


async def test_hydro_oversized_document_is_an_unusable_response(
    enable_custom_integrations, hass, arpav, freezer, monkeypatch,
):
    """A station file over the limit is a fetch error: the last valid reading is kept."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data.coordinator
    before = dict(coordinator.data)

    session = async_get_clientsession(hass)
    monkeypatch.setattr(hydro, "MAX_XML_BYTES", 1000)
    with pytest.raises(http_limits.ResponseTooLargeError):
        await hydro_coordinator.async_fetch_document(session, hydro.REGISTRY_URL)
    with pytest.raises(http_limits.ResponseTooLargeError):
        await hydro_coordinator.async_fetch_registry(hass)

    freezer.move_to(NOW + timedelta(minutes=5))
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    for key, state in coordinator.data.items():
        assert state.acquisition_status == "fetch_error"
        assert state.error == "response too large"
        assert state.reading.level == before[key].reading.level
        assert state.data == before[key].data
        assert state.fetched_at == before[key].fetched_at


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


async def _status(hass, station_id):
    registry = er.async_get(hass)
    return hass.states.get(registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_{station_id}_status"))


async def test_axis_ceiling_fills_only_stations_without_thresholds(
    enable_custom_integrations, hass, arpav, freezer,
):
    """The user ceiling sets chart_max_m without thresholds; ARPAV thresholds always win."""
    freezer.move_to(NOW)
    entry = _entry(**{CONF_HYDRO_AXIS_CEILING: {"334": 10.0, "287": 99.0}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    volta = (await _status(hass, "334")).attributes
    assert volta["chart_max_m"] == 10.0
    assert volta["chart_min_m"] is None
    assert volta["axis_ceiling_source"] == "user"
    assert volta["guardia1_m"] is None

    bovolenta = (await _status(hass, "287")).attributes
    assert (bovolenta["chart_min_m"], bovolenta["chart_max_m"]) == (2.5, 7.5)
    assert bovolenta["axis_ceiling_source"] is None


async def test_entity_ids_and_names_with_apostrophe_station(enable_custom_integrations, hass, arpav, freezer):
    """The accented name is only a display name: unique IDs and entity IDs stay as they were."""
    freezer.move_to(NOW)
    stations = [*STATIONS, _meta("595", "Bacchiglione a Ponte San Nicolo'", "Ponte San Nicolo'", 45.37, 11.97)]
    entry = _entry(**{CONF_HYDRO_STATIONS: stations})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    # the entity registered by a previous release, from the raw ARPAV name
    old = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DOMAIN}_hydro_595_status", suggested_object_id="bacchiglione_a_ponte_san_nicolo_stato",
        config_entry=entry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_595_status")
    assert entity_id == old.entity_id
    assert hass.states.get(entity_id).attributes["station_name"] == "Bacchiglione a Ponte San Nicolò"


async def _options_flow(hass, entry, **user_input):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "hydro_options"
    base = {"stations": ["333", "334", "287"], "trend_threshold_cm": 5,
            "stale_minutes": 0, "archive_history": False}
    return await hass.config_entries.options.async_configure(result["flow_id"], {**base, **user_input})


async def test_options_flow_stores_axis_ceiling(enable_custom_integrations, hass, arpav):
    """A valid ceiling is stored as a mapping and shown again as text."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await _options_flow(hass, entry, axis_ceiling="334=10, 287 = 8.5")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HYDRO_AXIS_CEILING] == {"334": 10.0, "287": 8.5}


async def test_options_flow_shows_stored_ceiling_as_text(enable_custom_integrations, hass, arpav):
    """The stored mapping is the suggested value of the text field, not a default."""
    entry = _entry(**{CONF_HYDRO_AXIS_CEILING: {"334": 10.0}})
    entry.add_to_hass(hass)
    form = await hass.config_entries.options.async_init(entry.entry_id)
    key = next(k for k in form["data_schema"].schema if k == CONF_HYDRO_AXIS_CEILING)
    assert key.description == {"suggested_value": "334=10"}
    assert CONF_HYDRO_AXIS_CEILING not in form["data_schema"]({"stations": []})


async def test_options_flow_matches_padded_station_ids(enable_custom_integrations, hass, arpav):
    """Like the order field, 0334 and 334 are the same station (saved under the entry's ID)."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await _options_flow(hass, entry, axis_ceiling="0334=10")
    assert result["data"][CONF_HYDRO_AXIS_CEILING] == {"334": 10.0}


async def test_axis_ceiling_matches_padded_stored_ids(enable_custom_integrations, hass, arpav, freezer):
    """A ceiling stored under a padded ID still applies to the station."""
    freezer.move_to(NOW)
    stored = _entry(**{CONF_HYDRO_AXIS_CEILING: {"0334": 12.0}})
    stored.add_to_hass(hass)
    assert await hass.config_entries.async_setup(stored.entry_id)
    await hass.async_block_till_done()
    assert (await _status(hass, "334")).attributes["chart_max_m"] == 12.0


async def test_options_flow_empty_ceiling_clears_it(enable_custom_integrations, hass, arpav):
    """An empty field removes every ceiling."""
    entry = _entry(**{CONF_HYDRO_AXIS_CEILING: {"334": 10.0}})
    entry.add_to_hass(hass)
    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await _options_flow(hass, entry, axis_ceiling="")
    assert result["data"][CONF_HYDRO_AXIS_CEILING] == {}


async def test_options_flow_omitted_ceiling_clears_it(enable_custom_integrations, hass, arpav):
    """The frontend omits an emptied optional field: the ceilings must be removed."""
    entry = _entry(**{CONF_HYDRO_AXIS_CEILING: {"334": 10.0}})
    entry.add_to_hass(hass)
    with patch("custom_components.arpav_meteo_idro.async_setup_entry", return_value=True):
        result = await _options_flow(hass, entry)  # no axis_ceiling key at all
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HYDRO_AXIS_CEILING] == {}


@pytest.mark.parametrize("text", [
    "999=10",    # not a station of the entry
    "595=10",    # known to ARPAV but not selected
    "334=abc", "334=0", "334=-2", "334=100.5", "334", "334=10, x=2",
])
async def test_options_flow_rejects_invalid_ceiling(enable_custom_integrations, hass, arpav, text):
    """Unknown stations and invalid numbers give a translated error and store nothing."""
    entry = _entry()
    entry.add_to_hass(hass)
    result = await _options_flow(hass, entry, axis_ceiling=text)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HYDRO_AXIS_CEILING: "invalid_axis_ceiling"}
    assert CONF_HYDRO_AXIS_CEILING not in entry.options

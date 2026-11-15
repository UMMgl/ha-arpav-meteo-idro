# SPDX-License-Identifier: Apache-2.0
"""Home Assistant tests for the hydrometric stations (config flow, sensors, history)."""

import pathlib
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.arpa_veneto_weather import hydro  # noqa: E402
from custom_components.arpa_veneto_weather.const import (  # noqa: E402
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


async def test_config_flow_creates_ordered_entry(hass, arpav):
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

    with patch("custom_components.arpa_veneto_weather.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stations": ["287", "333", "276"], "display_order": "276, 333"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: "Bacchiglione"}
    assert [s["id"] for s in result["options"][CONF_HYDRO_STATIONS]] == ["276", "333", "287"]


async def test_sensors_from_real_files(hass, arpav, freezer):
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

    # Voltabarozzo publishes no thresholds
    volta = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_334_status")
    assert hass.states.get(volta).state == "no_thresholds"
    assert hass.states.get(volta).attributes["guardia1_m"] is None

    trend = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_trend")
    assert hass.states.get(trend).state in hydro.TRENDS


async def test_old_reading_is_stale(hass, arpav, freezer):
    """A reading older than the limit is reported as stale, without a trend."""
    freezer.move_to(NOW + timedelta(hours=5))
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    status_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_status")
    assert hass.states.get(status_id).state == "stale"


async def test_history_is_imported_into_the_level_statistics(hass, arpav, freezer):
    """The archive writes hourly statistics into the level sensor, recorder source."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.config.components.add("recorder")

    from custom_components.arpa_veneto_weather import hydro_statistics

    with patch.object(hydro_statistics, "async_import_statistics") as imported:
        coordinator = entry.runtime_data.coordinator
        count = await hydro_statistics.async_import_hydro_history(hass, coordinator)

    assert count > 0 and imported.call_count == len(STATIONS)
    metadata, statistics = imported.call_args_list[-1].args[1:]
    assert metadata["source"] == "recorder"
    assert metadata["statistic_id"].startswith("sensor.")
    assert metadata["unit_of_measurement"] == "m"
    cut = NOW.replace(minute=0) - timedelta(hours=1)
    assert all(s["start"] + timedelta(hours=1) <= cut for s in statistics)


async def test_weather_entries_are_untouched(hass):
    """An entry without entry_type is still a weather location."""
    from custom_components.arpa_veneto_weather import _is_hydro

    weather = MockConfigEntry(domain=DOMAIN, data={"station_id": "1"})
    assert not _is_hydro(weather)
    assert _is_hydro(_entry())

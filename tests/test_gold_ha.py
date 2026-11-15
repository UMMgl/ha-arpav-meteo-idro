# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Home Assistant tests of the Gold rules: diagnostics, stale devices, disabled entities, exceptions."""

import pathlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("fcntl")  # Home Assistant tests need a POSIX system
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.components.diagnostics import REDACTED  # noqa: E402
from homeassistant.exceptions import ServiceValidationError  # noqa: E402
from homeassistant.helpers import device_registry as dr  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.arpav_meteo_idro import (  # noqa: E402
    ArpavRuntimeData,
    async_remove_config_entry_device,
    hydro,
)
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
from custom_components.arpav_meteo_idro.diagnostics import async_get_config_entry_diagnostics  # noqa: E402
from custom_components.arpav_meteo_idro.hydro_coordinator import HydroCoordinator  # noqa: E402

from .test_hydro_ha import NOW, REGISTRY, STATIONS, _entry  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def arpav(aioclient_mock):
    """Serve the ARPAV fixtures."""
    aioclient_mock.get(hydro.REGISTRY_URL, content=REGISTRY)
    for name in ("0287.xml", "0333.xml", "0334.xml", "0595.xml"):
        aioclient_mock.get(f"{hydro.XML_BASE}/{name}", content=(FIXTURES / name).read_bytes())
    return aioclient_mock


def _device(hass, entry, station_id):
    """Return the device of a station among the devices of the entry, if any."""
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        if (DOMAIN, f"hydro_{station_id}") in device.identifiers:
            return device
    return None


async def _setup(hass, freezer, **options):
    freezer.move_to(NOW)
    entry = _entry(**options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_hydro_diagnostics_are_redacted(enable_custom_integrations, hass, arpav, freezer):
    """Stations, status and errors are there; coordinates and title are not."""
    entry = await _setup(hass, freezer)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry_type"] == "hydro"
    assert result["entry"]["title"] == REDACTED
    assert result["entry"]["data"][CONF_HYDRO_RIVER] == "Bacchiglione"
    assert result["coordinator"]["last_update_success"] is True
    assert result["coordinator"]["last_exception"] is None
    assert [s["meta"]["id"] for s in result["stations"]] == ["333", "334", "287"]
    for station in result["stations"]:
        assert station["meta"]["latitude"] == REDACTED
        assert station["meta"]["longitude"] == REDACTED
        assert station["acquisition_status"] == "ok"
        assert station["last_fetch_error"] is None
    for option_station in result["entry"]["options"][CONF_HYDRO_STATIONS]:
        assert option_station["latitude"] == REDACTED
    text = str(result)
    for secret in ("45.55", "11.55", "45.38", "11.9", "Bacchiglione (ARPAV)"):
        assert secret not in text


async def test_hydro_diagnostics_report_the_last_fetch_error(enable_custom_integrations, hass, arpav, freezer):
    """A failing station shows its error and the retry state."""
    entry = await _setup(hass, freezer)
    state = entry.runtime_data.coordinator.data["287"]
    state.error = "boom"
    state.acquisition_status = "fetch_error"
    state.consecutive_failures = 2

    result = await async_get_config_entry_diagnostics(hass, entry)

    station = next(s for s in result["stations"] if s["meta"]["id"] == "287")
    assert station["last_fetch_error"] == "boom"
    assert station["acquisition_status"] == "fetch_error"
    assert station["consecutive_failures"] == 2


async def test_weather_diagnostics_are_redacted(enable_custom_integrations, hass):
    """The weather entry keeps the ids and loses the municipality and the coordinates."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="z1_s1", title="Padova (Pd) / Stazione di Legnaro (Pd)",
        data={"comune_id": "c1", "comune_name": "Padova (Pd)", "zone_id": "z1", "zone_name": "Pianura centrale",
              "station_id": "s1", "station_name": "Legnaro (Pd)",
              "station_latitude": 45.34, "station_longitude": 11.95},
        options={"update_interval": 10},
    )
    entry.add_to_hass(hass)
    coordinator = SimpleNamespace(
        last_update_success=True, last_update_success_time=datetime(2026, 11, 15, 7, 20, tzinfo=UTC),
        update_interval=None, last_exception=None,
        data={"sensors": {"temperature": 12.3, "humidity": None}, "forecast": [{}, {}]},
    )
    entry.runtime_data = ArpavRuntimeData(coordinator)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry_type"] == "weather"
    data = result["entry"]["data"]
    assert data["zone_id"] == "z1" and data["zone_name"] == "Pianura centrale"
    for key in ("comune_id", "comune_name", "station_id", "station_name", "station_latitude", "station_longitude"):
        assert data[key] == REDACTED
    assert result["entry"]["title"] == REDACTED
    assert result["entry"]["options"] == {"update_interval": 10}
    assert result["coordinator"]["last_update_success_time"] == "2026-11-15T07:20:00+00:00"
    assert result["data"] == {
        "sensors_with_value": ["temperature"], "sensors_without_value": ["humidity"], "forecast_entries": 2,
    }
    assert "Padova" not in str(result) and "45.34" not in str(result) and "Legnaro" not in str(result)


async def test_deselected_station_loses_its_device(enable_custom_integrations, hass, arpav, freezer):
    """Removing a station in the options removes its device, not the others."""
    entry = await _setup(hass, freezer)
    assert all(_device(hass, entry, i) is not None for i in ("333", "334", "287"))

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_HYDRO_STATIONS: STATIONS[:2]})
    await hass.async_block_till_done()

    assert _device(hass, entry, "287") is None
    assert _device(hass, entry, "333") is not None
    assert _device(hass, entry, "334") is not None
    # the entities of the removed device are gone with it
    assert er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_level") is None


async def test_user_can_delete_only_a_stale_device(enable_custom_integrations, hass, arpav, freezer):
    """The device of a selected station cannot be deleted by hand, a stale one can."""
    entry = await _setup(hass, freezer)
    registry = dr.async_get(hass)
    selected = _device(hass, entry, "287")
    assert not await async_remove_config_entry_device(hass, entry, selected)

    stale = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "hydro_999")})
    assert await async_remove_config_entry_device(hass, entry, stale)

    foreign = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.entry_id)})
    assert not await async_remove_config_entry_device(hass, entry, foreign)


async def test_weather_device_cannot_be_deleted(enable_custom_integrations, hass):
    """The service device of a weather entry is never removable by hand."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="z1_s1", data={"station_id": "s1"})
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.entry_id)})
    assert not await async_remove_config_entry_device(hass, entry, device)


async def test_time_and_change_are_disabled_by_default(enable_custom_integrations, hass, arpav, freezer):
    """New installations disable the two rarely used sensors, never level, status or trend."""
    await _setup(hass, freezer)
    registry = er.async_get(hass)

    def disabled(key):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_hydro_287_{key}")
        assert entity_id, key
        return registry.async_get(entity_id).disabled_by

    assert disabled("observed_at") is er.RegistryEntryDisabler.INTEGRATION
    assert disabled("level_change") is er.RegistryEntryDisabler.INTEGRATION
    assert disabled("level") is None
    assert disabled("status") is None
    assert disabled("trend") is None


async def test_existing_entities_keep_their_state(enable_custom_integrations, hass, arpav, freezer):
    """An entity already in the registry is not disabled by the new default."""
    freezer.move_to(NOW)
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DOMAIN}_hydro_287_observed_at", config_entry=entry)
    assert existing.disabled_by is None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(existing.entity_id).disabled_by is None
    assert hass.states.get(existing.entity_id) is not None


async def test_service_error_is_translated(enable_custom_integrations, hass, arpav, freezer):
    """A service call for an unknown entry raises a translated validation error."""
    await _setup(hass, freezer)
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            DOMAIN, "refresh_data", {"entry_id": "nope"}, blocking=True)
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "entry_not_loaded"
    assert raised.value.translation_placeholders == {"entry_id": "nope"}


async def test_update_failed_is_translated(enable_custom_integrations, hass, aioclient_mock):
    """When no station can be read the coordinator fails with a translated error."""
    for name in ("0287.xml", "0333.xml", "0334.xml"):
        aioclient_mock.get(f"{hydro.XML_BASE}/{name}", status=500)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="hydro_bacchiglione",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_HYDRO, CONF_HYDRO_RIVER: "Bacchiglione"},
        options={CONF_HYDRO_STATIONS: STATIONS, CONF_HYDRO_TREND_THRESHOLD: 5,
                 CONF_HYDRO_STALE_MINUTES: 0, CONF_HYDRO_ARCHIVE: False},
    )
    entry.add_to_hass(hass)

    with pytest.raises(UpdateFailed) as raised:
        await HydroCoordinator(hass, entry)._async_update_data()

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "no_station_readable"

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Tests of the night sky brightness archive (no network, no recorder)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fcntl")  # the package needs Home Assistant, which runs on POSIX only
pytest.importorskip("homeassistant")

from custom_components.arpav_meteo_idro import brightness_statistics as bs  # noqa: E402
from custom_components.arpav_meteo_idro import http_limits  # noqa: E402

from .helpers import FakeSession, load_json  # noqa: E402


def test_hourly_statistics_aggregates_and_filters():
    """Invalid, zero and undated readings are skipped; thin hours are dropped."""
    hourly = bs._hourly_statistics(load_json("arpav_brightness_readings.json")["data"])

    # 01:00-01:20 +0100 -> 00:00 UTC with three valid readings; 02:00 has only one
    assert len(hourly) == 1
    assert hourly[0]["start"] == datetime(2026, 8, 18, 0, 0, tzinfo=UTC)
    assert hourly[0]["mean"] == 20.3
    assert hourly[0]["min"] == 20.1
    assert hourly[0]["max"] == 20.5


def test_metadata_uses_station_name_or_code():
    """The statistic id is slugified from the station name."""
    meta = bs._metadata({"nome_stazione": "Good Station", "codseqst": "902"})
    assert meta["statistic_id"] == "arpav_meteo_idro:sky_brightness_good_station"
    assert meta["name"] == "Night sky brightness in Good Station"
    assert meta["unit_of_measurement"] == bs.UNIT_OF_MEASUREMENT
    assert bs._metadata({"codseqst": 7})["name"].endswith("7")


async def test_archive_skips_when_recorder_missing():
    """Without the recorder nothing is fetched."""
    hass = SimpleNamespace(config=SimpleNamespace(components=set()))
    assert await bs.async_archive_brightness(hass, 45.4, 11.9) == 0


async def test_archive_imports_nearest_usable_stations():
    """Stations without readings are skipped and the others archived nearest first."""
    hass = SimpleNamespace(config=SimpleNamespace(components={"recorder"}))
    readings = load_json("arpav_brightness_readings.json")
    session = FakeSession({
        "meteo_meteogrammi?": load_json("arpav_brightness_network.json"),
        "codseqst=901": {"data": []},
        "codseqst=902": readings,
        "codseqst=900": readings,
    })
    add = MagicMock()
    with (
        patch.object(bs, "async_get_clientsession", lambda hass: session),
        patch.object(bs, "async_add_external_statistics", add),
    ):
        imported = await bs.async_archive_brightness(hass, 45.4, 11.9, stations=2)

    assert imported == 2
    assert add.call_count == 2
    assert add.call_args_list[0].args[2][0]["mean"] == 20.3
    assert not any("codseqst=None" in url for url in session.requests)


async def test_archive_oversized_response_is_a_client_error(monkeypatch):
    """A body over the limit reaches the callers as an aiohttp error, which they already handle."""
    monkeypatch.setattr(http_limits, "MAX_JSON_RESPONSE_BYTES", 10)
    hass = SimpleNamespace(config=SimpleNamespace(components={"recorder"}))
    session = FakeSession({"meteo_meteogrammi?": load_json("arpav_brightness_network.json")})
    add = MagicMock()
    with (
        patch.object(bs, "async_get_clientsession", lambda hass: session),
        patch.object(bs, "async_add_external_statistics", add),
        pytest.raises(http_limits.ResponseTooLargeError),
    ):
        await bs.async_archive_brightness(hass, 45.4, 11.9)
    add.assert_not_called()

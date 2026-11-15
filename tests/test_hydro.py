# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Tests for the ARPAV hydrometric parser (no Home Assistant needed)."""

import importlib.util
import pathlib
import sys
from datetime import UTC, datetime, timedelta

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# load the module by path: the package __init__ needs Home Assistant
_spec = importlib.util.spec_from_file_location(
    "arpav_hydro", ROOT / "custom_components" / "arpav_meteo_idro" / "hydro.py")
hydro = importlib.util.module_from_spec(_spec)
sys.modules["arpav_hydro"] = hydro
_spec.loader.exec_module(hydro)


def fixture(name: str) -> bytes:
    """Return a fixture file as bytes."""
    return (FIXTURES / name).read_bytes()


def series_of(values, start=datetime(2026, 11, 15, 8, 0, tzinfo=UTC), step=10, thresholds=(1.0, 2.0, 3.0)):
    """Build a level series from raw VM strings."""
    samples = [hydro.HydroSample(start + timedelta(minutes=step * i), hydro.parse_number(v), v)
               for i, v in enumerate(values)]
    return hydro.HydroSeries("1", hydro.TYPE_LEVEL, "Livello", "m", step, thresholds, samples)


# --- primitives -------------------------------------------------------------

@pytest.mark.parametrize(("raw", "expected"), [
    ("1.45", 1.45), ("-0.24", -0.24), (" 8.20 ", 8.2), ("0,5", 0.5),
    (">>", None), ("", None), (None, None), ("nan", None), ("-", None),
])
def test_parse_number(raw, expected):
    """Sentinels and blanks become None, negative values are kept."""
    assert hydro.parse_number(raw) == expected


def test_parse_instant_is_fixed_utc_plus_one():
    """Solar time is UTC+1 in summer too (no DST)."""
    assert hydro.parse_instant("202611150800") == datetime(2026, 11, 15, 7, 0, tzinfo=UTC)
    assert hydro.parse_instant("202607150800") == datetime(2026, 7, 15, 7, 0, tzinfo=UTC)
    assert hydro.parse_instant("bad") is None


def test_split_name():
    """Station names are "<river> a <place>"."""
    assert hydro.split_name("Bacchiglione a Ponte San Nicolo'") == ("Bacchiglione", "Ponte San Nicolo'")
    assert hydro.split_name("Senza separatore") == (None, None)


# --- registry ---------------------------------------------------------------

def test_registry_lists_the_bacchiglione_stations():
    """The registry gives the seven Bacchiglione stations with coordinates and file."""
    stations = hydro.parse_registry(fixture("stazioni_idro.xml"))
    bacchiglione = {s.station_id: s for s in stations if s.river == "Bacchiglione"}
    assert set(bacchiglione) == {"276", "287", "303", "308", "333", "334", "595"}
    bovolenta = bacchiglione["287"]
    assert bovolenta.place == "Bovolenta"
    assert bovolenta.link == "0287.xml"
    assert bovolenta.url.endswith("/0287.xml")
    assert bovolenta.latitude == pytest.approx(45.27243536)
    assert bovolenta.longitude == pytest.approx(11.9389414)
    assert "Bacchiglione" in hydro.rivers(stations)


# --- station files ----------------------------------------------------------

def test_bovolenta_level_series_and_thresholds():
    """Bovolenta: one LIVIDRO series with GUARDIA 5.5/6.5/7.0."""
    data = hydro.parse_station(fixture("0287.xml"))
    assert data.station_id == "287"
    level = data.level_series()
    assert level.sensor_id == "300005755"
    assert level.thresholds == (5.5, 6.5, 7.0)
    assert level.frequency_minutes == 10
    assert level.samples == sorted(level.samples, key=lambda s: s.observed_at)
    assert len(level.valid_samples) == len(level.samples)


def test_vicenza_flow_sentinels_are_skipped():
    """Vicenza publishes '>>' for the flow: no value, never 0."""
    data = hydro.parse_station(fixture("0333.xml"))
    flow = next(s for s in data.series if s.type == hydro.TYPE_FLOW)
    assert flow.samples and all(s.value is None for s in flow.samples)
    assert data.level_series().sensor_id == "300005837"


def test_voltabarozzo_mixed_station_without_thresholds():
    """Voltabarozzo: PREC + LIVIDRO every 30 min, no thresholds."""
    data = hydro.parse_station(fixture("0334.xml"))
    assert {s.type for s in data.series} == {"PREC", hydro.TYPE_LEVEL}
    level = data.level_series()
    assert level.sensor_id == "300005838"
    assert level.thresholds == (None, None, None)
    assert level.frequency_minutes == 30
    reading = hydro.evaluate(level, level.samples[-1].observed_at)
    assert reading.band == hydro.BAND_NO_THRESHOLDS


def test_explicit_sensor_id():
    """A series is selected by ID, not by position."""
    data = hydro.parse_station(fixture("0595.xml"))
    assert data.level_series("300011408").type == hydro.TYPE_LEVEL
    assert data.level_series("300012208") is None  # that one is the flow
    assert data.level_series("999") is None


def test_html_and_wrong_root_are_rejected():
    """HTML pages and unexpected documents raise a parse error."""
    with pytest.raises(hydro.HydroParseError):
        hydro.parse_station(b"<!DOCTYPE html><html><body>maintenance</body></html>")
    with pytest.raises(hydro.HydroParseError):
        hydro.parse_station(fixture("stazioni_idro.xml"))
    with pytest.raises(hydro.HydroParseError):
        hydro.parse_station(b"<CONTENITORE><STAZIONE>")


# --- evaluation ---------------------------------------------------------------

@pytest.mark.parametrize(("level", "band"), [
    ("-0.5", hydro.BAND_BELOW_G1), ("0.99", hydro.BAND_BELOW_G1), ("1.0", hydro.BAND_G1_G2),
    ("1.99", hydro.BAND_G1_G2), ("2.0", hydro.BAND_G2_G3), ("3.0", hydro.BAND_ABOVE_G3), ("9", hydro.BAND_ABOVE_G3),
])
def test_bands(level, band):
    """Bands are closed below: G1 itself is already above G1."""
    series = series_of([level])
    assert hydro.evaluate(series, series.samples[-1].observed_at).band == band


@pytest.mark.parametrize(("values", "trend"), [
    (["1.00", "1.02", "1.04", "1.06"], hydro.TREND_RISING),   # +6 cm
    (["1.00", "1.01", "1.02", "1.04"], hydro.TREND_STEADY),   # +4 cm, below 5 cm
    (["1.00", "1.01", "1.00", "1.01"], hydro.TREND_STEADY),
    (["1.10", "1.08", "1.05", "1.03"], hydro.TREND_FALLING),  # -7 cm
    (["1.00", "1.00", "1.10", "1.00"], hydro.TREND_STEADY),   # a single spike
    (["1.00", "1.03", ">>", "1.06", "1.09"], hydro.TREND_RISING),  # sentinel skipped
])
def test_trend(values, trend):
    """Trend from the regression over 4 valid readings, threshold 5 cm."""
    series = series_of(values)
    assert hydro.evaluate(series, series.samples[-1].observed_at).trend == trend


def test_trend_needs_four_readings():
    """With fewer than 4 valid readings there is no trend."""
    series = series_of(["1.0", "1.5"])
    reading = hydro.evaluate(series, series.samples[-1].observed_at)
    assert reading.change is None and reading.trend is None


def test_last_sample_invalid_keeps_last_valid_value():
    """A trailing sentinel keeps the previous value and flags the quality."""
    series = series_of(["1.0", "1.1", ">>"])
    reading = hydro.evaluate(series, series.samples[-1].observed_at)
    assert reading.level == 1.1
    assert reading.observed_at == series.samples[1].observed_at
    assert reading.last_sample_valid is False
    assert reading.quality == hydro.QUALITY_LAST_INVALID


def test_stale_and_missing():
    """Old readings are stale (never green); no reading is missing."""
    series = series_of(["0.5"])
    later = series.samples[-1].observed_at + timedelta(minutes=91)
    reading = hydro.evaluate(series, later)
    assert reading.band == hydro.BAND_STALE and reading.trend is None
    assert hydro.evaluate(series_of([">>"]), later).band == hydro.BAND_MISSING
    assert hydro.evaluate(None, later).band == hydro.BAND_MISSING


@pytest.mark.parametrize("thresholds", [(1.0, 2.2, 3.2), (3.0, 4.6, 5.4), (5.5, 6.5, 7.0)])
def test_chart_axis_puts_g1_at_60_and_g3_at_90(thresholds):
    """The normalized scale gives every station the same visual reference."""
    low, high = hydro.chart_axis(thresholds)
    position = lambda v: (v - low) / (high - low)  # noqa: E731
    assert position(thresholds[0]) == pytest.approx(0.6, abs=0.01)
    assert position(thresholds[2]) == pytest.approx(0.9, abs=0.01)


def test_chart_axis_without_thresholds():
    """No published thresholds, no reference scale."""
    assert hydro.chart_axis((None, None, None)) is None
    assert hydro.chart_axis((2.0, 2.0, 1.0)) is None


def test_default_stale_minutes():
    """30-minute series get more room than the 90-minute default."""
    assert hydro.default_stale_minutes(series_of(["1"], step=10)) == 90
    assert hydro.default_stale_minutes(series_of(["1"], step=30)) == 120


# --- hourly statistics ----------------------------------------------------------

def test_hourly_statistics_from_real_file():
    """Hours are complete, in UTC, and only those ended before the cut-off."""
    level = hydro.parse_station(fixture("0287.xml")).level_series()
    cut = level.samples[-1].observed_at.replace(minute=0)
    stats = hydro.hourly_statistics(level, before=cut)
    assert stats
    assert all(s["start"].tzinfo is not None and s["start"].minute == 0 for s in stats)
    assert all(s["start"] + timedelta(hours=1) <= cut for s in stats)
    assert all(s["min"] <= s["mean"] <= s["max"] for s in stats)
    assert stats == sorted(stats, key=lambda s: s["start"])


def test_hourly_statistics_skips_sentinels_and_thin_hours():
    """Sentinels are ignored; an hour with fewer than 3 readings is dropped."""
    series = series_of(["1.0", ">>", "1.2", "1.4", "2.0", "2.2"], start=datetime(2026, 11, 15, 8, 0, tzinfo=UTC), step=15)
    stats = hydro.hourly_statistics(series)
    assert [s["start"].hour for s in stats] == [8]
    assert stats[0]["mean"] == pytest.approx(1.2) and stats[0]["min"] == 1.0 and stats[0]["max"] == 1.4


def test_hourly_statistics_thirty_minute_series():
    """A 30-minute series has 2 readings an hour and is still archived."""
    level = hydro.parse_station(fixture("0334.xml")).level_series()
    assert hydro.hourly_statistics(level)

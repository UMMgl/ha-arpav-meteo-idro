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


def test_registry_recognizes_both_station_name_connectors():
    """Parse station names from the registry written with either a or ad."""
    stations = {s.station_id: (s.river, s.place) for s in hydro.parse_registry(fixture("stazioni_idro.xml"))}
    assert stations["287"] == ("Bacchiglione", "Bovolenta")
    assert stations["664"] == ("Canal Bianco", "Adria")
    assert stations["649"] == ("Cordevole", "Agordo")
    assert stations["684"] == ("Cordevole", "Alleghe")
    assert stations["554"] == ("Muson dei Sassi", "Asolo")


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


# --- untrusted registry data (OWASP A10 / ASVS input validation) ---------------

@pytest.mark.parametrize(("link", "station_id", "expected"), [
    ("0287.xml", "287", "0287.xml"),
    (" 0287.xml ", "287", "0287.xml"),
    (None, "287", "0287.xml"),
    ("", "287", "0287.xml"),
    ("../../etc/passwd", "287", "0287.xml"),
    ("//evil.example/x.xml", "287", "0287.xml"),
    ("0287.xml?x=1", "287", "0287.xml"),
    ("https://evil.example/0287.xml", "287", "0287.xml"),
    ("0287.xml/../../admin", "287", "0287.xml"),
])
def test_station_file_accepts_only_plain_numeric_names(link, station_id, expected):
    """A tampered LINKSTAZ never changes the requested path: the ID is used instead."""
    assert hydro.station_file(link, station_id) == expected
    assert hydro.station_url(link, station_id) == f"{hydro.XML_BASE}/{expected}"


@pytest.mark.parametrize("station_id", ["", "abc", "1/2", "../1", "1234567"])
def test_station_file_rejects_invalid_ids(station_id):
    """Without a valid LINKSTAZ, an invalid station ID is an error, not a URL."""
    with pytest.raises(hydro.HydroParseError):
        hydro.station_file("../bad", station_id)


def test_registry_skips_stations_with_invalid_ids_and_sanitizes_links():
    """Registry entries with non-numeric IDs are skipped; bad links fall back to the ID."""
    document = (
        b"<METEOGRAMMI>"
        b"<STAZIONE><IDSTAZ>287</IDSTAZ><NOME>Fiume a Luogo</NOME><LINKSTAZ>../../x</LINKSTAZ></STAZIONE>"
        b"<STAZIONE><IDSTAZ>../1</IDSTAZ><NOME>Altro a Posto</NOME><LINKSTAZ>0001.xml</LINKSTAZ></STAZIONE>"
        b"</METEOGRAMMI>"
    )
    stations = hydro.parse_registry(document)
    assert [(s.station_id, s.link) for s in stations] == [("287", "0287.xml")]
    assert stations[0].url == f"{hydro.XML_BASE}/0287.xml"


@pytest.mark.parametrize(("raw", "expected"), [
    ("Bacchiglione a Ponte San Nicolo'", "Bacchiglione a Ponte San Nicolò"),
    ("Perche' Citta' Virtu' Cosi' Lunedi'", "Perchè Città Virtù Così Lunedì"),
    ("Nicolo\u2019", "Nicolò"),
    ("NICOLO'", "NICOLÒ"),
    ("Nicolo', Padova", "Nicolò, Padova"),
    # elisions and plain names are left alone
    ("Sant'Antonio", "Sant'Antonio"),
    # Veneto truncations (casa, Po) are not accents; only the whole word
    ("Ca' Bianca", "Ca' Bianca"),
    ("CA' Bianca", "CA' Bianca"),
    ("Fiume a Ca’ Sabbioni", "Fiume a Ca’ Sabbioni"),
    ("Po' a Piacenza", "Po' a Piacenza"),
    ("Fiume a Ca' Nicolo'", "Fiume a Ca' Nicolò"),
    ("Cica' Bianca, Spo'", "Cicà Bianca, Spò"),
    ("Bacchiglione a L'Aquila", "Bacchiglione a L'Aquila"),
    ("Bacchiglione a Vicenza", "Bacchiglione a Vicenza"),
    ("", ""),
])
def test_normalize_name(raw, expected):
    """A vowel + apostrophe ending a word becomes the accented vowel."""
    assert hydro.normalize_name(raw) == expected
    assert hydro.normalize_name(expected) == expected  # idempotent


def test_registry_names_are_normalized_but_ids_and_river_are_not():
    """Only the display names change: the station ID and the river stay as published."""
    document = (
        b"<METEOGRAMMI><STAZIONE><IDSTAZ>595</IDSTAZ>"
        b"<NOME>Bacchiglione a Ponte San Nicolo'</NOME><LINKSTAZ>0595.xml</LINKSTAZ></STAZIONE></METEOGRAMMI>"
    )
    (station,) = hydro.parse_registry(document)
    assert station.station_id == "595"
    assert station.river == "Bacchiglione"
    assert station.name == "Bacchiglione a Ponte San Nicolò"
    assert station.place == "Ponte San Nicolò"


def test_station_file_name_is_normalized():
    """The station file carries the same apostrophe."""
    data = hydro.parse_station(fixture("0595.xml"))
    assert "'" not in (data.name or "")


@pytest.mark.parametrize(("text", "expected"), [
    (None, {}),
    ("", {}),
    ("  ", {}),
    ("334=10", {"334": 10.0}),
    ("334 = 10, 595=7.5", {"334": 10.0, "595": 7.5}),
    ("334=10;595=7.5", {"334": 10.0, "595": 7.5}),
    ("334=100", {"334": 100.0}),
    ("334=0.5,", {"334": 0.5}),
])
def test_parse_axis_ceilings_valid(text, expected):
    """Well formed ceilings, separated by commas or semicolons."""
    assert hydro.parse_axis_ceilings(text) == expected


@pytest.mark.parametrize("text", [
    "334", "334=", "=10", "x=10", "334=abc", "334=0", "334=-1", "334=100.5", "334=nan", "334=inf", "../1=5",
    "595=7,5",  # the comma separates entries: the decimal separator is the dot
])
def test_parse_axis_ceilings_invalid(text):
    """Malformed, non positive, too large or non finite values make the text invalid."""
    assert hydro.parse_axis_ceilings(text) is None


def test_format_axis_ceilings_roundtrip():
    """The text form parses back to the same ceilings."""
    ceilings = {"334": 10.0, "595": 7.5}
    assert hydro.format_axis_ceilings(ceilings) == "334=10, 595=7.5"
    assert hydro.parse_axis_ceilings(hydro.format_axis_ceilings(ceilings)) == ceilings
    assert hydro.format_axis_ceilings({}) == ""


@pytest.mark.parametrize("raw", ["20261115080", "2026111508", "2026111580", "202611158 0", "٢٠٢٦١١١٥٠٨٠٠"])
def test_parse_instant_requires_twelve_ascii_digits(raw):
    """Regression (found by fuzzing): strptime accepted truncated/unpadded instants."""
    assert hydro.parse_instant(raw) is None


# --- recent samples for charts ----------------------------------------------

def test_recent_samples_real_file_is_24_hours_of_10_minute_points():
    """A real 10-minute station gives ~144 compact [iso, value] pairs, oldest first."""
    series = hydro.parse_station(fixture("0287.xml")).level_series()
    recent = hydro.recent_samples(series)
    assert 100 <= len(recent) <= 145
    assert all(len(point) == 2 and isinstance(point[1], float) for point in recent)
    stamps = [datetime.fromisoformat(point[0]) for point in recent]
    assert stamps == sorted(stamps)
    assert stamps[-1] - stamps[0] <= timedelta(hours=24)
    assert stamps[-1] == series.valid_samples[-1].observed_at
    assert stamps[1] - stamps[0] == timedelta(minutes=10)
    assert recent[0][0].endswith("+00:00")


def test_recent_samples_skips_sentinels_and_keeps_negative_values():
    """A sentinel leaves a gap, never a zero; negative levels are real."""
    series = series_of(["0.5", ">>", "-0.24", "0.6"])
    assert [p[1] for p in hydro.recent_samples(series)] == [0.5, -0.24, 0.6]


def test_recent_samples_window_ends_at_last_valid_sample():
    """Older points fall out of the window, anchored on the newest valid sample."""
    series = series_of([str(i / 100) for i in range(200)])  # 200 samples, 10 min apart
    recent = hydro.recent_samples(series)
    assert len(recent) == 145  # 24 h inclusive of both ends
    assert recent[-1][1] == 1.99
    assert hydro.recent_samples(series, hours=1)[0][1] == 1.93


def test_recent_samples_is_bounded():
    """The size limit keeps the newest points."""
    series = series_of(["1.0"] * 20)
    recent = hydro.recent_samples(series, max_points=5)
    assert len(recent) == 5
    assert datetime.fromisoformat(recent[-1][0]) == series.samples[-1].observed_at
    assert len(hydro.recent_samples(series_of(["1"] * 400, step=1))) == hydro.MAX_RECENT_SAMPLES


def test_recent_samples_empty_cases():
    """No series, no valid sample or a zero limit give an empty list."""
    assert hydro.recent_samples(None) == []
    assert hydro.recent_samples(series_of([">>", "-"])) == []
    assert hydro.recent_samples(series_of(["1.0"]), max_points=0) == []


def _station(station_id, river, lat, lon, place="Somewhere"):
    return hydro.HydroStation(
        station_id=station_id, name=f"{river} a {place}", river=river, place=place,
        latitude=lat, longitude=lon, link=f"{int(station_id):04d}.xml")


PADOVA = (45.4064, 11.8768)


def test_haversine():
    """Distances are in kilometres."""
    assert hydro.haversine(45.0, 11.0, 45.0, 11.0) == 0
    assert hydro.haversine(45.0, 11.0, 46.0, 11.0) == pytest.approx(111.2, abs=0.5)


@pytest.mark.parametrize(("lat", "lon", "usable"), [
    (45.4, 11.9, True),
    (0.0, 12.0, True),
    (45.4, 0.0, True),
    (None, 11.9, False),
    (45.4, None, False),
    (0.0, 0.0, False),
    (float("nan"), 11.9, False),
    (45.4, float("inf"), False),
    (91.0, 11.9, False),
    (45.4, 181.0, False),
])
def test_has_home_position(lat, lon, usable):
    """None, NaN, out-of-range and (0, 0) are not a home position."""
    assert hydro.has_home_position(lat, lon) is usable


def test_station_distance():
    """A station without coordinates or a missing home has no distance."""
    near = _station("1", "A", 45.4064, 11.8868)
    assert hydro.station_distance(near, *PADOVA) == pytest.approx(0.78, abs=0.05)
    assert hydro.station_distance(_station("2", "A", None, 11.9), *PADOVA) is None
    assert hydro.station_distance(_station("3", "A", 45.4, None), *PADOVA) is None
    assert hydro.station_distance(near, None, None) is None
    assert hydro.station_distance(near, 0.0, 0.0) is None


def test_rivers_by_distance_orders_by_nearest_station():
    """A river is as far as its nearest station."""
    stations = [
        _station("1", "Piave", 46.1, 12.2),
        _station("2", "Brenta", 45.45, 11.90),
        _station("3", "Brenta", 45.40, 12.01),
        _station("4", "Bacchiglione", 45.39, 11.91),
        _station("5", "Bacchiglione", 45.20, 11.90),
    ]
    result = hydro.rivers_by_distance(stations, *PADOVA)
    assert [name for name, _ in result] == ["Bacchiglione", "Brenta", "Piave"]
    nearest = dict(result)
    # a river is as far as its nearest station, not its first or last one
    assert nearest["Bacchiglione"] == pytest.approx(hydro.haversine(*PADOVA, 45.39, 11.91))
    assert nearest["Brenta"] == pytest.approx(hydro.haversine(*PADOVA, 45.45, 11.90))
    assert nearest["Bacchiglione"] < nearest["Brenta"] < nearest["Piave"]


def test_rivers_by_distance_tie_keeps_alphabetical_order():
    """Equal distances keep the alphabetical order."""
    stations = [_station("1", "Zeta", 45.5, 11.9), _station("2", "alfa", 45.5, 11.9)]
    assert [n for n, _ in hydro.rivers_by_distance(stations, *PADOVA)] == ["alfa", "Zeta"]


def test_rivers_by_distance_rivers_without_coordinates_come_last():
    """Rivers with no coordinates follow, alphabetically."""
    stations = [
        _station("1", "Adige", None, None),
        _station("2", "Brenta", None, 11.9),
        _station("3", "Piave", 46.1, 12.2),
        _station("4", "Po", 44.9, 12.4),
        _station("5", "Adige", 45.4, None),
    ]
    result = hydro.rivers_by_distance(stations, *PADOVA)
    assert [n for n, _ in result][:2] == ["Po", "Piave"]
    assert [km is None for _, km in result] == [False, False, True, True]
    assert [n for n, _ in result][2:] == ["Adige", "Brenta"]


def test_rivers_by_distance_skips_stations_without_a_river():
    """Stations without a river name are ignored."""
    stations = [_station("1", "Adige", 45.4, 11.9),
                hydro.HydroStation("2", "Orphan", None, None, 45.4, 11.9, "0002.xml")]
    assert hydro.rivers_by_distance(stations, *PADOVA) == [("Adige", pytest.approx(
        hydro.haversine(*PADOVA, 45.4, 11.9)))]


@pytest.mark.parametrize("home", [(None, None), (0.0, 0.0), (None, 11.9), (45.4, None)])
def test_rivers_by_distance_without_home_is_alphabetical(home):
    """No usable home: today's alphabetical list, no distances."""
    stations = [_station("1", "Piave", 46.1, 12.2), _station("2", "adige", 45.4, 11.0),
                _station("3", "Brenta", 45.45, 11.9)]
    assert hydro.rivers_by_distance(stations, *home) == [("adige", None), ("Brenta", None), ("Piave", None)]
    assert [n for n, _ in hydro.rivers_by_distance(stations, *home)] == hydro.rivers(stations)


def test_rivers_by_distance_on_the_registry_fixture():
    """Real registry: Bacchiglione and Brenta are the nearest to Padova."""
    stations = hydro.parse_registry(fixture("stazioni_idro.xml"))
    result = hydro.rivers_by_distance(stations, *PADOVA)
    assert [n for n, _ in result][:2] == ["Bacchiglione", "Brenta"]
    assert sorted(n for n, _ in result) == sorted(hydro.rivers(stations))
    assert [km for _, km in result] == sorted(km for _, km in result if km is not None) + \
        [None] * sum(km is None for _, km in result)

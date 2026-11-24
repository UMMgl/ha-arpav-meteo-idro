# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""ARPAV hydrometric stations: parsing and evaluation of the open-data XML.

This module has no Home Assistant dependency, so it can be tested on its own.

Sources (ARPAV open data, CC BY 4.0, automatic data not previously validated):

* station registry: ``stazioni_idro.xml`` (root ``METEOGRAMMI``)
* one file per station: ``<IDSTAZ as 4 digits>.xml`` (root ``CONTENITORE``),
  holding the last ~2-3 days of every series of the station

Rules that come from the data and must not be relaxed:

* timestamps are in solar time, i.e. a fixed UTC+01:00 all year round;
* a series is chosen by ``TYPE`` and ``ID``, never by its position in the file;
* ``VM`` may hold sentinels such as ``>>``: they are skipped, never turned into 0;
* negative levels are real values (the level is relative to the local zero);
* GUARDIA1/2/3 are per-series thresholds: missing means "not published",
  never 0, and they are never borrowed from another station.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, TypedDict, cast

# defusedxml only: a malicious or broken XML must not be able to expand entities
# or reach external resources. There is deliberately no fallback to the
# standard library parser (defusedxml is a requirement of the manifest).
from defusedxml import ElementTree as ET

if TYPE_CHECKING:
    # typing only: parsing always goes through defusedxml
    from xml.etree.ElementTree import Element

XML_BASE = "https://meteo.arpa.veneto.it/meteo/dati_meteo/xml"
REGISTRY_URL = f"{XML_BASE}/stazioni_idro.xml"
# station file names come from the remote registry (LINKSTAZ): only plain
# numeric XML names are accepted, so a tampered registry cannot make the
# integration request arbitrary paths
STATION_FILE = re.compile(r"^[0-9]{1,6}\.xml$")
STATION_ID = re.compile(r"^[0-9]{1,6}$")
# ARPAV instants are always 12 ASCII digits: strptime alone would also accept
# truncated or unpadded values ("20261115080" -> 08:00) and mis-date them
INSTANT = re.compile(r"[0-9]{12}")


def station_file(link: str | None, station_id: str) -> str:
    """Return a safe file name for a station: LINKSTAZ if well formed, else from the ID."""
    if link and STATION_FILE.fullmatch(link.strip()):
        return link.strip()
    if not STATION_ID.fullmatch(str(station_id).strip()):
        raise HydroParseError(f"invalid station id {station_id!r}")
    return f"{int(station_id):04d}.xml"


def station_url(link: str | None, station_id: str) -> str:
    """Return the URL of a station file, always under XML_BASE."""
    return f"{XML_BASE}/{station_file(link, station_id)}"

# ARPAV timestamps carry no offset and are on a fixed +0100 all year round
ARPAV_TZ = timezone(timedelta(hours=1))

TYPE_LEVEL = "LIVIDRO"
TYPE_FLOW = "PORTATA"

# refuse anything bigger than this: a station file is ~20-40 kB
MAX_XML_BYTES = 5 * 1024 * 1024

# trend: least squares slope over the last N valid readings
TREND_SAMPLES = 4
DEFAULT_TREND_THRESHOLD_M = 0.05
# a reading older than this no longer describes the river
DEFAULT_STALE_MINUTES = 90

# recent samples exposed for charts: the last 24 h, at most 288 points (24 h of a
# 5-minute series; ARPAV level series are 10 or 30 minutes, i.e. 144 or 48)
RECENT_SAMPLES_HOURS = 24
MAX_RECENT_SAMPLES = 288

# states exposed by the integration (translated in the UI)
BAND_BELOW_G1 = "below_g1"
BAND_G1_G2 = "g1_g2"
BAND_G2_G3 = "g2_g3"
BAND_ABOVE_G3 = "above_g3"
BAND_NO_THRESHOLDS = "no_thresholds"
BAND_STALE = "stale"
BAND_MISSING = "missing"
BANDS = [BAND_BELOW_G1, BAND_G1_G2, BAND_G2_G3, BAND_ABOVE_G3,
         BAND_NO_THRESHOLDS, BAND_STALE, BAND_MISSING]
# the bands that describe a measured level against published thresholds
LEVEL_BANDS = [BAND_BELOW_G1, BAND_G1_G2, BAND_G2_G3, BAND_ABOVE_G3]

TREND_RISING = "rising"
TREND_STEADY = "steady"
TREND_FALLING = "falling"
TRENDS = [TREND_RISING, TREND_STEADY, TREND_FALLING]

QUALITY_VALID = "valid"
QUALITY_LAST_INVALID = "last_sample_invalid"
QUALITY_STALE = "stale"
QUALITY_MISSING = "missing"


class HydroParseError(ValueError):
    """The document is not the ARPAV XML that was expected."""


@dataclass(frozen=True)
class HydroStation:
    """A station of the ARPAV hydrometric registry."""

    station_id: str
    name: str
    river: str | None
    place: str | None
    latitude: float | None
    longitude: float | None
    link: str

    @property
    def url(self) -> str:
        """Return the URL of the station file."""
        return station_url(self.link, self.station_id)


@dataclass
class HydroSample:
    """A single observation: the value is None when ARPAV published a sentinel."""

    observed_at: datetime
    value: float | None
    raw: str | None


@dataclass
class HydroSeries:
    """A series (sensor) of a station file."""

    sensor_id: str
    type: str
    name: str | None
    unit: str | None
    frequency_minutes: int | None
    thresholds: tuple[float | None, float | None, float | None]
    samples: list[HydroSample] = field(default_factory=list)

    @property
    def valid_samples(self) -> list[HydroSample]:
        """Return the samples holding a number, oldest first."""
        return [s for s in self.samples if s.value is not None]

    @property
    def has_thresholds(self) -> bool:
        """Return True when all three GUARDIA thresholds are published."""
        return all(t is not None for t in self.thresholds)


@dataclass
class HydroStationData:
    """The content of a station file."""

    station_id: str
    name: str | None
    latitude: float | None
    longitude: float | None
    generated_at: datetime | None
    start: datetime | None
    end: datetime | None
    series: list[HydroSeries]

    def level_series(self, sensor_id: str | None = None) -> HydroSeries | None:
        """Return the water level series, by explicit ID or the only LIVIDRO one."""
        levels = [s for s in self.series if s.type == TYPE_LEVEL]
        if sensor_id is not None:
            return next((s for s in levels if s.sensor_id == sensor_id), None)
        # with more than one level series the choice must be explicit
        return levels[0] if len(levels) == 1 else None

    def flow_series(self) -> HydroSeries | None:
        """Return the discharge series, when the file holds exactly one PORTATA series."""
        flows = [s for s in self.series if s.type == TYPE_FLOW]
        # like the level, more than one series is ambiguous: no guess
        return flows[0] if len(flows) == 1 else None


class HourlyStatistic(TypedDict):
    """One completed hourly bucket, in the shape the statistics importer reads."""

    start: datetime
    mean: float
    min: float
    max: float


@dataclass
class HydroReading:
    """What the integration exposes for a station at a given moment."""

    level: float | None
    observed_at: datetime | None
    last_sample_valid: bool | None
    change: float | None
    trend: str | None
    band: str
    quality: str
    age_minutes: float | None
    thresholds: tuple[float | None, float | None, float | None]


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def _root(document: bytes | str, expected: str) -> Element:
    # bytes are preferred: the parser then honours the ISO-8859-1 declaration
    if len(document) > MAX_XML_BYTES:
        raise HydroParseError("document too large")
    head = document.lstrip()[:200]
    head = head.lower() if isinstance(head, str) else head.decode("latin-1").lower()
    if head.startswith(("<!doctype html", "<html")):
        raise HydroParseError("HTML returned instead of XML")
    try:
        root: Element = ET.fromstring(document)
    except Exception as err:  # defusedxml raises its own subclasses
        raise HydroParseError(f"malformed XML: {err}") from err
    if root.tag != expected:
        raise HydroParseError(f"unexpected root {root.tag!r}, expected {expected!r}")
    return root


def parse_number(raw: str | None) -> float | None:
    """Return the value of a VM/threshold, or None for sentinels and blanks."""
    if raw is None:
        return None
    text = raw.strip().replace(",", ".")
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_instant(raw: str | None) -> datetime | None:
    """Return a YYYYMMDDHHMM solar-time instant as an aware UTC datetime."""
    if not raw or not INSTANT.fullmatch(raw.strip()):
        return None
    try:
        local = datetime.strptime(raw.strip(), "%Y%m%d%H%M")
    except ValueError:
        return None
    return local.replace(tzinfo=ARPAV_TZ).astimezone(UTC)


def _float(text: str | None) -> float | None:
    return parse_number(text)


# ARPAV writes accented vowels as vowel + apostrophe ("Nicolo'", "Perche'")
_ACCENTED = {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù",
             "A": "À", "E": "È", "I": "Ì", "O": "Ò", "U": "Ù"}
_APOSTROPHE_ACCENT = re.compile(r"\b([^\W\d_]*)([aeiouAEIOU])['’](?![^\W\d_])")
# truncations, not accents: "Ca'" (casa) and "Po'" stay as written
_TRUNCATIONS = frozenset({"ca", "po"})


def normalize_name(name: str) -> str:
    """Turn a vowel + apostrophe at the end of a word into the accented vowel.

    ``Ponte San Nicolo'`` becomes ``Ponte San Nicolò``. An apostrophe followed
    by a letter is an elision (``Sant'Antonio``) and is left alone. Applying it
    twice gives the same result, so it is safe on names already normalized.
    The Veneto truncations ``Ca'`` (casa) and ``Po'`` are whole words that
    keep their apostrophe: ``Ca' Bianca`` is not ``Cà Bianca``.
    """
    def accent(match: re.Match[str]) -> str:
        if (match.group(1) + match.group(2)).lower() in _TRUNCATIONS:
            return match.group(0)
        return match.group(1) + _ACCENTED[match.group(2)]

    return _APOSTROPHE_ACCENT.sub(accent, name)


def split_name(name: str) -> tuple[str | None, str | None]:
    """Split an ARPAV station name into its river and place."""
    parts = re.split(r" ad? ", name, maxsplit=1)
    if len(parts) != 2:
        return None, None
    river, place = parts
    return river.strip() or None, place.strip() or None


def parse_registry(document: bytes | str) -> list[HydroStation]:
    """Parse ``stazioni_idro.xml`` into stations, in document order."""
    root = _root(document, "METEOGRAMMI")
    stations = []
    for node in root.findall("STAZIONE"):
        station_id = (node.findtext("IDSTAZ") or "").strip()
        name = (node.findtext("NOME") or "").strip()
        if not STATION_ID.fullmatch(station_id) or not name:
            continue
        link = station_file(node.findtext("LINKSTAZ"), station_id)
        river, place = split_name(name)
        stations.append(HydroStation(
            station_id=station_id,
            name=normalize_name(name),
            river=river,
            place=normalize_name(place) if place else None,
            latitude=_float(node.findtext("Y")),
            longitude=_float(node.findtext("X")),
            link=link,
        ))
    return stations


def rivers(stations: list[HydroStation]) -> list[str]:
    """Return the water bodies of the registry, sorted."""
    return sorted({s.river for s in stations if s.river}, key=str.casefold)


def parse_station(document: bytes | str) -> HydroStationData:
    """Parse a station file into its series."""
    root = _root(document, "CONTENITORE")
    node = root.find("STAZIONE")
    if node is None:
        raise HydroParseError("no STAZIONE in the station file")

    series = []
    for sensor in node.findall("SENSORE"):
        sensor_id = (sensor.findtext("ID") or "").strip()
        if not sensor_id:
            continue
        samples = []
        for data in sensor.findall("DATI"):
            observed_at = parse_instant(data.get("ISTANTE"))
            if observed_at is None:
                continue
            raw = data.findtext("VM")
            samples.append(HydroSample(observed_at, parse_number(raw), raw))
        # never trust the order of the nodes
        samples.sort(key=lambda s: s.observed_at)
        frequency = parse_number(sensor.findtext("FREQ"))
        series.append(HydroSeries(
            sensor_id=sensor_id,
            type=(sensor.findtext("TYPE") or "").strip(),
            name=(sensor.findtext("PARAMNM") or "").strip() or None,
            unit=(sensor.findtext("UNITNM") or "").strip() or None,
            frequency_minutes=int(frequency) if frequency else None,
            thresholds=(
                parse_number(sensor.findtext("GUARDIA1")),
                parse_number(sensor.findtext("GUARDIA2")),
                parse_number(sensor.findtext("GUARDIA3")),
            ),
            samples=samples,
        ))

    return HydroStationData(
        station_id=(node.findtext("IDSTAZ") or "").strip(),
        name=normalize_name((node.findtext("NOME") or "").strip()) or None,
        latitude=_float(node.findtext("Y")),
        longitude=_float(node.findtext("X")),
        generated_at=parse_instant(root.findtext("ISTANTERUN")),
        start=parse_instant(root.findtext("INIZIO")),
        end=parse_instant(root.findtext("FINE")),
        series=series,
    )


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

def level_change(samples: list[HydroSample], count: int = TREND_SAMPLES) -> float | None:
    """Return the change over the last ``count`` valid readings, from a least squares fit.

    The slope of the regression line is multiplied by the number of intervals,
    so the result is in the unit of the series (m) and a single spike weighs
    less than in a plain difference between the first and the last reading.
    """
    valid = [s for s in samples if s.value is not None][-count:]
    if len(valid) < count:
        return None
    t0 = valid[0].observed_at
    xs = [(s.observed_at - t0).total_seconds() for s in valid]
    ys = [s.value for s in valid if s.value is not None]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator
    return round(slope * (xs[-1] - xs[0]), 3)


def trend_of(change: float | None, threshold: float = DEFAULT_TREND_THRESHOLD_M) -> str | None:
    """Classify a change: rising/falling only from the threshold up (inclusive)."""
    if change is None:
        return None
    if change >= threshold:
        return TREND_RISING
    if change <= -threshold:
        return TREND_FALLING
    return TREND_STEADY


def band_of(level: float, thresholds: tuple[float | None, float | None, float | None]) -> str:
    """Return the band of a level against the GUARDIA thresholds."""
    g1, g2, g3 = thresholds
    if g1 is None or g2 is None or g3 is None:
        return BAND_NO_THRESHOLDS
    if level < g1:
        return BAND_BELOW_G1
    if level < g2:
        return BAND_G1_G2
    if level < g3:
        return BAND_G2_G3
    return BAND_ABOVE_G3


def evaluate(
    series: HydroSeries | None,
    now: datetime,
    stale_minutes: float = DEFAULT_STALE_MINUTES,
    trend_threshold: float = DEFAULT_TREND_THRESHOLD_M,
) -> HydroReading:
    """Evaluate a level series at ``now`` (aware datetime)."""
    if series is None:
        return HydroReading(None, None, None, None, None, BAND_MISSING, QUALITY_MISSING, None,
                            (None, None, None))

    valid = series.valid_samples
    if not valid:
        return HydroReading(None, None, False if series.samples else None, None, None,
                            BAND_MISSING, QUALITY_MISSING, None, series.thresholds)

    # valid_samples only holds samples with a number: last.value is never None
    last = valid[-1]
    last_sample_valid = series.samples[-1].value is not None
    age = (now - last.observed_at).total_seconds() / 60
    change = level_change(series.samples)

    if age > stale_minutes:
        band, quality = BAND_STALE, QUALITY_STALE
    else:
        band = band_of(cast(float, last.value), series.thresholds)
        quality = QUALITY_VALID if last_sample_valid else QUALITY_LAST_INVALID

    return HydroReading(
        level=last.value,
        observed_at=last.observed_at,
        last_sample_valid=last_sample_valid,
        change=change,
        trend=trend_of(change, trend_threshold) if quality != QUALITY_STALE else None,
        band=band,
        quality=quality,
        age_minutes=round(age, 1),
        thresholds=series.thresholds,
    )


def last_valid_sample(series: HydroSeries | None) -> HydroSample | None:
    """Return the newest sample holding a number, or None (no series, only sentinels)."""
    if series is None:
        return None
    valid = series.valid_samples
    return valid[-1] if valid else None


def recent_samples(
    series: HydroSeries | None,
    hours: float = RECENT_SAMPLES_HOURS,
    max_points: int = MAX_RECENT_SAMPLES,
) -> list[list[str | float]]:
    """Return the valid samples of the last ``hours`` as ``[[iso_utc, value], ...]``.

    The window ends at the newest valid sample (not at "now"), so a stale
    station still shows what it last measured. Sentinels are left out: a gap in
    the list is a gap in the chart. Oldest first, values rounded to millimetres,
    never more than ``max_points`` entries (the newest are kept), so the
    attribute stays small whatever the file holds.
    """
    if series is None or max_points <= 0:
        return []
    valid = series.valid_samples
    if not valid:
        return []
    since = valid[-1].observed_at - timedelta(hours=hours)
    window = [s for s in valid if s.observed_at >= since][-max_points:]
    return [[s.observed_at.isoformat(), round(float(s.value), 3)]
            for s in window if s.value is not None]


# normalized charts: the first and the third threshold always at the same height
CHART_G1_POSITION = 0.6
CHART_G3_POSITION = 0.9


MAX_AXIS_CEILING_M = 100.0


def parse_axis_ceilings(text: str | None) -> dict[str, float] | None:
    """Parse ``station_id=metres[, ...]`` into ``{station_id: metres}``.

    Empty text gives an empty dict. Anything malformed, or a ceiling that is not
    in (0, 100] metres, makes the whole text invalid: None.
    """
    if not text or not text.strip():
        return {}
    result: dict[str, float] = {}
    for token in (t.strip() for t in text.replace(";", ",").split(",")):
        if not token:
            continue
        station_id, sep, raw = token.partition("=")
        station_id = station_id.strip()
        value = parse_number(raw) if sep else None
        if (not STATION_ID.fullmatch(station_id) or value is None
                or not 0 < value <= MAX_AXIS_CEILING_M):
            return None
        result[station_id] = value
    return result


def format_axis_ceilings(ceilings: dict[str, float]) -> str:
    """Return the text form of the ceilings, the inverse of ``parse_axis_ceilings``."""
    return ", ".join(f"{sid}={value:g}" for sid, value in ceilings.items())


def chart_axis(
    thresholds: tuple[float | None, float | None, float | None],
) -> tuple[float, float] | None:
    """Return the (min, max) of a chart axis that puts G1 at 60% and G3 at 90%.

    Charts of different stations then share the same visual reference: the
    level is read against the thresholds, not against an absolute scale.
    Without published thresholds there is no reference: None.
    """
    g1, _, g3 = thresholds
    if g1 is None or g3 is None or g3 <= g1:
        return None
    span = (g3 - g1) / (CHART_G3_POSITION - CHART_G1_POSITION)
    low = g1 - CHART_G1_POSITION * span
    return round(low, 2), round(low + span, 2)


def default_stale_minutes(series: HydroSeries | None) -> float:
    """Return a staleness limit suited to the frequency of a series."""
    if series is None or not series.frequency_minutes:
        return DEFAULT_STALE_MINUTES
    # ARPAV publishes with ~30-60 min of delay: leave room for three slots
    return max(DEFAULT_STALE_MINUTES, 3 * series.frequency_minutes + 30)


def hourly_statistics(
    series: HydroSeries | None,
    before: datetime | None = None,
    min_readings: int = 3,
    *,
    complete_hours_only: bool = False,
) -> list[HourlyStatistic]:
    """Aggregate distinct valid observations into completed hourly buckets."""
    if series is None:
        return []
    by_hour: dict[datetime, dict[datetime, float]] = {}
    for sample in series.valid_samples:
        hour = sample.observed_at.replace(minute=0, second=0, microsecond=0)
        by_hour.setdefault(hour, {})[sample.observed_at] = cast(float, sample.value)

    frequency = series.frequency_minutes
    if complete_hours_only and (not frequency or frequency <= 0 or 60 % frequency):
        return []
    if frequency and frequency >= 30:
        min_readings = min(min_readings, max(1, 60 // frequency))

    statistics: list[HourlyStatistic] = []
    for hour, observations in sorted(by_hour.items()):
        if before is not None and hour + timedelta(hours=1) > before:
            continue
        if complete_hours_only and frequency:
            phases = {timestamp.minute % frequency for timestamp in observations}
            if len(observations) != 60 // frequency or len(phases) != 1:
                continue
        if len(observations) < min_readings and not complete_hours_only:
            continue
        values = observations.values()
        statistics.append({
            "start": hour,
            "mean": round(sum(values) / len(values), 3),
            "min": min(values),
            "max": max(values),
        })
    return statistics

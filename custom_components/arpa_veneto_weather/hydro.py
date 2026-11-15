# SPDX-License-Identifier: Apache-2.0
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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone

try:  # a malicious or broken XML must not be able to expand entities
    from defusedxml import ElementTree as ET  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - defusedxml is a declared requirement
    from xml.etree import ElementTree as ET  # noqa: N817

XML_BASE = "https://meteo.arpa.veneto.it/meteo/dati_meteo/xml"
REGISTRY_URL = f"{XML_BASE}/stazioni_idro.xml"

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
        return f"{XML_BASE}/{self.link}"


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

def _root(document: bytes | str, expected: str):
    # bytes are preferred: the parser then honours the ISO-8859-1 declaration
    if len(document) > MAX_XML_BYTES:
        raise HydroParseError("document too large")
    head = document.lstrip()[:200]
    head = head.lower() if isinstance(head, str) else head.decode("latin-1").lower()
    if head.startswith(("<!doctype html", "<html")):
        raise HydroParseError("HTML returned instead of XML")
    try:
        root = ET.fromstring(document)
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
    if not raw:
        return None
    try:
        local = datetime.strptime(raw.strip(), "%Y%m%d%H%M")
    except ValueError:
        return None
    return local.replace(tzinfo=ARPAV_TZ).astimezone(UTC)


def _float(text: str | None) -> float | None:
    return parse_number(text)


def split_name(name: str) -> tuple[str | None, str | None]:
    """Split an ARPAV station name "<river> a <place>" into its parts."""
    river, sep, place = name.partition(" a ")
    if not sep:
        return None, None
    return river.strip() or None, place.strip() or None


def parse_registry(document: bytes | str) -> list[HydroStation]:
    """Parse ``stazioni_idro.xml`` into stations, in document order."""
    root = _root(document, "METEOGRAMMI")
    stations = []
    for node in root.findall("STAZIONE"):
        station_id = (node.findtext("IDSTAZ") or "").strip()
        name = (node.findtext("NOME") or "").strip()
        if not station_id or not name:
            continue
        link = (node.findtext("LINKSTAZ") or "").strip() or f"{int(station_id):04d}.xml"
        river, place = split_name(name)
        stations.append(HydroStation(
            station_id=station_id,
            name=name,
            river=river,
            place=place,
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
        name=(node.findtext("NOME") or "").strip() or None,
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
    ys = [float(s.value) for s in valid]  # type: ignore[arg-type]
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

    last = valid[-1]
    last_sample_valid = series.samples[-1].value is not None
    age = (now - last.observed_at).total_seconds() / 60
    change = level_change(series.samples)

    if age > stale_minutes:
        band, quality = BAND_STALE, QUALITY_STALE
    else:
        band = band_of(float(last.value), series.thresholds)  # type: ignore[arg-type]
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
) -> list[dict]:
    """Aggregate the valid readings into hourly mean/min/max.

    Only hours that ended before ``before`` are returned, so an hour the
    recorder may still be compiling is never written.
    """
    if series is None:
        return []
    by_hour: dict[datetime, list[float]] = {}
    for sample in series.valid_samples:
        hour = sample.observed_at.replace(minute=0, second=0, microsecond=0)
        by_hour.setdefault(hour, []).append(float(sample.value))  # type: ignore[arg-type]

    # a 30-minute series has at most 2 readings an hour
    if series.frequency_minutes and series.frequency_minutes >= 30:
        min_readings = min(min_readings, max(1, 60 // series.frequency_minutes))

    return [
        {
            "start": hour,
            "mean": round(sum(values) / len(values), 3),
            "min": min(values),
            "max": max(values),
        }
        for hour, values in sorted(by_hour.items())
        if len(values) >= min_readings and (before is None or hour + timedelta(hours=1) <= before)
    ]

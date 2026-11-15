# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Property-based (fuzz) tests of the ARPAV XML parser (no Home Assistant needed).

The parser reads untrusted remote XML: whatever it is given, the only exception
allowed out of it is ``HydroParseError``.
"""

import contextlib
import importlib.util
import math
import pathlib
import sys
from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = pathlib.Path(__file__).resolve().parents[1]

# load the module by path: the package __init__ needs Home Assistant
_spec = importlib.util.spec_from_file_location(
    "arpav_hydro_fuzz", ROOT / "custom_components" / "arpav_meteo_idro" / "hydro.py")
hydro = importlib.util.module_from_spec(_spec)
sys.modules["arpav_hydro_fuzz"] = hydro
_spec.loader.exec_module(hydro)

FUZZ = settings(max_examples=200, deadline=None)

# characters legal in XML 1.0 text (surrogates and control characters excluded)
xml_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs", "Cc"), blacklist_characters="\ufffe\uffff"),
    max_size=30)

STATION_PREFIX = '<?xml version="1.0" encoding="ISO-8859-1"?><CONTENITORE>'

# seeds that make the fuzzer reach the interesting branches quickly
SEED_DOCUMENTS = [
    b"",
    b"<html><body>503</body></html>",
    b"<!DOCTYPE html><html></html>",
    b"<METEOGRAMMI/>",
    b"<CONTENITORE/>",
    b"<CONTENITORE><STAZIONE/></CONTENITORE>",
    b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><CONTENITORE>&b;</CONTENITORE>',
    b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><METEOGRAMMI>&e;</METEOGRAMMI>',
    b"<CONTENITORE><STAZIONE><SENSORE><ID>1</ID><DATI ISTANTE='202611150800'><VM>>></VM></DATI>"
    b"</SENSORE></STAZIONE></CONTENITORE>",
    b"\xff\xfe<\x00C\x00",
]


def _tagged(root: str, children: str) -> str:
    return f"<{root}>{children}</{root}>"


# --- arbitrary input never raises anything but HydroParseError ---------------

@FUZZ
@given(st.binary(max_size=2000))
def test_parse_station_arbitrary_bytes(document):
    """Parse station arbitrary bytes."""
    with contextlib.suppress(hydro.HydroParseError):
        hydro.parse_station(document)


@FUZZ
@given(st.binary(max_size=2000))
def test_parse_registry_arbitrary_bytes(document):
    """Parse registry arbitrary bytes."""
    with contextlib.suppress(hydro.HydroParseError):
        hydro.parse_registry(document)


@FUZZ
@given(st.text(max_size=500))
def test_parsers_arbitrary_text(document):
    """Parsers arbitrary text."""
    for parser in (hydro.parse_station, hydro.parse_registry):
        with contextlib.suppress(hydro.HydroParseError):
            parser(document)


@pytest.mark.parametrize("document", SEED_DOCUMENTS)
@pytest.mark.parametrize("parser_name", ["parse_station", "parse_registry"])
def test_seed_documents(parser_name, document):
    """Seed documents."""
    parser = getattr(hydro, parser_name)
    with contextlib.suppress(hydro.HydroParseError):
        parser(document)


@FUZZ
@given(
    st.sampled_from(SEED_DOCUMENTS),
    st.integers(min_value=0, max_value=200),
    st.binary(max_size=20),
)
def test_mutated_seeds(seed, position, junk):
    """Splice junk into plausible documents: still only HydroParseError."""
    position = min(position, len(seed))
    document = seed[:position] + junk + seed[position:]
    for parser in (hydro.parse_station, hydro.parse_registry):
        with contextlib.suppress(hydro.HydroParseError):
            parser(document)


@FUZZ
@given(st.lists(st.sampled_from(["<A>", "<CONTENITORE>", "<STAZIONE>", "<SENSORE>"]),
                min_size=1, max_size=3000))
def test_deep_nesting(tags):
    """Deep nesting."""
    document = "".join(tags)
    with contextlib.suppress(hydro.HydroParseError):
        hydro.parse_station(document)


def test_oversized_document_is_refused():
    """Oversized document is refused."""
    big = b"<CONTENITORE>" + b" " * hydro.MAX_XML_BYTES + b"</CONTENITORE>"
    for parser in (hydro.parse_station, hydro.parse_registry):
        with pytest.raises(hydro.HydroParseError, match="too large"):
            parser(big)


@FUZZ
@given(st.sampled_from(["<html>", "<HTML lang='it'>", "<!DOCTYPE html>", "<!doctype HTML>"]),
       st.text(max_size=50), st.text(alphabet=" \t\r\n", max_size=5))
def test_html_is_refused(opening, rest, lead):
    """Html is refused."""
    document = f"{lead}{opening}{rest}"
    for parser in (hydro.parse_station, hydro.parse_registry):
        with pytest.raises(hydro.HydroParseError):
            parser(document)
        with pytest.raises(hydro.HydroParseError):
            parser(document.encode("utf-8"))


@FUZZ
@given(st.sampled_from(["parse_station", "parse_registry"]), xml_text)
def test_wrong_root_is_refused(parser_name, tag_text):
    """Wrong root is refused."""
    parser = getattr(hydro, parser_name)
    document = "<ALTRO>" + escape(tag_text) + "</ALTRO>"
    with pytest.raises(hydro.HydroParseError, match="unexpected root"):
        parser(document)


def test_entities_are_not_expanded():
    """Defusedxml refuses entity declarations: no billion laughs, no file access."""
    for document in SEED_DOCUMENTS[6:8]:
        for parser in (hydro.parse_station, hydro.parse_registry):
            with pytest.raises(hydro.HydroParseError):
                parser(document)


# --- primitives ---------------------------------------------------------------

@FUZZ
@given(st.one_of(st.none(), st.text(max_size=60)))
def test_parse_number_total(raw):
    """Parse number total."""
    value = hydro.parse_number(raw)
    assert value is None or (isinstance(value, float) and math.isfinite(value))


@FUZZ
@given(st.floats(allow_nan=False, allow_infinity=False, width=32),
       st.sampled_from(["", " ", "\t"]), st.booleans())
def test_parse_number_round_trip(number, pad, comma):
    """Parse number round trip."""
    text = repr(number)
    if comma:
        text = text.replace(".", ",")
    assert hydro.parse_number(f"{pad}{text}{pad}") == number


@pytest.mark.parametrize("raw", [
    None, "", " ", "\n", ">>", "->", "-", "--", "nan", "NaN", "-nan", "inf", "-inf",
    "Infinity", "1e999", "-1e999", "n/d", "ND",
])
def test_parse_number_sentinels(raw):
    """Parse number sentinels."""
    assert hydro.parse_number(raw) is None


@FUZZ
@given(st.one_of(st.none(), st.text(max_size=40)))
def test_parse_instant_total(raw):
    """Parse instant total."""
    value = hydro.parse_instant(raw)
    assert value is None or (value.tzinfo is not None and value.utcoffset() == timedelta(0))
    if value is not None:
        # only exactly 12 ASCII digits (YYYYMMDDHHMM) are accepted
        assert raw is not None
        assert len(raw.strip()) == 12
        assert all(c in "0123456789" for c in raw.strip())


@FUZZ
@given(st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2100, 12, 31)),
       st.sampled_from(["", " ", "\t"]))
def test_parse_instant_round_trip(local, pad):
    """Parse instant round trip."""
    local = local.replace(second=0, microsecond=0)
    parsed = hydro.parse_instant(f"{pad}{local:%Y%m%d%H%M}{pad}")
    # ARPAV timestamps are solar time: a fixed UTC+1
    assert parsed == (local - timedelta(hours=1)).replace(tzinfo=UTC)
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.parametrize("raw", [None, "", "  ", "2026", "202613010000", "202611152560", "not a date",
                                 "2026-11-15 08:00", "20261115080"])
def test_parse_instant_invalid(raw):
    """Parse instant invalid."""
    assert hydro.parse_instant(raw) is None


# --- station_file ---------------------------------------------------------------

@FUZZ
@given(st.one_of(st.none(), st.text(max_size=30)), st.text(max_size=12))
def test_station_file_never_leaves_the_pattern(link, station_id):
    """Station file never leaves the pattern."""
    try:
        name = hydro.station_file(link, station_id)
    except hydro.HydroParseError:
        return
    assert hydro.STATION_FILE.fullmatch(name)
    assert name.isascii()
    assert "/" not in name
    assert ".." not in name
    # never an URL outside the ARPAV base
    assert hydro.station_url(link, station_id).startswith(f"{hydro.XML_BASE}/")


@FUZZ
@given(st.one_of(st.none(), st.text(max_size=30)), st.integers(min_value=0, max_value=999999))
def test_station_file_with_valid_id_never_fails(link, number):
    """Station file with valid id never fails."""
    name = hydro.station_file(link, str(number))
    assert hydro.STATION_FILE.fullmatch(name)


@pytest.mark.parametrize("link", [
    "../etc/passwd", "../1.xml", "/1.xml", "http://evil.example/1.xml", "1.xml/../2.xml",
    "1.xml\n", "1.xml\nX", "0001.XML", "1234567.xml", "1.xml?x=1", "1.xml#", "١٢٣.xml", ".xml",
    "1.xml\x00", "C:\\1.xml",
])
def test_station_file_rejects_hostile_links(link):
    """Station file rejects hostile links."""
    # the hostile link is ignored and the file name is rebuilt from the station ID
    name = hydro.station_file(link, "7")
    if link.strip() != name:
        assert name == "0007.xml"
    assert hydro.STATION_FILE.fullmatch(name)


@pytest.mark.parametrize("station_id", ["", "abc", "../1", "1234567", "-1", "1.5", "١٢", "1\n2"])
def test_station_file_rejects_invalid_ids(station_id):
    """Station file rejects invalid ids."""
    with pytest.raises(hydro.HydroParseError):
        hydro.station_file(None, station_id)


# --- well-formed documents round-trip -----------------------------------------

value_strategy = st.one_of(
    st.none(),
    st.just(">>"),
    st.just(""),
    st.floats(min_value=-50, max_value=500, allow_nan=False, allow_infinity=False)
    .map(lambda f: round(f, 3)))

instants = st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2099, 12, 31)).map(
    lambda d: d.replace(second=0, microsecond=0))

ids = st.integers(min_value=1, max_value=999999).map(str)
safe_text = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "Zs"), exclude_characters="<>&\"'"),
    min_size=1, max_size=20).map(str.strip).filter(bool)


@st.composite
def sensors(draw):
    """Sensors."""
    sensor_id = draw(ids)
    stype = draw(st.sampled_from([hydro.TYPE_LEVEL, hydro.TYPE_FLOW, "PLUV"]))
    thresholds = draw(st.tuples(*[value_strategy] * 3))
    freq = draw(st.sampled_from([None, 5, 10, 15, 30, 60]))
    points = draw(st.lists(st.tuples(instants, value_strategy), max_size=8,
                           unique_by=lambda p: p[0]))
    return {"id": sensor_id, "type": stype, "thresholds": thresholds, "freq": freq,
            "points": points, "name": draw(safe_text), "unit": draw(safe_text)}


def _fmt(value) -> str:
    return "" if value is None else str(value)


def _render_sensor(sensor: dict, shuffle_seed: int) -> str:
    points = list(sensor["points"])
    # the order of the nodes carries no meaning
    points.sort(key=lambda p: hash((p[0], shuffle_seed)))
    parts = [f"<ID>{sensor['id']}</ID><TYPE>{sensor['type']}</TYPE>",
             f"<PARAMNM>{escape(sensor['name'])}</PARAMNM><UNITNM>{escape(sensor['unit'])}</UNITNM>"]
    if sensor["freq"] is not None:
        parts.append(f"<FREQ>{sensor['freq']}</FREQ>")
    for index, value in enumerate(sensor["thresholds"], start=1):
        parts.append(f"<GUARDIA{index}>{_fmt(value)}</GUARDIA{index}>")
    for instant, value in points:
        parts.append(f'<DATI ISTANTE="{instant:%Y%m%d%H%M}"><VM>{_fmt(value)}</VM></DATI>')
    return "<SENSORE>" + "".join(parts) + "</SENSORE>"


@FUZZ
@given(st.lists(sensors(), max_size=4), ids, safe_text, st.integers(0, 10**6),
       st.sampled_from(["str", "utf8", "latin1"]))
def test_station_round_trip(sensor_list, station_id, name, shuffle_seed, encoding):
    """Station round trip."""
    body = (f"<ISTANTERUN>202611150930</ISTANTERUN><INIZIO>202611120000</INIZIO><FINE>202611151000</FINE>"
            f"<STAZIONE><IDSTAZ>{station_id}</IDSTAZ><NOME>{escape(name)}</NOME><Y>45,5</Y><X>11.25</X>"
            + "".join(_render_sensor(s, shuffle_seed) for s in sensor_list) + "</STAZIONE>")
    text = f'<?xml version="1.0" encoding="ISO-8859-1"?><CONTENITORE>{body}</CONTENITORE>'
    if encoding == "str":
        document = text.replace(' encoding="ISO-8859-1"', "")
    elif encoding == "utf8":
        document = text.replace("ISO-8859-1", "UTF-8").encode("utf-8")
    else:
        try:
            document = text.encode("latin-1")
        except UnicodeEncodeError:
            return
    data = hydro.parse_station(document)

    assert data.station_id == station_id
    assert data.name == name
    assert data.latitude == 45.5
    assert data.longitude == 11.25
    assert data.generated_at == datetime(2026, 11, 15, 8, 30, tzinfo=UTC)
    assert data.start == datetime(2026, 11, 11, 23, 0, tzinfo=UTC)
    assert data.end == datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
    assert [s.sensor_id for s in data.series] == [s["id"] for s in sensor_list]

    for parsed, expected in zip(data.series, sensor_list, strict=True):
        assert parsed.type == expected["type"]
        assert parsed.name == expected["name"]
        assert parsed.unit == expected["unit"]
        assert parsed.frequency_minutes == expected["freq"]
        # missing or blank thresholds are "not published": None, never 0
        assert parsed.thresholds == tuple(
            v if isinstance(v, float) else None for v in expected["thresholds"])
        assert parsed.has_thresholds == all(isinstance(v, float) for v in expected["thresholds"])
        # samples come back sorted, in UTC, with sentinels as None
        expected_samples = sorted(
            ((i - timedelta(hours=1)).replace(tzinfo=UTC), v if isinstance(v, float) else None)
            for i, v in expected["points"])
        assert [(s.observed_at, s.value) for s in parsed.samples] == expected_samples
        assert [s.observed_at for s in parsed.samples] == sorted(s.observed_at for s in parsed.samples)
        assert all(s.value is None for s in parsed.samples if s.raw in (">>", "", None))
        assert all(s.value is not None for s in parsed.valid_samples)


registry_entries = st.lists(
    st.tuples(ids, safe_text, st.one_of(st.none(), st.just(""), safe_text)),
    max_size=8, unique_by=lambda e: e[0])


@FUZZ
@given(registry_entries)
def test_registry_round_trip(entries):
    """Registry round trip."""
    nodes = []
    for station_id, name, link in entries:
        link_xml = "" if link is None else f"<LINKSTAZ>{escape(link)}</LINKSTAZ>"
        nodes.append(f"<STAZIONE><IDSTAZ>{station_id}</IDSTAZ><NOME>{escape(name)}</NOME>"
                     f"<Y>45.1</Y><X>11,9</X>{link_xml}</STAZIONE>")
    document = ('<?xml version="1.0" encoding="UTF-8"?><METEOGRAMMI>'
                + "".join(nodes) + "</METEOGRAMMI>").encode()
    stations = hydro.parse_registry(document)
    assert [s.station_id for s in stations] == [e[0] for e in entries]
    for station, (station_id, name, link) in zip(stations, entries, strict=True):
        assert station.name == name
        assert station.latitude == 45.1
        assert station.longitude == 11.9
        assert hydro.STATION_FILE.fullmatch(station.link)
        assert station.url.startswith(f"{hydro.XML_BASE}/")
        if not (link and hydro.STATION_FILE.fullmatch(link.strip())):
            assert station.link == f"{int(station_id):04d}.xml"


@FUZZ
@given(st.lists(st.tuples(xml_text, xml_text, xml_text), max_size=6))
def test_registry_with_arbitrary_fields(entries):
    """Arbitrary field contents: bad rows are skipped, links are always safe."""
    nodes = "".join(
        f"<STAZIONE><IDSTAZ>{escape(i)}</IDSTAZ><NOME>{escape(n)}</NOME>"
        f"<LINKSTAZ>{escape(link)}</LINKSTAZ></STAZIONE>" for i, n, link in entries)
    try:
        stations = hydro.parse_registry(_tagged("METEOGRAMMI", nodes))
    except hydro.HydroParseError:
        return
    for station in stations:
        assert hydro.STATION_ID.fullmatch(station.station_id)
        assert station.name
        assert hydro.STATION_FILE.fullmatch(station.link)


@FUZZ
@given(st.lists(st.tuples(xml_text, xml_text, xml_text, xml_text), max_size=5))
def test_station_with_arbitrary_fields(entries):
    """Arbitrary field contents inside a valid structure never escape HydroParseError."""
    sensor_xml = "".join(
        f"<SENSORE><ID>{escape(a)}</ID><TYPE>{escape(b)}</TYPE><FREQ>{escape(c)}</FREQ>"
        f'<GUARDIA1>{escape(d)}</GUARDIA1><DATI ISTANTE="{escape(c)}"><VM>{escape(d)}</VM></DATI></SENSORE>'
        for a, b, c, d in entries)
    document = _tagged("CONTENITORE", _tagged("STAZIONE", sensor_xml))
    try:
        data = hydro.parse_station(document)
    except hydro.HydroParseError:
        return
    for series in data.series:
        assert series.sensor_id
        assert all(s.value is None or math.isfinite(s.value) for s in series.samples)

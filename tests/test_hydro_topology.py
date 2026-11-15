# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Regression tests for documented upstream-to-downstream ordering."""

from collections import defaultdict
from pathlib import Path

from custom_components.arpav_meteo_idro.hydro import parse_registry
from custom_components.arpav_meteo_idro.hydro_topology import (
    BACCHIGLIONE_REACHES,
    ordered_selection,
    topology_evidence,
)


def test_bacchiglione_order_uses_the_documented_profile():
    """Exercise the verified order, partial coverage, fallback and overrides."""
    selected = ["0287", "999", "0595", "308", "334", "303", "888", "333", "276"]
    assert ordered_selection(selected, "", "Bacchiglione") == [
        "276", "333", "303", "308", "334", "0595", "0287", "999", "888",
    ]
    assert ordered_selection(["287", "303"], "", "bacchiglione") == ["303", "287"]
    assert ordered_selection(selected, "", "An unprofiled river") == selected
    assert ordered_selection(selected, None, "Bacchiglione") == selected
    assert ordered_selection(selected, "287; 0308, 287, 12", "Bacchiglione") == [
        "0287", "308", "999", "0595", "334", "303", "888", "333", "276",
    ]
    assert ordered_selection(selected, "south", "Bacchiglione") is None


def test_bacchiglione_keeps_diversion_and_confluence_as_reaches():
    """Keep the branches and their evidence in the graph."""
    endpoints = {(reach.upstream, reach.downstream) for reach in BACCHIGLIONE_REACHES}
    assert {("voltabarozzo", "595"), ("voltabarozzo", "san_gregorio_piovego"),
            ("san_gregorio_piovego", "brenta"), ("595", "bovolenta"),
            ("cagnola", "bovolenta")} <= endpoints
    assert len(endpoints) == len(BACCHIGLIONE_REACHES)
    for reach in BACCHIGLIONE_REACHES:
        assert reach.source_url.startswith("https://")
        assert reach.source_reference and reach.verified_on and reach.confidence
    assert topology_evidence("Bacchiglione", "0334").downstream == "voltabarozzo"
    assert topology_evidence("Bacchiglione", "0999") is None
    assert topology_evidence("Brenta", "334") is None


def test_registry_profiles_cover_all_multi_station_water_bodies():
    """Verify coverage of the real registry, including names with ad."""
    fixture = Path(__file__).parent / "fixtures" / "stazioni_idro.xml"
    groups = defaultdict(set)
    for station in parse_registry(fixture.read_bytes()):
        assert station.river
        groups[station.river].add(station.station_id)
    multiple = {river: ids for river, ids in groups.items() if len(ids) > 1}
    unverified = {
        (river, station_id)
        for river, ids in multiple.items()
        for station_id in ids
        if not topology_evidence(river, station_id)
    }
    assert len(multiple) == 23
    assert unverified == {("Po", "319"), ("Po", "552"), ("Po", "561")}


def test_veneto_profiles_follow_reaches_and_keep_po_delta_selection_order():
    """Check main-stem paths, compound place names and ambiguous gauges."""
    cases = {
        "Adige": "607 332 270 301 281 284 293",
        "Brenta": "374 283 302 629 329 646",
        "Canal Bianco": "693 665 666 664",
        "Cordevole": "6 684 649 277 634",
        "Livenza": "400 306 401 294 300",
        "Muson dei Sassi": "554 292 645",
        "Piave": "406 652 651 271 628 661 327 309 316 323 297",
    }
    for river, sequence in cases.items():
        expected = sequence.split()
        assert ordered_selection(expected[::-1], "", river) == expected
    selected = ["552", "562", "561", "560", "399", "319"]
    assert ordered_selection(selected, "", "Po") == ["399", "562", "560", "552", "561", "319"]
    assert ordered_selection(selected, "0561, 0399", "Po") == [
        "561", "399", "552", "562", "560", "319",
    ]
    assert topology_evidence("Piave", "406").source_reference == "WFS v_idrografia_rete, HYDROID 40466 to 25480"


def test_gua_profile_accepts_registry_and_accented_names():
    """Both ARPAV spelling and accented river labels identify the Guà profile."""
    expected = ["313", "317", "555", "304", "295"]
    for river in ("Gua'", "Guà", " GUA’ ", "Gua\u0300"):
        assert ordered_selection(expected[::-1], "", river) == expected
        assert topology_evidence(river, "0313") == topology_evidence("Guà", "313")


def test_canal_bianco_uses_medium_confidence():
    """A regulated route keeps its ordering with documented confidence."""
    for station in ("693", "665", "666", "664"):
        assert topology_evidence("Canal Bianco", station).confidence == "medium"
    assert topology_evidence("Brenta", "374").confidence == "high"

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Regression tests for documented upstream-to-downstream ordering."""

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
    assert ordered_selection(selected, "", "Brenta") == selected
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

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Documented hydrometric topology, independent of the ARPAV XML ordering."""

from dataclasses import dataclass
from graphlib import TopologicalSorter

_ARPAV_MAPS = (
    "https://www.arpa.veneto.it/api/temi-ambientali/idrologia/file-e-allegati/rapporti-e-documenti/"
    "idrologia-regionale/idrologia-regionale-la-rete-idrometrica/misure-di-portata/"
    "rel_0119_misure_q_arpav_2018_00.pdf/@@download/file/@@breadcrumbs"
)
_VOLTABAROZZO = (
    "https://www.comune.padova.it/urbanistica/Varianti_Pi_2021/44_progetto_variante_SIR3/"
    "051_NP00-00-D-Z2-RI-ID0001-001-A.pdf#page=8"
)
_BOVOLENTA = "https://bur.regione.veneto.it/BurvServices/pubblica/DettaglioDgr.aspx?id=523553"


@dataclass(frozen=True)
class Reach:
    """A directed reach of the network with its cartographic evidence."""

    upstream: str
    downstream: str
    source_url: str
    source_reference: str
    verified_on: str = "2026-11-15"
    confidence: str = "high"


BACCHIGLIONE_REACHES = (
    Reach("276", "333", _ARPAV_MAPS, "Tavola 03"),
    Reach("333", "303", _ARPAV_MAPS, "Tavola 03"),
    Reach("303", "308", _ARPAV_MAPS, "Tavola 03"),
    Reach("308", "voltabarozzo", _ARPAV_MAPS, "Tavola 03"),
    Reach("voltabarozzo", "san_gregorio_piovego", _VOLTABAROZZO, "§2.2, figures 6–8"),
    Reach("san_gregorio_piovego", "brenta", _VOLTABAROZZO, "§2.2, figures 6–8"),
    Reach("voltabarozzo", "595", _ARPAV_MAPS, "Tavola 05"),
    Reach("595", "bovolenta", _ARPAV_MAPS, "Tavola 05"),
    Reach("cagnola", "bovolenta", _BOVOLENTA, "DGR 122/2024, Premesse"),
    Reach("bovolenta", "pontelongo", _BOVOLENTA, "DGR 122/2024, Premesse"),
)
# Place these measurements at their named nodes for display. The reach graph
# does not locate the gauge relative to a gate or the exact point of confluence.
_STATION_NODES = {
    "276": "276", "333": "333", "303": "303", "308": "308",
    "334": "voltabarozzo", "595": "595", "287": "bovolenta",
}


def _bacchiglione_profile() -> dict[str, Reach]:
    """List covered stations in topological order with their evidence."""
    graph = TopologicalSorter()
    evidence = {}
    for reach in BACCHIGLIONE_REACHES:
        graph.add(reach.downstream, reach.upstream)
        evidence.setdefault(reach.downstream, reach)
    head = BACCHIGLIONE_REACHES[0]
    evidence[head.upstream] = head
    station_by_node = {node: station for station, node in _STATION_NODES.items()}
    return {
        station_by_node[node]: evidence[node]
        for node in graph.static_order()
        if node in station_by_node
    }


_PROFILES = {"bacchiglione": _bacchiglione_profile()}


def _station_key(station_id: str) -> str:
    """Match padded and unpadded ARPAV IDs without changing the saved ID."""
    return station_id.lstrip("0") or "0"


# public name for the other modules: the same matching of padded and unpadded IDs
station_key = _station_key


def _profile(river: str | None) -> dict[str, Reach]:
    return _PROFILES.get((river or "").strip().casefold(), {})


def ordered_selection(
    selected: list[str], order_text: str | None, river: str | None,
) -> list[str] | None:
    """Apply explicit order, preserved legacy order or verified river order."""
    if order_text is None:
        return list(selected)

    selected_by_key = {_station_key(station_id): station_id for station_id in selected}
    if order_text.strip():
        order = [token.strip() for token in order_text.replace(";", ",").split(",") if token.strip()]
        if any(not token.isdecimal() for token in order):
            return None
        keys = dict.fromkeys(_station_key(token) for token in order)
    else:
        keys = _profile(river)

    ordered = [selected_by_key[key] for key in keys if key in selected_by_key]
    return ordered + [station_id for station_id in selected if station_id not in ordered]


def topology_evidence(river: str | None, station_id: str) -> Reach | None:
    """Return the evidence for a station covered by the named profile."""
    return _profile(river).get(_station_key(station_id))

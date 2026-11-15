# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Documented hydrometric topology, independent of the ARPAV XML ordering."""

from dataclasses import dataclass
from graphlib import TopologicalSorter
from unicodedata import normalize

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


_RIVER_GRAPH_URL = "https://gaia.arpa.veneto.it/layers/idrografia:geonode:v_idrografia_rete"

# Derived from ARPAV, Grafo Idrografia (elemento idrico), CC BY 3.0.
# Each row records the upstream/downstream IDs and the first/last HYDROID
# of the directed path in geonode:v_idrografia_rete (2026-11-15).
# Intermediate vertices were checked in the WFS network, then collapsed.
_VENETO_PATHS = {
    "adige": (
        ("270", "301", 60063, 60316),
        ("332", "270", 843, 60063),
        ("281", "284", 36517, 60085),
        ("301", "281", 60316, 36517),
        ("284", "293", 60085, 31421),
        ("607", "332", 115204, 843),
    ),
    "agno": (
        ("278", "315", 10672, 15698),
    ),
    "alpone": (
        ("273", "322", 28560, 1152),
    ),
    "astico": (
        ("404", "305", 36017, 137800),
    ),
    "biois": (
        ("597", "402", 137218, 40208),
    ),
    "boite": (
        ("214", "682", 18223, 45144),
        ("682", "403", 45144, 18375),
    ),
    "brenta": (
        ("283", "302", 34371, 26633),
        ("374", "283", 14126, 34371),
        ("302", "629", 26633, 10139),
        ("629", "329", 10139, 137775),
        ("329", "646", 137775, 37684),
    ),
    "canal bianco": (
        ("666", "664", 55827, 43843),
        ("665", "666", 40541, 55827),
        ("693", "665", 138295, 40541),
    ),
    "chiampo": (
        ("679", "377", 23292, 138363),
    ),
    "cordevole": (
        ("6", "684", 17368, 41512),
        ("277", "634", 35735, 21187),
        ("649", "277", 24461, 35735),
        ("684", "649", 41512, 24461),
    ),
    "frassine": (
        ("286", "288", 31419, 8105),
    ),
    "fratta": (
        ("325", "330", 9121, 7370),
    ),
    "gorzone": (
        ("291", "328", 60135, 122965),
    ),
    "guà": (
        ("304", "295", 10049, 43456),
        ("555", "304", 8058, 10049),
        ("313", "317", 14026, 35866),
        ("317", "555", 35866, 8058),
    ),
    "livenza": (
        ("294", "300", 138360, 8380),
        ("401", "294", 42051, 138360),
        ("400", "306", 35386, 36837),
        ("306", "401", 36837, 42051),
    ),
    "meschio": (
        ("462", "296", 115241, 42097),
        ("463", "462", 5594, 115241),
    ),
    "monticano": (
        ("298", "310", 6669, 33763),
        ("331", "298", 6940, 6669),
        ("310", "299", 33763, 7468),
    ),
    "muson dei sassi": (
        ("554", "292", 43517, 138298),
        ("292", "645", 138298, 37103),
    ),
    "piave": (
        ("271", "628", 20196, 48144),
        ("651", "271", 38285, 20196),
        ("323", "297", 138362, 37414),
        ("309", "316", 32594, 26615),
        ("327", "309", 138299, 32594),
        ("316", "323", 26615, 138362),
        ("661", "327", 19583, 138299),
        ("406", "652", 40466, 25480),
        ("628", "661", 48144, 19583),
        ("652", "651", 25480, 38285),
    ),
    # Pila and Porto Barricata are on separate branches below the split.
    "po": (
        ("399", "562", 60245, 42269),
        ("562", "560", 42269, 115189),
        ("560", "pila_tolle_junction", 115189, 115196),
        ("pila_tolle_junction", "po_di_pila", 114007, 114007),
        ("pila_tolle_junction", "po_delle_tolle", 7637, 7637),
        ("po_di_pila", "561", 114007, 2242),
        ("po_delle_tolle", "552", 7637, 10042),
    ),
    "posina": (
        ("194", "407", 31597, 115229),
    ),
    "retrone": (
        ("635", "321", 16678, 55642),
    ),
}


def _station_profile(reaches: tuple[Reach, ...], station_nodes: dict[str, str]) -> dict[str, Reach]:
    """List covered stations in topological order with their evidence."""
    graph = TopologicalSorter()
    for reach in reaches:
        graph.add(reach.downstream, reach.upstream)

    evidence = {reach.upstream: reach for reach in reversed(reaches)}
    evidence.update({reach.downstream: reach for reach in reversed(reaches)})
    station_by_node = {node: station for station, node in station_nodes.items()}
    return {
        station_by_node[node]: evidence[node]
        for node in graph.static_order()
        if node in station_by_node
    }


def _cartographic_profile(river: str, paths: tuple[tuple[str, str, int, int], ...]) -> dict[str, Reach]:
    """Build a profile from station-scale paths with traceable WFS endpoints."""
    # The regulated Canal Bianco path establishes order for display; its
    # cartographic direction does not establish the direction of actual flow.
    confidence = "medium" if river == "canal bianco" else "high"
    reaches = tuple(
        Reach(upstream, downstream, _RIVER_GRAPH_URL, f"WFS v_idrografia_rete, HYDROID {first} to {last}",
              confidence=confidence)
        for upstream, downstream, first, last in paths
    )
    station_nodes = {
        node: node for reach in reaches for node in (reach.upstream, reach.downstream) if node.isdecimal()
    }
    return _station_profile(reaches, station_nodes)


_PROFILES = {river: _cartographic_profile(river, paths) for river, paths in _VENETO_PATHS.items()}
_PROFILES["bacchiglione"] = _station_profile(BACCHIGLIONE_REACHES, _STATION_NODES)
# ARPAV lists 319 under Po. Append its independent route after the Po di
# Venezia branches for display. Volta Grimana is a navigation connection, so
# there is no directed reach to this station from Cavanella Po.
_PO_LEVANTE_REACH = Reach(
    upstream="canal_bianco_volta_grimana",
    downstream="319",
    source_url="https://www.agenziapo.it/idrovia/idrovia-fissero-tartaro-canalbianco-po-di-levante",
    source_reference="AIPo, Canal Bianco to Porto Levante via the Po-Brondolo junction",
    confidence="medium",
)
_PROFILES["po"].update(_station_profile((_PO_LEVANTE_REACH,), {"319": "319"}))


def _station_key(station_id: str) -> str:
    """Match padded and unpadded ARPAV IDs without changing the saved ID."""
    return station_id.lstrip("0") or "0"


def _profile(river: str | None) -> dict[str, Reach]:
    key = normalize("NFC", (river or "").strip()).casefold()
    if key in {"gua'", "gua’"}:
        key = "guà"
    return _PROFILES.get(key, {})


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

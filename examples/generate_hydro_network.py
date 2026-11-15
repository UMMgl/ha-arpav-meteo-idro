# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Render the Bacchiglione profile as a PNG for Home Assistant (requires Graphviz)."""

import json
import runpy
import subprocess
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent
TOPOLOGY = EXAMPLES.parent / "custom_components" / "arpav_meteo_idro" / "hydro_topology.py"
OUTPUT = EXAMPLES / "hydro_network_bacchiglione.png"

LABELS = {
    "276": "Ponte Marchese",
    "333": "Vicenza",
    "303": "Longare",
    "308": "Montegalda",
    "voltabarozzo": "Voltabarozzo",
    "san_gregorio_piovego": "San Gregorio / Piovego",
    "brenta": "Brenta",
    "595": "Ponte San Nicolò",
    "bovolenta": "Bovolenta",
    "cagnola": "Cagnola",
    "pontelongo": "Pontelongo",
}


def diagram() -> str:
    """Produce Graphviz input directly from the integration's directed reaches."""
    profile = runpy.run_path(str(TOPOLOGY))
    reaches = profile["BACCHIGLIONE_REACHES"]
    gauges = {node: station for station, node in profile["_STATION_NODES"].items()}
    nodes = dict.fromkeys(node for reach in reaches for node in (reach.upstream, reach.downstream))
    lines = [
        "digraph Bacchiglione {",
        '  graph [bgcolor="#ffffff", pad=0.24, nodesep=0.18, ranksep=0.24, dpi=140];',
        '  node [fontname="DejaVu Sans", fontsize=12, style="rounded,filled", shape=box, '
        'color="#536370", fillcolor="#f1f4f6", fontcolor="#142530", margin="0.12,0.07"];',
        '  edge [color="#39669e", penwidth=1.5, arrowsize=0.7];',
    ]
    for node in nodes:
        name = LABELS[node]
        options = ""
        if node in gauges:
            name = f"{name}\nARPAV {gauges[node]}"
            options = ', color="#0b5f6b", fillcolor="#dcf1f1"'
        lines.append(f'  "{node}" [label={json.dumps(name, ensure_ascii=False)}{options}];')
    for reach in reaches:
        lines.append(f'  "{reach.upstream}" -> "{reach.downstream}";')
    return "\n".join([*lines, "}"])


if __name__ == "__main__":
    subprocess.run(
        ["dot", "-Tpng", "-o", str(OUTPUT)],
        input=diagram().encode("utf-8"),
        check=True,
        timeout=10,
    )

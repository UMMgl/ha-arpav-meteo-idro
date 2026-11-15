# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Generate an example dashboard view for the hydrometric stations of a river.

Usage: python generate_hydro_dashboard.py > hydro_dashboard_bacchiglione.yaml

The charts use the normalized scale of the integration: the first alert
threshold (G1) at 60% and the third (G3) at 90% of the height, so every station
is read against its own thresholds. Requires the ApexCharts card (HACS).
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "arpav_meteo_idro"))
import hydro  # noqa: E402

# station id, device name, thresholds as published by ARPAV (None: not published),
# interim axis ceiling for stations without thresholds. Upstream first.
STATIONS = [
    ("276", "Bacchiglione a Ponte Marchese", (1.0, 2.2, 3.2), None),
    ("333", "Bacchiglione a Vicenza", (3.0, 4.6, 5.4), None),
    ("303", "Bacchiglione a Longare", (3.8, 5.0, 6.3), None),
    ("308", "Bacchiglione a Montegalda", (3.0, 5.5, 6.5), None),
    ("334", "Bacchiglione a Padova Voltabarozzo", None, 10.0),
    ("595", "Bacchiglione a Ponte San Nicolo'", None, None),
    ("287", "Bacchiglione a Bovolenta", (5.5, 6.5, 7.0), None),
]
# entity name of the water level sensor in the language of the installation
# ("water_level" in English, "livello_idrometrico" in Italian)
LEVEL_SUFFIX = "water_level"
COLORS = {"below": "#1e88e5", "g1": "#fbc02d", "g2": "#ef6c00", "g3": "#c62828"}


def slug(text: str) -> str:
    """Return the entity id slug Home Assistant derives from a name."""
    out = "".join(c.lower() if c.isalnum() else "_" for c in text)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def chart(name, thresholds, ceiling, span="24h", height=260):
    """Return an ApexCharts card for a station."""
    entity = f"sensor.{slug(name)}_{LEVEL_SUFFIX}"

    def series(label, color, opacity, transform=None, main=False):
        s = {"entity": entity, "name": label, "type": "area", "color": color, "opacity": opacity,
             "stroke_width": 2 if main else 0, "curve": "stepline", "fill_raw": "last",
             "group_by": {"func": "last", "duration": "10min", "fill": "last"}}
        if transform:
            s["transform"] = transform
            s["show"] = {"in_header": False, "in_legend": False}
        return s

    all_series = [series("Livello", COLORS["below"], 0.35, main=True)]
    axis = {"decimals": 2, "show": False}
    apex = {"legend": {"show": False}, "plotOptions": {"area": {"fillTo": "end"}}, "chart": {"height": height}}
    normalized = hydro.chart_axis(thresholds) if thresholds else None
    if normalized:
        # soft bounds: the scale grows only if the level leaves it
        axis.update(min=f"~{normalized[0]}", max=f"~{normalized[1]}")
        for value, key in zip(thresholds, ("g1", "g2", "g3"), strict=True):
            all_series.append(series(f">= {value}", COLORS[key], 0.55, transform=f"return x >= {value} ? x : null;"))
        apex["annotations"] = {"yaxis": [
            {"y": v, "borderColor": COLORS[k], "strokeDashArray": 4,
             "label": {"text": k.upper(), "style": {"background": COLORS[k], "color": "#fff"}}}
            for v, k in zip(thresholds, ("g1", "g2", "g3"), strict=True)]}
    else:
        axis.update(min="|-0.5|", max=f"~{ceiling}" if ceiling else "|+0.5|")
    return {"type": "custom:apexcharts-card", "graph_span": span, "update_interval": "5min",
            "header": {"show": True, "title": name.split(" a ", 1)[-1], "show_states": True},
            "series": all_series, "yaxis": [axis], "apex_config": apex}


TABLE = """{%- set dot = {'below_g1':'#2e7d32','g1_g2':'#fbc02d','g2_g3':'#ef6c00','above_g3':'#c62828'} -%}
{%- set arrow = {'rising':'mdi:arrow-top-right-thick','steady':'mdi:arrow-right-thick','falling':'mdi:arrow-bottom-right-thick'} -%}
| Stazione | Livello | Stato | Trend |
|---|---:|:---:|:---:|
{% for s in states.sensor | selectattr('attributes.source', 'defined') | selectattr('attributes.source', 'eq', 'arpav_hydrometric_station') | selectattr('attributes.display_order', 'defined') | sort(attribute='attributes.display_order') -%}
{%- set d = s.attributes.level_change_m -%}
| <small>{{ (s.attributes.station_name or s.name).split(' a ')[-1] }}</small> | <small>{{ '%.2f' | format(s.attributes.level_m) if s.attributes.level_m is number else '—' }}</small> | <font size="4" color="{{ dot.get(s.state, '#9e9e9e') }}">{{ '◯' if s.state in ['stale', 'missing'] else '⬤' }}</font> | {% if s.attributes.trend %}<ha-icon icon="{{ arrow[s.attributes.trend] }}"></ha-icon>{% if s.attributes.trend != 'steady' and d is number %} <small>{{ '%+.0f' | format(d * 100) }}</small>{% endif %}{% else %}—{% endif %} |
{% endfor %}"""

view = {
    "title": "Bacchiglione",
    "path": "bacchiglione",
    "type": "sections",
    "max_columns": 4,
    "sections": [
        {"type": "grid", "column_span": 2, "cards": [
            {"type": "heading", "heading": "Livelli ARPAV (monte → valle)"},
            {"type": "markdown", "content": TABLE},
            {"type": "markdown", "content": "<small>Fonte: ARPAV, dati automatici non validati, CC BY 4.0. Non è un servizio di allerta.</small>"}]},
        {"type": "grid", "column_span": 4, "cards": [
            {"type": "heading", "heading": "Ultime 24 ore, dalla sorgente alla foce"},
            {"type": "horizontal-stack", "grid_options": {"columns": "full"},
             "visibility": [{"condition": "screen", "media_query": "(min-width: 768px)"}],
             "cards": [chart(n, t, c) for _, n, t, c in STATIONS]},
            *[dict(chart(n, t, c, height=170), grid_options={"columns": "full"},
                   visibility=[{"condition": "screen", "media_query": "(max-width: 767px)"}])
              for _, n, t, c in STATIONS]]},
    ],
}

if __name__ == "__main__":
    try:
        import yaml
        sys.stdout.write("# Generated by examples/generate_hydro_dashboard.py\n")
        sys.stdout.write(yaml.safe_dump(view, allow_unicode=True, sort_keys=False, width=200))
    except ImportError:  # JSON is valid YAML
        sys.stdout.write(json.dumps(view, ensure_ascii=False, indent=2))

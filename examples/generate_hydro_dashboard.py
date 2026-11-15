# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Generate example dashboard views for the hydrometric stations of a river.

Usage: python generate_hydro_dashboard.py [--lang en|it] [--full] > view.yaml

* basic: table, 24-hour charts and 72-hour hourly Recorder means
* --full: also legend, alert badges and a period selector (last hour / day /
  week / month), which needs the helper of ``helpers_bacchiglione.yaml``
* --lang: entity IDs as created by Home Assistant in that language

The charts use the normalized scale of the integration: the first alert
threshold (G1) at 60% and the third (G3) at 90% of the height, so every station
is read against its own thresholds. Missing measurements stay visible as gaps.
Requires the ApexCharts card (HACS).
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
# entity names in the language of the installation
SUFFIXES = {
    "en": {"level": "water_level", "status": "status"},
    "it": {"level": "livello_idrometrico", "status": "stato"},
}
LEVEL_SUFFIX = SUFFIXES["en"]["level"]
COLORS = {"below": "#1e88e5", "g1": "#fbc02d", "g2": "#ef6c00", "g3": "#c62828"}
PERIOD_HELPER = "input_select.bacchiglione_periodo_grafici"
# label, graph span, grouping of the states, hourly Recorder means
PERIODS = [
    # a grouping is needed in the last hour too: a level that did not change
    # may return no point at all, and ApexCharts fails drawing the thresholds
    ("Ultima ora", "1h", {"func": "last", "duration": "5min", "fill": "last"}, False),
    ("Ultimo giorno", "24h", {"func": "last", "duration": "10min", "fill": "null"}, False),
    ("Ultima settimana", "7d", {"func": "avg", "duration": "30min", "fill": "null"}, False),
    ("Ultimo mese", "30d", None, True),
]


def slug(text: str) -> str:
    """Return the entity id slug Home Assistant derives from a name."""
    out = "".join(c.lower() if c.isalnum() else "_" for c in text)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def chart(name, thresholds, ceiling, span="24h", height=260, hourly=False, group_by=PERIODS[1][2]):
    """Return an ApexCharts card for a station."""
    entity = f"sensor.{slug(name)}_{LEVEL_SUFFIX}"

    def series(label, color, opacity, transform=None, main=False):
        s = {"entity": entity, "name": label, "type": "area", "color": color, "opacity": opacity,
             "stroke_width": 2 if main else 0, "curve": "stepline", "fill_raw": "null"}
        if hourly:
            s["statistics"] = {"type": "mean", "period": "hour", "align": "start"}
        elif group_by:
            s["group_by"] = group_by
        if transform:
            s["transform"] = transform
            s["show"] = {"in_header": False, "in_legend": False}
        return s

    all_series = [series("Media oraria" if hourly else "Livello", COLORS["below"], 0.35, main=True)]
    axis = {"decimals": 2, "show": False}
    apex = {"legend": {"show": False}, "plotOptions": {"area": {"fillTo": "end"}}, "chart": {"height": height}}
    normalized = hydro.chart_axis(thresholds) if thresholds else None
    if normalized:
        # soft bounds: the scale grows only if the level leaves it
        axis.update(min=f"~{normalized[0]}", max=f"~{normalized[1]}")
        if not hourly:
            for value, key in zip(thresholds, ("g1", "g2", "g3"), strict=True):
                all_series.append(series(f">= {value}", COLORS[key], 0.55,
                                         transform=f"return x !== null && x >= {value} ? x : null;"))
        apex["annotations"] = {"yaxis": [
            {"y": v, "borderColor": COLORS[k], "strokeDashArray": 4,
             "label": {"text": k.upper(), "style": {"background": COLORS[k], "color": "#fff"}}}
            for v, k in zip(thresholds, ("g1", "g2", "g3"), strict=True)]}
    else:
        axis.update(min="|-0.5|", max=f"~{ceiling}" if ceiling else "|+0.5|")
    # no update_interval: a card created hidden (period selector, phone/wide
    # layout) would wait for the interval before loading and show N/A; without
    # it the card loads at once and refreshes on every new state of the sensor
    return {"type": "custom:apexcharts-card", "graph_span": span,
            "header": {"show": True, "title": name.split(" a ", 1)[-1], "show_states": not hourly},
            "series": all_series, "yaxis": [axis], "apex_config": apex}


TABLE = """{%- set dot = {'below_g1':'#2e7d32','g1_g2':'#fbc02d','g2_g3':'#ef6c00','above_g3':'#c62828'} -%}
{%- set arrow = {'rising':'mdi:arrow-top-right-thick','steady':'mdi:arrow-right-thick','falling':'mdi:arrow-bottom-right-thick'} -%}
| Stazione | Livello | Stato | Età (min) | Trend |
|---|---:|:---:|---:|:---:|
{% for s in states.sensor | selectattr('attributes.source', 'defined') | selectattr('attributes.source', 'eq', 'arpav_hydrometric_station') | selectattr('attributes.display_order', 'defined') | selectattr('attributes.station_id', 'in', STATION_IDS) | sort(attribute='attributes.display_order') -%}
{%- set d = s.attributes.level_change_m -%}
| <small>{{ (s.attributes.station_name or s.name).split(' a ')[-1] }}</small> | <small>{{ '%.2f' | format(s.attributes.level_m) if s.attributes.level_m is number else '—' }}</small> | <font size="4" color="{{ dot.get(s.state, '#9e9e9e') }}">{{ '◯' if s.state in ['stale', 'missing'] else '⬤' }}</font> | {{ s.attributes.age_minutes | round(0) | int if s.attributes.age_minutes is number else '—' }} | {% if s.attributes.trend %}<ha-icon icon="{{ arrow[s.attributes.trend] }}"></ha-icon>{% if s.attributes.trend != 'steady' and d is number %} <small>{{ '%+.0f' | format(d * 100) }}</small>{% endif %}{% else %}—{% endif %} |
{% endfor %}""".replace("STATION_IDS", json.dumps([station[0] for station in STATIONS]))

SOURCE = "<small>Fonte: ARPAV, dati automatici non validati, CC BY 4.0. Non è un servizio di allerta.</small>"
LEGEND = (
    "<small>**Grafici**: area blu sotto G1, gialla oltre G1, arancione oltre G2, rossa oltre G3; "
    "scala normalizzata con G1 al 60% e G3 al 90% dell'altezza (si allarga se il livello esce); "
    "i buchi sono misure mancanti.<br>"
    '**Stato**: <font color="#2e7d32">⬤</font> sotto G1 · <font color="#fbc02d">⬤</font> G1–G2 · '
    '<font color="#ef6c00">⬤</font> G2–G3 · <font color="#c62828">⬤</font> da G3 · '
    '<font color="#9e9e9e">⬤</font> soglie non pubblicate · <font color="#9e9e9e">◯</font> dato mancante o vecchio.<br>'
    "**Trend**: ultime 4 misure; freccia inclinata e variazione in cm da ±5 cm.<br>"
    "Livelli rispetto allo zero idrometrico locale: non confrontabili tra stazioni. "
    "Stazioni monitorate mostrate da monte a valle (ordine candidato).<br>"
    "_Fonte: ARPAV, dati automatici non validati, CC BY 4.0. Non è un servizio di allerta._</small>"
)
WIDE = {"condition": "screen", "media_query": "(min-width: 768px)"}
NARROW = {"condition": "screen", "media_query": "(max-width: 767px)"}


def chart_rows(span="24h", group_by=PERIODS[1][2], hourly=False, extra=()):
    """Charts side by side on wide screens, stacked on phones."""
    return [
        {"type": "horizontal-stack", "grid_options": {"columns": "full"}, "visibility": [*extra, WIDE],
         "cards": [chart(n, t, c, span, 260, hourly, group_by) for _, n, t, c in STATIONS]},
        *[dict(chart(n, t, c, span, 170, hourly, group_by), grid_options={"columns": "full"},
               visibility=[*extra, NARROW]) for _, n, t, c in STATIONS],
    ]


def recorder_section():
    """Hourly Recorder means, including the hours recovered by the archive action."""
    return {"type": "grid", "column_span": 4, "cards": [
        {"type": "heading", "heading": "Ultime 72 ore, medie orarie dal Recorder"},
        *[chart(n, t, c, span="72h", height=190, hourly=True) for _, n, t, c in STATIONS],
    ]}


def build_view(lang="en", full=False):
    """Return the view for a language, basic or full."""
    global LEVEL_SUFFIX
    LEVEL_SUFFIX = SUFFIXES[lang]["level"]
    status = SUFFIXES[lang]["status"]
    table = [{"type": "heading", "heading": "Livelli ARPAV (monte → valle)"}, {"type": "markdown", "content": TABLE}]
    if not full:
        return {
            "title": "Bacchiglione", "path": "bacchiglione", "type": "sections", "max_columns": 4,
            "sections": [
                {"type": "grid", "column_span": 2, "cards": [*table, {"type": "markdown", "content": SOURCE}]},
                {"type": "grid", "column_span": 4, "cards": [
                    {"type": "heading", "heading": "Ultime 24 ore, stazioni monitorate da monte a valle"},
                    *chart_rows()]},
                recorder_section(),
            ],
        }
    charts = []
    for label, span, group_by, hourly in PERIODS:
        charts += chart_rows(span, group_by, hourly,
                             extra=[{"condition": "state", "entity": PERIOD_HELPER, "state": label}])
    badges = [
        {"type": "entity", "entity": f"sensor.{slug(n)}_{status}", "name": n.split(" a ", 1)[-1],
         "show_name": True, "show_state": True, "icon": "mdi:alert", "color": color,
         "visibility": [{"condition": "state", "entity": f"sensor.{slug(n)}_{status}", "state": band}]}
        for _, n, t, _c in STATIONS if t
        for band, color in (("g1_g2", "amber"), ("g2_g3", "orange"), ("above_g3", "red"))
    ]
    return {
        "title": "Bacchiglione", "path": "bacchiglione", "type": "sections", "max_columns": 4, "badges": badges,
        "sections": [
            {"type": "grid", "column_span": 2, "cards": table},
            {"type": "grid", "column_span": 2, "cards": [
                {"type": "heading", "heading": "Legenda", "heading_style": "subtitle"},
                {"type": "markdown", "content": LEGEND}]},
            {"type": "grid", "column_span": 4, "cards": [
                {"type": "heading", "heading": "Stazioni monitorate da monte a valle (con soglie)"},
                {"type": "tile", "entity": PERIOD_HELPER, "name": "Periodo", "hide_state": True,
                 "features": [{"type": "select-options"}], "features_position": "inline",
                 "grid_options": {"columns": 12}},
                *charts]},
            recorder_section(),
        ],
    }


if __name__ == "__main__":
    lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "en"
    view = build_view(lang, "--full" in sys.argv)
    header = ("# Generated by examples/generate_hydro_dashboard.py " + " ".join(sys.argv[1:])).rstrip() + "\n"
    try:
        import yaml
        sys.stdout.write(header + yaml.safe_dump(view, allow_unicode=True, sort_keys=False, width=200))
    except ImportError:  # JSON is valid YAML
        sys.stdout.write(header + json.dumps(view, ensure_ascii=False, indent=2))

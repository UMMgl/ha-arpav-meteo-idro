# ARPAV Meteo e Idro – ARPAV weather and hydrometric stations for Home Assistant
Home Assistant unofficial integration for ARPAV (Veneto) weather (current conditions and forecast bulletins) and hydrometric stations (river water levels, alert thresholds, trend and history).

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
[![Community Forum][forum-shield]][forum]
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/16742/badge)](https://www.bestpractices.dev/projects/16742)

> **Fork notice** – This is a fork of [davidecavestro/arpa-veneto-weather](https://github.com/davidecavestro/arpa-veneto-weather) by Davide Cavestro, who wrote the weather part (© 2024, BSD 3-Clause). The ARPAV **hydrometric stations** part (river water levels, alert thresholds, trend and long-term history) is by Gianluca Nardin ([@UMMgl](https://github.com/UMMgl)) (© 2026, Apache-2.0). See [Credits and licensing](#credits-and-licensing).


This integration adds support for retrieving the Forecast data from the
[Arpav bulletin endpoint](https://api.arpa.veneto.it/REST/v1/bollettini_meteo_simboli_en)
and current conditions from
[Arpav meteogram endpoint](https://api.arpa.veneto.it/REST/v1/meteo_meteogrammi_tabella).

For this integration you must choose an Arpav forecast zone for forecast data and a weather station for current conditions.

#### This integration will set up the following platforms.

Platform | Description
-- | --
`weather` | A Home Assistant `weather` entity, with current data and twice-daily forecast data (weather locations).
`sensor` | Home Assistant `sensor` entities, with all available sensor data from the API (weather locations); water level, observation time, status, trend and level change of each station (hydrometric stations, see [below](#hydrometric-stations-river-water-levels)).


## Installation through HACS

1. In HACS, open **Custom repositories**, add `UMMgl/ha-arpav-meteo-idro` and choose **Integration**.
2. Open **ARPAV Meteo e Idro** in HACS, download the latest release and restart Home Assistant.
3. In Home Assistant, open **Settings → Devices & services → Add integration** and choose **ARPAV Meteo e Idro**.
4. Choose **Hydrometric stations** to add a river and its stations, or **Weather location** to configure weather.

## Manual installation

Download `ha-arpav-meteo-idro.zip` from the [latest release](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/latest). Extract its contents into `custom_components/arpav_meteo_idro/` under your Home Assistant configuration directory, restart Home Assistant and follow steps 3 and 4 above.

## Configuration

For a **Weather location**, the setup wizard asks for:

  | Parameter | Required | Default Value | Description |
  | --------- | -------- | ------------- | ----------- |
  | `Comune ID` | Yes | None | Set the municipality to use for the *forecast zone lookup*, based on [synthetic forecast by zone](https://meteo.arpa.veneto.it/?page=comuni_geo). |
  | `Zone ID` | Yes | None | Set the *forecast zone*. |
  | `Station ID` | Yes | None | Choose the Weather Station for getting *current conditions* among the available ones. Check [the meteo variables page](https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/meteo-idro-nivo/variabili_meteo). |

- Complete the wizard to save your data.
  If all goes well you should now have a new Weather entity with data from Arpav Forecast

> [!TIP]
You can configure multiple instances of the Integration, so properly name them to avoid confusion.

### Preferences

Once you have configured a station, you can control some options from ⚙ (its _Configure_ action):

- **Expose JSON extra attribute for internal forecast data**: Expose additional attributes on the weather entity used internally for forecasts
- **Expose JSON extra attribute for raw original forecast data**: Expose additional attributes on the weather entity based on the data obtained from the remote api call
- **Expose extra attributes for raw original sensor data**: Expose as sensors the data obtaining from the remote api call
- **Compute the current condition**: Expose the weather state as computed from available metrics
- **Choose stations providing air-quality data**: Since the set of [stations differs](https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/aria/qualita-aria-dati-in-diretta) between PM10, PM2.5 and Ozone, the user can choose a specific station for each of them. 
- **Current condition during the day**: Choose which source describes the sky while the sun is above the horizon
- **Current condition at night**: Choose which source describes the sky while the sun is below the horizon
- **Additional observations**: Optionally choose an aerodrome publishing METAR reports, to observe the sky and to complete the data the chosen station does not provide

## Compute the current weather condition

Since the stations don't provide data for current sky condition, the weather
state has been historically left to _Unknown_.
Since v0.5 this integration optionally computes the current sky condition
with a best-effort approach based on available sensors:
<dl>
<dt>
day - sun above the horizon
</dt>
<dd>
it compares the actual sunlight (Global Horizontal Irradiance) with the maximum expected
for the current sun position, as its elevation over the horizon and the azimuth actually reflects
the <i>latitude</i>, the <i>season</i> and the <i>time</i> of the day.<br>
Based on the nearest realtime data available for <a href="https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/meteo-idro-nivo/variabili_meteo">solar radiation</a>.
It also uses data such as <i>precipitation</i>, <i>wind speed</i> and <i>visibility</i> to make
the best possible estimate of the actual sky conditions.
</dd>
<dt>
night - sun below the horizon
</dt>
<dd>
it compares the actual night sky brightness with the maximum expected, based on the moon phase.<br>
Based on the realtime data available from the nearest station for the <a href="https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/luminosita-del-cielo/brillanza">night sky brightness</a>:
please note that this measure is not typically supplied directly by the chosen station, so we have to fallback to the nearest station providing this data.
</dd>
</dl>

> [!NOTE]
The current weather condition computation is enabled by default since v0.12.<br>
In order to disable it, go to <i>Settings > Devices & services > ARPAV Meteo e Idro</i>.<br>
Click on the gear on the station you are interested in.<br>
Then choose <i>Compute the current condition: &gt; <b>Don't compute</b></i>.

> [!TIP]
Choose  <i>Compute the current condition</i>: <i>From sensors
using custom thresholds</b></i> to set custom thresholds
for separately switching between <i>clear</i>, <i>partly cloudy</i> and <i>cloudy</i>
during day and night.

### The current condition during the day

Solar radiation is measured by the station itself, so where it is available the
daytime sky is inferred from a local, near real-time measurement, and that stays
the default. It is not available everywhere though: **92 of the 223 stations of
the MGRAMMI network carry no pyranometer**, and for those the daytime condition
would be `unknown` all day long, every day. The sun very low over the horizon is
the same problem for a shorter while, since the ratio between the measured and
the expected irradiance means little around sunrise and sunset.

The choice is therefore left to the user, under _Current condition during the
day_:

| Option | Behaviour |
| ------ | --------- |
| _Solar radiation only_ | The default, and the historical behaviour: use the irradiance ratio, and leave the condition unknown when the station measures no radiation |
| _Solar radiation, METAR observation as a fallback_ | Use the irradiance ratio when available, otherwise the cloud cover observed by the configured aerodrome. Both are observations, so no forecast is ever served |
| _METAR observation, forecast as a fallback_ | Always use the aerodrome, and the bulletin when no report is available: for a station whose nearest aerodrome is closer, or more representative, than its own pyranometer |
| _Forecast bulletin_ | Always use the bulletin |
| _Leave it unknown_ | Report no condition unless the station measurements alone decide it (rain, fog, wind) |

### The current condition at night

The night is the harder part, because no single source works everywhere:

- the **night sky brightness** network publishes its readings in a single daily
  batch (around 09:30, standard time), so at night the latest reading normally
  describes the *previous* night rather than the current one, and is discarded
  as stale;
- the **forecast bulletin** is always available and covers the whole region, but
  it is a forecast, not an observation;
- a **METAR** report is an actual observation of the sky, published every 30
  minutes, but it comes from the nearest aerodrome, which may be tens of
  kilometres away;
- some setups are better off with **no value at all** than with a value that is
  not measured.

The choice is therefore left to the user, under _Current condition at night_:

| Option | Behaviour |
| ------ | --------- |
| _Sky brightness, forecast as a fallback_ | The default, and the historical behaviour: use the brightness reading when it is fresh enough, otherwise the bulletin |
| _Sky brightness only_ | Use the brightness reading when fresh, otherwise leave the condition unknown |
| _METAR observation, forecast as a fallback_ | Use the cloud cover observed by the configured aerodrome, and the bulletin when no report is available |
| _Forecast bulletin_ | Always use the bulletin |
| _Leave it unknown_ | Report no condition unless the station measurements alone decide it (rain, fog, wind) |

Whatever the choice, the weather entity says which one was used through its
`condition_source` attributes: see [Data provenance](#data-provenance).

## Additional observations

ARPAV stations do not observe the state of the sky, and several of them report
neither visibility nor pressure: those sensors stay `unknown`. Aerodromes do
observe all of it, and publish a
[METAR](https://en.wikipedia.org/wiki/METAR) report every 30 minutes, with cloud
cover reported layer by layer.

Under _Additional observations_ you can select one, from the list of aerodromes
around the station, **sorted by distance**. When configured, it provides:

- the **cloud coverage** of the weather entity, as a percentage of the sky;
- the **current condition**, day or night, if you selected one of the METAR
  options above;
- any value **missing** from the chosen ARPAV station, typically visibility and
  pressure, unless you turn that off.

Values taken from a METAR are marked with `source: metar`, so they can always
be told apart from the ones measured by the ARPAV station.

> [!IMPORTANT]
Distance matters more than it seems: an aerodrome 60 km away describes the
general state of the sky well, and local fog or low stratus poorly, which in the
Po valley is exactly the typical winter situation. The distance of each
aerodrome is shown in the selection list.

> [!TIP]
Not every aerodrome reports around the clock: the smaller ones only publish
during their opening hours, and the list says which ones are reporting at the
moment. Choosing one is perfectly fine — reports older than 90 minutes are
ignored, so outside those hours the values simply go back to being missing and
the night condition falls back to whatever you configured. A nearby aerodrome
reporting only by day can still be a better choice than a distant one reporting
always.

> [!NOTE]
Reports are retrieved from the
[Aviation Weather Center](https://aviationweather.gov/data/api/) of the US
National Weather Service, which requires no credentials, and are fetched at most
once every 10 minutes, since a METAR is issued every 30.

## Hydrometric stations (river water levels)

*Fork addition.* Besides weather locations, the integration can add the ARPAV
**hydrometric stations** of a river. Add the integration again and choose
**Hydrometric stations**, then the river and its stations. Automatic order
covers 89 stations across the 23 ARPAV water bodies with multiple gauges in
the 15 November 2026 registry. See the [profile coverage and sources](docs/hydro_topology.md).
Other selected stations follow in their selected order. Rivers without a profile
use the selected order throughout.

Since 0.16.0 the display order cannot be set by hand: the manual order field
of 0.15.x was removed and entries that had one are migrated to the verified
profile (see the changelog). Stations not covered by a profile follow the
profiled ones in the order they were selected.

The status sensor exposes `display_order_source`: `topology` for a station
covered by the documented profile, `selection` for any other station.
`topology_status: verified` means the same thing as `topology`.
The source URL, document reference, verification date and confidence are
available in the status attributes of covered stations. The [Bacchiglione
profile](custom_components/arpav_meteo_idro/hydro_topology.py) represents the
Voltabarozzo diversion towards the Brenta and the Cagnola confluence at Bovolenta.
The two gauges at those junctions are placed at the named nodes for display.
The reach between Montegalda and Voltabarozzo summarizes the main connection
through Bassanello. The [SIR3 hydrological report (§2.2, figures 6–7)](https://www.comune.padova.it/urbanistica/Varianti_Pi_2021/44_progetto_variante_SIR3/051_NP00-00-D-Z2-RI-ID0001-001-A.pdf#page=8)
shows the additional urban Padova and Canale Battaglia branches, which are
outside this station-ordering profile.

Source: the ARPAV open-data XML files (`stazioni_idro.xml` and one
`<IDSTAZ>.xml` per station under `https://meteo.arpa.veneto.it/meteo/dati_meteo/xml/`),
read every 5 minutes. ARPAV publishes in batches, usually 20-60 minutes after
the observation.

Each station is a device with these sensors:

| Sensor | Meaning |
|---|---|
| Water level | Last valid reading, in m, relative to the **local hydrometric zero** of the station: levels of different stations are not comparable and can be negative |
| Observed at | Time of that reading (ARPAV solar time, a fixed UTC+1, converted to UTC). Diagnostic, disabled by default on new installations |
| Status | `below_g1`, `g1_g2`, `g2_g3`, `above_g3` against the alert thresholds (GUARDIA1/2/3) published for the series; `no_thresholds` when ARPAV publishes none; `stale` when the reading is older than the staleness limit; `missing` when there is no valid reading |
| Trend | `rising`, `steady`, `falling`: least squares change over the last 4 valid readings, rising or falling from the threshold (default 5 cm) |
| Level change | That change, in m. Disabled by default on new installations (also available as `level_change_m` on the Status sensor) |

The Status sensor also exposes `guardia1_m`/`guardia2_m`/`guardia3_m` (null when
not published, never 0), `quality`, `age_minutes`, `last_sample_valid`,
`display_order`, `display_order_source`, `topology_status`, `latitude` and
`longitude`. Covered stations include `topology_source_url`,
`topology_source_reference`, `topology_verified_on` and `topology_confidence`.
The Status sensor also shows `acquisition_status`, `last_successful_acquisition` and `next_retry_at` when
applicable. Every sensor exposes `station_id`,
`sensor_id`, `source_url` and `source_observed_at`.

#### The 24-hour sample attribute

ARPAV station files hold one sample every 10 minutes (30 for some stations) for
the last 2-3 days, but a sensor state is a single value and the imported history
is hourly. To draw every sample, the **Water level** sensor exposes the last 24
hours as the attribute `samples_24h`:

```yaml
samples_24h:
  - ["2026-11-15T06:00:00+00:00", 1.43]
  - ["2026-11-15T06:10:00+00:00", 1.44]
  # ...
```

* A list of `[timestamp, value]` pairs, oldest first; timestamps are ISO 8601
  UTC, values in m rounded to the millimetre.
* The window ends at the newest valid sample, so a station that stopped
  publishing still shows what it last measured. Sentinels (`>>`) are left out
  (a gap, never a 0); negative levels are kept.
* Bounded: at most 288 points (about 12 kB), whatever the file holds; a 10-minute
  station gives 145 or fewer.
* **Not stored by the Recorder** (`_unrecorded_attributes`): it is live data for
  charts and does not grow the database. It is therefore only available for the
  last 24 hours; longer periods use the Recorder (hourly means).

Rules applied to the data: series are selected by `TYPE` and `ID`, never by
position; readings are sorted by time; sentinels such as `>>` are skipped and
never turned into 0; when the last sample is invalid the previous valid value is
kept and `quality` is `last_sample_invalid`; thresholds are never borrowed from a
nearby station.

### Completing the level history

Home Assistant cannot back-date states, but it can import statistics. Once a
day (03:20), at start-up and through the `arpav_meteo_idro.archive_hydro_history`
action, the hourly mean/min/max of the last 2-3 days that ARPAV still publishes
are written into the **statistics of the Water level sensor** of each station.
Missing hours are filled when ARPAV provides a complete set of observations.
Existing rows are preserved. Only hours ending at least an hour earlier are
eligible. Automatic recovery can be disabled in the options.

### Example dashboards

> **Requirements:** the example views need two HACS frontend cards, the
> [ApexCharts card](https://github.com/RomRider/apexcharts-card) and
> [card-mod](https://github.com/thomasloven/lovelace-card-mod) (HACS → Frontend
> → search the name → Download, then reload the browser). card-mod is new in
> these examples.

Ready views in [`examples/`](examples), generated by
[`examples/generate_hydro_dashboard.py`](examples/generate_hydro_dashboard.py)
(`--lang en|it`, `--full`):

| File | Content | Entity IDs |
|---|---|---|
| [`hydro_dashboard_bacchiglione.yaml`](examples/hydro_dashboard_bacchiglione.yaml) | table, 24-hour charts (10-minute samples), 72-hour hourly Recorder means | English |
| [`hydro_dashboard_bacchiglione_it.yaml`](examples/hydro_dashboard_bacchiglione_it.yaml) | table, 24-hour charts (10-minute samples), 72-hour hourly Recorder means | Italian |
| [`hydro_dashboard_bacchiglione_full.yaml`](examples/hydro_dashboard_bacchiglione_full.yaml) | + legend, alert badges, period selector (hour/day/week/month) | English |
| [`hydro_dashboard_bacchiglione_full_it.yaml`](examples/hydro_dashboard_bacchiglione_full_it.yaml) | + legend, alert badges, period selector (hour/day/week/month) | Italian |

The table lists the configured stations of the river (level, status dot, age of
the observation, trend arrow, read from the Status sensor attributes); the
charts show the monitored stations upstream to downstream, side by side on wide
screens and stacked on phones, with missing measurements left as gaps. The
24-hour charts draw every 10-minute sample from the `samples_24h` attribute
through the ApexCharts `data_generator` (the other periods of the full views
use the Recorder). The 72-hour view shows hourly means from the Recorder, including recovered hours.
The full views need the helper in
[`helpers_bacchiglione.yaml`](examples/helpers_bacchiglione.yaml). To use one:
create a dashboard, open the raw configuration editor of a view and paste the
file (or add it as a view of an existing dashboard).

Two details of the views are deliberate:

* **Conditional charts are grouped.** The charts shown only for a period or a
  screen width sit inside a `vertical-stack` (phones, below 768 px) or a
  `horizontal-stack` (from 768 px), and the `visibility` conditions are on that
  container, never on an ApexCharts card. An ApexCharts card with its own
  `visibility` that is hidden when the view loads is created and detached before
  it finishes its first load, and it never draws when it is shown later (an
  endless spinner). If you adapt the YAML, keep the conditions on the container.
* **Charts follow the card width.** Every chart carries the card-mod rule
  `#graph-wrapper { min-width: 0; }`: without it `apexcharts-card` keeps the
  chart as wide as it was first drawn (300 px) inside a narrower card, and the
  newest data and the G1-G3 labels are clipped. The rule reaches into the card
  internals, so check it again after updating Home Assistant or
  `apexcharts-card`.

The last hour and the last day are drawn from `samples_24h`; headers show two
decimals, like the table.

The charts use a **normalized scale**: the first alert threshold (G1) at 60%
and the third (G3) at 90% of the height, so every station is read against its
own thresholds. The Status sensor exposes this scale as `chart_min_m` and
`chart_max_m` (null when the thresholds are not published, unless you set an
axis ceiling, see Options). The area is blue
below G1 and yellow, orange, red above G1, G2, G3, filled from the bottom of
the axis (negative levels are real values).

#### Bacchiglione river network schematic

Copy [the PNG](examples/hydro_network_bacchiglione.png) to
`www/arpav/hydro_network_bacchiglione.png` in your Home Assistant configuration
directory. Paste [the example card YAML](examples/hydro_network_bacchiglione.yaml)
into a manual card on your dashboard. The card uses the built-in Picture and
Markdown cards. It shows the documented connections and gauge IDs, including the
two outlets at Voltabarozzo and the Cagnola confluence. The layout is schematic,
with no geographic scale or live flow indication.

To refresh the image after editing the topology, run
`python examples/generate_hydro_network.py` with Graphviz (`dot`) and the
DejaVu Sans font installed. Source references for the reaches are included in
[the profile](custom_components/arpav_meteo_idro/hydro_topology.py).

### Map of the stations

The Status sensor of each station already exposes the ARPAV `latitude` and
`longitude` attributes, so the built-in
[Map card](https://www.home-assistant.io/dashboards/map/) can show one marker
per station without any change to the integration. Ready views:
[`hydro_map_bacchiglione.yaml`](examples/hydro_map_bacchiglione.yaml) (English
entity IDs) and [`hydro_map_bacchiglione_it.yaml`](examples/hydro_map_bacchiglione_it.yaml)
(Italian entity IDs). To use one:

1. Open a dashboard, switch to edit mode and open the raw configuration editor.
2. Paste the file as a new view (it contains `title`, `path` and a sections
   layout like the other examples), or copy only the `type: map` card into an
   existing view.
3. Replace the entity IDs if your stations or the entity language differ: use
   the Status entity of each station (`..._status`, `..._stato` in Italian).
   The Map card takes a fixed list of entities, so a new station must be added
   by hand.

Each marker shows the Status of the station (below G1, between thresholds,
stale, missing...); tapping it opens the entity dialog with level, observation
time (`source_observed_at`) and `quality` among the attributes. A table below the
map lists the same stations with level, a status dot (hollow for stale or missing
readings), observation time and quality, and skips any station whose coordinates
are not numeric. The map ignores entities without coordinates, so the other
sensors of such a station are unaffected. Marker colours cannot depend on the
state with the built-in card: use the table for the colour code.

## Options

Stations and their order, trend threshold (cm), staleness limit (0 = automatic:
90 minutes, longer for series published every 30 minutes), daily history
completion and the **axis ceiling for stations without thresholds**.

The axis ceiling is an optional text field, `station_id=metres`, several
separated by commas (for example `334=10, 595=8`): the stations must be selected
in the entry, each value between 0 (excluded) and 100 m, with a dot as decimal
separator. For a station that publishes no GUARDIA thresholds (such as
Voltabarozzo, 334) the Status sensor then exposes `chart_max_m` with that value,
`chart_min_m` null (the chart keeps a soft minimum from the data) and
`axis_ceiling_source: user`. Stations with ARPAV thresholds ignore the option:
the published values always win. The entry reloads when the options are saved.
The example dashboard generator takes the same value with `--chart-max 334=10`.

Station names: ARPAV writes accents as apostrophes (`Ponte San Nicolo'`); the
names shown (devices, `station_name` attribute) now carry the accent
(`Ponte San Nicolò`). Entity IDs and unique IDs do not change.

> The levels and thresholds are automatic ARPAV data, not previously validated.
> This is not an official warning service: refer to ARPAV and Civil Protection.

## Data provenance

A single weather station in Home Assistant is fed by several distinct ARPAV
networks: the [meteogram](https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/meteo-idro-nivo/variabili_meteo)
network for the observations, the [air quality](https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/aria/qualita-aria-dati-in-diretta)
network, the [night sky brightness](https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/luminosita-del-cielo/brillanza)
network and the forecast bulletin. They have different locations, different
sampling intervals and different publishing latencies, and not every value is
an observation: some are forecasts.

Every entity therefore reports where its value comes from, as extra state
attributes:

| Attribute | Description |
| --------- | ----------- |
| `source` | Origin of the value: `station`, `air_quality_station`, `sky_brightness_station`, `metar`, `forecast` or `unknown` |
| `source_name` | The reporting station, or the forecast zone |
| `source_observed_at` | When the value was observed at the origin, which can be well before the last update |

The weather entity exposes the same information for the current condition,
prefixed with `condition_`, plus `condition_source_rule`: the criterion that
decided the condition, one of `precipitation`, `visibility`, `wind`,
`solar_radiation`, `sky_brightness`, `cloud_cover` or `forecast`.

> [!TIP]
`condition_source` is the honest way to tell a measured condition from a
forecast one: for example a `cloudy` state coming from
`source: station, source_rule: solar_radiation` is measured sunlight, while
`source: forecast` means the sky could not be measured and the bulletin was
used instead.

## Archive of the night sky brightness

The [night sky brightness](https://www.arpa.veneto.it/dati-ambientali/dati-in-diretta/luminosita-del-cielo/brillanza)
network publishes its readings in a single batch a day, around 09:30 standard
time, so a night value only becomes available the morning after. That makes it
unusable to describe the current sky, but it remains a genuine measurement of
the night that has just passed.

Enabling _Archive the night sky brightness as long-term statistics_ imports
those readings with their real timestamps, for the three brightness stations
nearest to the chosen weather station:

- statistics are hourly, with mean, minimum and maximum, in `mag/arcsec²`;
- they are named `arpav_meteo_idro:sky_brightness_<station>` and can be
  charted with a `statistics-graph` card;
- the API exposes about the last 72 hours and they are all re-imported at every
  run, so a day spent offline recovers by itself, with no duplicates;
- the import runs at 11:15 local time, after the daily batch, and once at
  startup. The `arpav_meteo_idro.archive_brightness` service runs it on
  demand.

> [!NOTE]
This is entirely separate from the real-time path: no entity and no automation
is fed by these statistics. They serve to recalibrate the night thresholds on
the values a given area actually reaches, and to check after the fact what the
forecast fallback got right. Requires the `recorder` integration, which is
enabled by default.

## Expose raw data

In order to get the raw data for advanced stuff in HA, from the UI go to
_Settings > Devices & services > ARPAV Meteo e Idro_.
<br>
Press the _CONFIGURE_ button on the integration entry.
<br>
Enable the option you need among:

<dl>
<dt>
Expose JSON extra attribute for internal forecast data
</dt>
<dd>
JSON representation of the internal data structure serving forecasts
</dd>
<dt>
Expose JSON extra attribute for raw original forecast data
</dt>
<dd>
JSON representation of the raw forecast data, as obtained from the bulletin remote endpoint
</dd>
<dt>
Expose extra attributes for raw original sensor data
</dt>
<dd>
Raw data from the meteogram remote endpoint, exposed both as single attributes (prefixed with <i>raw_</i> leading to related value) plus the list of raw objects representing last available sensor observation, along with description, unit of measure, date/time.
</dd>
</dl>

## Actions

| Action | What it does | Fields |
|---|---|---|
| `arpav_meteo_idro.refresh_data` | Fetch the data now instead of waiting for the next update | `entry_id` (optional): one configuration entry; all when omitted |
| `arpav_meteo_idro.archive_brightness` | Import the night sky brightness of the last ~72 hours as statistics (weather locations) | `entry_id` (optional) |
| `arpav_meteo_idro.archive_hydro_history` | Fill missing hourly statistics of the water level sensors using complete source hours from the last 2–3 days. Returns `imported_hours` and, per level sensor, `hours`, `from`, `to` (enable "return response" in Developer tools to see it) | `entry_id` (optional) |

An `entry_id` that is not loaded, or that is of the wrong kind for the action, is
rejected with an error.

## Use cases

* **River level dashboard.** Paste one of the ready views in
  [`examples/`](examples) (see *Example dashboards*): a table of the stations of
  the river with level, status, age and trend, plus 24-hour and 72-hour charts
  against the alert thresholds.
* **Threshold notifications.** A notification that is sent only when the river
  has stayed above an alert threshold for a while and the data is recent, and
  that says when it is back below. The first trigger fires when the Status
  sensor of a station has been `g1_g2`, `g2_g3` or `above_g3` for
  `confirm_minutes` (default 20) **and** the measurement is not older than 90
  minutes; the second when it has been `below_g1` for as long, under the same
  age condition. A helper (`input_boolean.vicenza_river_alert_sent`, create it in
  *Settings → Devices & services → Helpers*) remembers that an alert was sent, so
  the "back below" message is sent only after one:

  ```yaml
  automation:
    - alias: River level alert with confirmation
      mode: queued
      max: 5
      trigger_variables:
        confirm_minutes: 20
      triggers:
        - trigger: template
          id: above
          value_template: >-
            {% set e = 'sensor.bacchiglione_a_vicenza_status' %}
            {% set observed = state_attr(e, 'source_observed_at') %}
            {{ is_state(e, ['g1_g2', 'g2_g3', 'above_g3'])
               and observed is not none
               and (now() - as_datetime(observed)).total_seconds() <= 90 * 60 }}
          for:
            minutes: "{{ confirm_minutes }}"
        - trigger: template
          id: below
          value_template: >-
            {% set e = 'sensor.bacchiglione_a_vicenza_status' %}
            {% set observed = state_attr(e, 'source_observed_at') %}
            {{ is_state(e, 'below_g1')
               and observed is not none
               and (now() - as_datetime(observed)).total_seconds() <= 90 * 60 }}
          for:
            minutes: "{{ confirm_minutes }}"
      actions:
        - variables:
            e: sensor.bacchiglione_a_vicenza_status
            name: "{{ state_attr(e, 'station_name') }}"
            level: "{{ state_attr(e, 'level_m') }}"
            trend: "{{ state_attr(e, 'trend') }}"
            observed_at: >-
              {{ as_datetime(state_attr(e, 'source_observed_at'))
                 | as_local | string | truncate(16, True, '') }}
        - choose:
            - conditions: "{{ trigger.id == 'above' }}"
              sequence:
                - action: input_boolean.turn_on
                  target:
                    entity_id: input_boolean.vicenza_river_alert_sent
                - action: notify.mobile_app_phone
                  data:
                    title: "{{ name }}"
                    message: >-
                      {% set band = states(e) %}
                      {% set limit = {'g1_g2': 'guardia1_m', 'g2_g3': 'guardia2_m',
                                      'above_g3': 'guardia3_m'}[band] %}
                      {% set label = {'g1_g2': 'G1', 'g2_g3': 'G2',
                                      'above_g3': 'G3'}[band] %}
                      Level {{ level }} m, above alert threshold {{ label }}
                      ({{ state_attr(e, limit) }} m), trend {{ trend }}.
                      Observed at {{ observed_at }}.
            - conditions:
                - "{{ trigger.id == 'below' }}"
                - condition: state
                  entity_id: input_boolean.vicenza_river_alert_sent
                  state: "on"
              sequence:
                - action: input_boolean.turn_off
                  target:
                    entity_id: input_boolean.vicenza_river_alert_sent
                - action: notify.mobile_app_phone
                  data:
                    title: "{{ name }}"
                    message: >-
                      Level back below the first alert threshold:
                      {{ level }} m, trend {{ trend }}. Observed at {{ observed_at }}.
  ```

  How it avoids false alarms and stale data:

  * Each trigger is a template that is true only while the band is right *and*
    the age of the measurement is acceptable. The age is computed from
    `source_observed_at`, not read from `age_minutes`, so the example does not
    depend on that attribute. `stale`, `missing`, `no_thresholds` and
    `unavailable` are never in the list, and a reading older than 90 minutes makes
    the template false.
  * `for` starts when the template turns true and is cancelled when it turns
    false, so a brief excursion over a threshold, a station that stops publishing
    or a switch to `stale` sends nothing. Because the whole condition is in one
    template, the example does not rely on whether a change of attributes only
    (the Status sensor updates its attributes at every poll) restarts a `for`
    timer on a state trigger.
  * Changing band while above (for example `g1_g2` to `g2_g3`) does not send a
    second message: the message gives the band reached when the confirmation
    time ended. To be told about escalations as well, add a trigger per band.
  * `mode: queued` keeps both messages if the "above" and "below" triggers fire
    close together, which `single` would drop (with a log warning); the actions
    are short, so the queue never grows. `restart` is not suitable because it
    would cut a notification that is being sent.

  The entity ID depends on the station name; the `confirm_minutes` and 90-minute
  values can be changed. This is not an official warning service: refer to ARPAV
  and Civil Protection.
* **Moon phase next to the river levels.** Add Home Assistant's built-in
  [Moon integration](https://www.home-assistant.io/integrations/moon/)
  (*Settings → Devices & services → Add integration → Moon*) and put its sensor
  in the same view as the river tables, for example with a card in the view next
  to them:

  ```yaml
  type: tile
  entity: sensor.moon
  name: Moon phase
  ```

  The entity ID may differ on your installation. This only shows the phase of
  the moon: the **astronomical tide** is a different source and this integration
  does not provide it.
* **History import.** Recover the hourly statistics of the days the installation
  was offline, or fill the history right after installing, with the
  `arpav_meteo_idro.archive_hydro_history` action (see *Completing the level
  history*): the water level then shows up in the statistics graph and in
  history charts.

## Data updates

* Weather locations: every 5 minutes; METAR at most every 10 minutes; night sky
  brightness once a day.
* Hydrometric stations: every 5 minutes. ARPAV publishes in batches, usually
  20-60 minutes after the observation (the recorded files were generated about
  18 minutes after their last sample); polling more often than 5 minutes
  cannot show newer data and a longer interval would only add delay to the
  next batch, while each poll is one small file per station
  (at most 5 requests at once). The Water level sensor is written to the
  database only when a poll brings a new sample. The Status sensor is written at
  every poll, even when ARPAV has published nothing new, because its
  `age_minutes` and `last_successful_acquisition` attributes change each time:
  one state per poll, so 288 a day per station at the 5-minute interval (the
  other sensors of the station, Trend among them, are not written when nothing
  changed). To store fewer rows, exclude the Status sensors from the Recorder
  (`recorder:` → `exclude:` → `entities:`, listing their entity IDs) or shorten
  `purge_keep_days`. A station without a reading newer than
  the staleness limit is reported as `stale`. An unusable response retains the last valid reading and its timestamp, so
  it still becomes `stale` as it ages. Polling limits concurrent requests and
  backs off stations with repeated acquisition failures while continuing to
  poll healthy stations.

## Known limitations

* ARPAV data are automatic and not previously validated; they may later change
  or be invalidated by ARPAV.
* Water levels are relative to the local hydrometric zero of each station: they
  are not altitudes and cannot be compared between stations.
* The verified display order covers the documented station paths in each profile.
  The graph describes connections at the scale of the named reaches and junctions.
  The display order gives no information about gate settings, travel times or backwater.
* Home Assistant cannot back-date states: the history of the days before the
  installation only reaches the long-term statistics, and only for the 2-3 days
  ARPAV still publishes.
* GUARDIA1/2/3 are the thresholds published by ARPAV for the series; they are
  not the official warning codes of the Civil Protection.

## Troubleshooting

* *Cannot connect while adding the integration*: the ARPAV servers are
  unreachable or returned an HTML page; try again later.
* *The data are delayed*: ARPAV publishes in batches, usually 20-60 minutes after
  the observation, and the integration reads the files every 5 minutes. The
  **Observed at** time (attribute `source_observed_at` on every sensor) is when
  the value was measured, not when it was downloaded.
* *A station is always `stale`*: check the station file
  (`source_url` attribute) for its latest `DATI` time; some stations stop
  publishing for maintenance. The staleness limit can be changed in the options.
* *A value is missing or a station is `missing`*: ARPAV writes sentinels such as
  `>>` where a measurement is not available. They are never turned into 0: the
  last valid value is kept and `quality` is `last_sample_invalid`; when the whole
  period holds only sentinels the status is `missing`.
* *A station has the status `no_thresholds`*: ARPAV publishes no alert
  thresholds (GUARDIA1/2/3) for it. The level is still reported; the thresholds
  are never borrowed from a nearby station.
* *The Observed at and Level change sensors are not there*: they are disabled by
  default on new installations (the same information is in the attributes and
  in the Trend sensor); enable them from **Settings → Devices & services →
  Entities**.
* *The icon in the HACS update dialog is a placeholder*: HACS 2.0.5 takes the
  icon from the central brands site, where this integration is not listed;
  Home Assistant 2026.11 and its Marketplace fix this. The integration page and
  the device pages show the local icon.
* *A removed station still has a device*: devices of deselected stations are
  removed when the entry reloads; otherwise delete the device from its page.
* To report a problem, download the **diagnostics** of the entry (**Settings →
  Devices & services → ARPAV Meteo e Idro → ⋮ → Download diagnostics**): the
  coordinates and the municipality are redacted.
* Enable debug logging (see below) and look for `arpav_meteo_idro` in the logs.

## Removing the integration

1. Go to **Settings → Devices & services → ARPAV Meteo e Idro**.
2. Open the menu (⋮) of each configuration entry (weather location or river)
   and choose **Delete**.
3. To uninstall the files, remove the repository in HACS (or delete
   `custom_components/arpav_meteo_idro`) and restart Home Assistant.

Statistics already imported stay in the database until they are deleted in
**Developer tools → Statistics**.

## Enable Debug Logging

If logs are needed for debugging or reporting an issue, use the following configuration.yaml:

```yaml
logger:
  default: error
  logs:
    custom_components.arpav_meteo_idro: debug
```

## Quality

Self-assessment against the Home Assistant integration quality scale (target: Bronze) and how to run the tests: [docs/quality_scale.md](docs/quality_scale.md).

## Credits and licensing

- Weather part and original code: Davide Cavestro, from [davidecavestro/arpa-veneto-weather](https://github.com/davidecavestro/arpa-veneto-weather).
- Hydrometric stations part (`hydro*.py`, related flow steps, tests and examples): Gianluca Nardin ([@UMMgl](https://github.com/UMMgl)).

- Original code from [davidecavestro/arpa-veneto-weather](https://github.com/davidecavestro/arpa-veneto-weather): Copyright (c) 2024 Davide Cavestro, [BSD 3-Clause License](LICENSE-BSD-3-Clause).
- New files and modifications introduced in this fork: [Apache License 2.0](LICENSE).
- See [NOTICE](NOTICE) for details. ARPAV data are CC BY 4.0 (see Disclaimer).

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by ARPAV (Agenzia Regionale
per la Prevenzione e Protezione Ambientale del Veneto).

The data and information provided through this integration are sourced from the ARPAV API,
which is publicly available and licensed under the Creative Commons Attribution 4.0 Italy
(CC BY 4.0) license unless otherwise specified.

### Terms of Use

All trademarks, logos, and distinctive signs visible on ARPAV's website are the property of
ARPAV and cannot be used without prior authorization.

Any reproduction, distribution, modification, or use of ARPAV's content must attribute the
source by citing "ARPAV" and providing the URL: http://www.arpa.veneto.it.

This project utilizes ARPAV's data strictly within the terms of the
[Creative Commons Attribution 4.0 Italy license](https://creativecommons.org/licenses/by/4.0/deed.it).

### Limitations of Liability

ARPAV disclaims all responsibility for the accuracy, completeness, and timeliness of the data
provided via their API, and for any issues arising from its use. Users should refer to ARPAV's
official site for authoritative information.

For more details about ARPAV's copyright and licensing terms, visit their
[website](http://www.arpa.veneto.it/).



***

[commits-shield]: https://img.shields.io/github/commit-activity/y/UMMgl/ha-arpav-meteo-idro.svg?style=flat-square
[commits]: https://github.com/UMMgl/ha-arpav-meteo-idro/commits/main
[hacs]: https://www.hacs.xyz/docs/faq/custom_repositories/
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=flat-square
[forum]: https://community.home-assistant.io/
[license-shield]: https://img.shields.io/github/license/UMMgl/ha-arpav-meteo-idro.svg?style=flat-square
[releases-shield]: https://img.shields.io/github/release/UMMgl/ha-arpav-meteo-idro.svg?style=flat-square
[releases]: https://github.com/UMMgl/ha-arpav-meteo-idro/releases

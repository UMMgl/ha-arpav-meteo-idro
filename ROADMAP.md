# Roadmap

Planned work, one pull request each. Quality items refer to
[docs/quality_scale.md](docs/quality_scale.md).

## Hydrometric stations

- [x] **Automatic upstream-to-downstream ordering for Bacchiglione**, using a
  documented graph covering the first seven stations, with source, verification
  date and confidence per reach. Manual overrides remain available.
- [x] **Extend automatic ordering** to the 22 other multi-station water bodies
  in the 15 November 2026 registry. See [coverage and sources](docs/hydro_topology.md).
- [x] Attach Pila and Porto Barricata to their separate Po delta branches.
- [x] Model Porto Levante on the regulated Canal Bianco / Po di Levante route.
- [x] Per-station axis ceiling option for stations without published thresholds
  (e.g. Voltabarozzo, interim 10 m in the example dashboard).
- [ ] **Full sample resolution in charts.** ARPAV station files carry a sample
  every 10 minutes for about two days (`FREQ` 10), but the level sensor only
  exposes the latest one and the imported history is hourly, so charts show
  steps instead of the ARPAV curve. Expose the recent samples (e.g. the last
  24 hours) as an attribute of the level sensor, draw them in the example
  dashboards with ApexCharts `data_generator`, and review the update interval
  against ARPAV's publication blocks.

## Quality – Bronze

- [ ] Tests for the weather config flow and options flow (`config-flow-test-coverage`).
- [ ] Shared base entity in `entity.py` (`common-modules`).

## Quality – Silver

- [ ] Test coverage above 95%, coverage report in the Tests workflow (`test-coverage`).

## Quality – Gold

- [ ] Diagnostics (redacted).
- [ ] Reconfiguration flow.
- [ ] Repair issues (e.g. a station that stops publishing for days).
- [ ] Stale devices: remove the devices of deselected stations.
- [ ] Entities disabled by default where few users need them.
- [ ] Complete exception translations; use cases and troubleshooting docs.

## Quality – Platinum

- [ ] Inject the Home Assistant web session in the weather part.
- [ ] Strict typing (mypy --strict).

## Compliance

- [ ] EU Cyber Resilience Act (Regulation (EU) 2024/2847): scope decision, Annex I
  essential requirements, vulnerability handling (SBOM, coordinated disclosure,
  signed updates), reporting obligations from 11 September 2026 – see
  [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18).

## Upstream

Deferred in [#13](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/13). ARPAV Meteo e Idro is the active Home Assistant integration. ARPAV River Level provides a technical reference for hydrometric data quality and polling resilience.

- [ ] Propose the hydrometric part to davidecavestro/arpa-veneto-weather as a pull
  request (without the fork rename; contribution under BSD-3-Clause like the
  original project), if the author is interested.

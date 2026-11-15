# Roadmap

Planned work, one pull request each. Quality items refer to
[docs/quality_scale.md](docs/quality_scale.md).

## Hydrometric stations

- [ ] **Automatic upstream-to-downstream ordering** of the stations of a river,
  instead of the order typed by the user. The ARPAV XML files publish no
  adjacency, so the order must come from the river network (Regione Veneto /
  basin authority cartography) and be stored per segment with source,
  verification date and confidence (`topology_status: verified`). Confluences,
  diversions and side branches (e.g. Cagnola at Bovolenta) need a graph, not a
  list; never order by IDSTAZ, node order, latitude, longitude or QUOTA. The
  manual order stays as an override.
- [ ] Per-station axis ceiling option for stations without published thresholds
  (e.g. Voltabarozzo, interim 10 m in the example dashboard).

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

# Roadmap

Planned work, grouped by release and delivered one pull request each. Dates are
indicative. Quality items refer to the
[Home Assistant Quality Scale](docs/quality_scale.md); the minimum tier a stable
release must reach is enforced in CI and can only go up (`release_tier` ratchet,
see 0.16.0).

Already delivered and not repeated below: automatic upstream-to-downstream
ordering for all multi-station water bodies (see
[coverage and sources](docs/hydro_topology.md)), the per-station axis ceiling
option, and the Bronze tier plus the Gold quick wins (diagnostics, stale devices,
disabled-by-default entities, exception translations).

## 0.16.0 – Silver and release security (stable planned for December 2026)

Minimum release tier: **Silver**.

- [x] **10-minute samples in charts.** The level sensor exposes the last 24 hours
  of samples as an attribute (excluded from the Recorder) and the example
  dashboards draw them.
- [x] **Map example** of the hydrometric stations
  ([#20](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/20)).
- [x] **Hash-pinned test requirements** and removal of the unused development
  container.
- [ ] **Shared web session in the weather part** (`inject-websession`, first half of
  [#7](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/7)).
- [ ] **Remove the manual station order**, with migration of existing entries
  ([#38](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/38)).
- [ ] **Test coverage above 95% for every module**, coverage report in the Tests
  workflow (`test-coverage`,
  [#5](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/5)).
- [ ] **Release security gate:** the security workflow must pass on the tagged
  commit before anything is published, beta tags included; the minimum quality
  tier is read from a versioned `release_tier` setting that cannot be lowered.
- [ ] **Security evidence register** with the OpenSSF Passing criteria and a draft
  OWASP SAMM level 1 baseline, and the written CRA scope decision
  ([#28](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/28),
  [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18)).

## 0.16.x – Consolidation (December 2026 – January 2027)

- [ ] **Strict typing, phase A:** the modules that do not import Home Assistant,
  checked by mypy in the Lint job.
- [ ] **Risk assessment and vulnerability-handling exercise** (simulated report,
  outcome recorded in the evidence register), completing
  [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18).

## 0.17.0 – Gold and Platinum (planned for February 2027)

Minimum release tier: **Gold**.

- [ ] **Reconfiguration flow** for the weather and hydrometric entries
  ([#6](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/6)).
- [ ] **Repair issues**, e.g. a station that stops publishing for days
  ([#6](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/6)).
- [ ] **Strict typing (`mypy --strict`) for the whole integration**, Platinum
  ([#7](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/7)); if it is not
  finished in time it follows in a 0.17.x release.
- [ ] **Rainfall context** over several time windows, design first
  ([#47](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/47)).
- [ ] **Re-evaluate ClusterFuzzLite** (fuzzing is currently covered by property
  tests of the XML parser only).
- [ ] First quarterly review of the evidence register.

## Research backlog

Explorations with no release attached; each needs a design decision before any
implementation:
[#46](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/46),
[#48](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/48),
[#49](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/49),
[#50](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/50),
[#51](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/51),
[#52](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/52).

## Compliance

This is a non-commercial open source project. Regulation (EU) 2024/2847 (Cyber
Resilience Act) is handled as **due diligence**, not as a claim of conformity: the
project does not carry the CE marking, does not issue a declaration of
conformity and does not promise five years of support.

- [ ] Scope decision, evidence register and review triggers
  ([#28](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/28),
  [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18), 0.16.0).
- [ ] Security gate on every release: scanning on the tagged commit, SBOM, release
  checksums and build provenance (0.16.0).
- [ ] Vulnerability handling: acknowledgement within 7 days and triage within
  2 weeks, as targets rather than guarantees; exercised in 0.16.x
  ([#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18)).

## Upstream

Deferred in [#13](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/13). ARPAV Meteo e Idro is the active Home Assistant integration. ARPAV River Level provides a technical reference for hydrometric data quality and polling resilience.

- [ ] Propose the hydrometric part to davidecavestro/arpa-veneto-weather as a pull
  request (without the fork rename; contribution under BSD-3-Clause like the
  original project), if the author is interested.

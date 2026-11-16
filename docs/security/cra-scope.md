<!-- SPDX-License-Identifier: Apache-2.0 -->
# Cyber Resilience Act: scope decision and due diligence

Tracking issue: [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18).
Evidence register: [evidence.md](evidence.md).

**Status: the scope decision below is the maintainer's; the factual
statements in section 2 were confirmed by the maintainer on 2026-11-16. This page is the project's own assessment, not legal
advice, and it does not claim that the project, the integration or any release
conforms to Regulation (EU) 2024/2847. There is no CE marking, no EU
declaration of conformity and no support-period commitment.**

## 1. Decision

On **2026-11-15** the maintainer decided
([#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18)) that:

* no commercialisation is planned;
* the project is therefore treated as **outside the commercial scope** of the
  Cyber Resilience Act (Regulation (EU) 2024/2847, "CRA"), so the
  manufacturer obligations do not apply to it as things stand;
* the project nevertheless pursues the CRA's security practices as
  **proportionate due diligence**: it keeps voluntarily those that suit a
  non-commercial project and reviews the scope when its circumstances change.

On **2026-11-16** the maintainer set the vulnerability-handling targets in
[SECURITY.md](../../SECURITY.md): acknowledgement within 7 days, triage within
2 weeks, as internal targets and not as service-level agreements.

## 2. Factual basis (confirmed by the maintainer on 2026-11-16)

| Fact | Status |
|---|---|
| The integration "ARPAV Meteo e Idro" (`arpav_meteo_idro`) is free and open-source software under Apache-2.0 and BSD-3-Clause ([LICENSE](../../LICENSE), [LICENSE-BSD-3-Clause](../../LICENSE-BSD-3-Clause), [NOTICE](../../NOTICE)). | Checked against the repository |
| It is published on GitHub and installed through HACS; releases are built by [release.yml](../../.github/workflows/release.yml). | Checked against the repository |
| It reads public ARPAV open data (CC BY 4.0) and the public METAR service; no credentials, no personal data ([SECURITY.md](../../SECURITY.md)). | Checked against the repository |
| It is developed by a private individual, the maintainer (`@UMMgl`), outside any commercial activity of that person, and is not offered for a price. | Confirmed by the maintainer |
| No paid support, no sale, no sponsorship or donation arrangement is tied to the project, and no organisation steadily supports it for commercial use. | Confirmed by the maintainer |
| The software is not part of a product that the maintainer or an employer sells. | Confirmed by the maintainer |

## 3. Role assessment

The CRA distinguishes economic operators; the roles below are assessed for the
current situation only.

| Role | Assessment | Reason |
|---|---|---|
| Manufacturer (Art. 3, Art. 13) | Not applicable now | The product is not made available on the market in the course of a commercial activity (see recitals 15–20 on free and open-source software developed without monetisation). Free availability alone is not the test; the absence of monetisation and of commercial support is. |
| Open-source software steward (Art. 3, Art. 24) | Not applicable now | No legal person or organisation systematically provides support for commercial use or develops the project on a continuing commercial basis. |
| Importer, distributor | Not applicable | The project does not place third-country products on the market. |
| Component used by a manufacturer | Possible, outside the project's control | A third party could embed the integration in a commercial product. That party would then be the manufacturer and would have to exercise due diligence on the component (Art. 13(5)); the project's practices ([evidence.md](evidence.md), SBOM, advisories) are meant to make that possible, without any commitment towards that party. |

Public hosting, regular releases and use by third parties in a commercial
setting do not by themselves make the maintainer's distribution commercial.
Donations and similar income are triggers for review (below), not proof either
way.

Timeline for orientation: the vulnerability and incident reporting duties of
manufacturers apply from 11 September 2026, the remaining obligations from 11
December 2027, subject to the applicable role. As the project is currently
not a manufacturer, no reporting duty is assumed; a decision point is part of
the reassessment (below).

References: [Regulation (EU) 2024/2847](https://eur-lex.europa.eu/eli/reg/2024/2847/oj);
[European Commission CRA overview](https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act).

## 4. Product category

If the CRA applied, the integration would not fall in the important or
critical product classes of Annex III or IV: it is a default-category product,
for which the conformity route is self-assessment (module A). This is recorded
for planning only; no assessment is carried out and no declaration is issued.

## 5. Reassessment triggers

The scope and role decision is reviewed, and this page updated, when any of the
following happens or is planned:

1. paid support, a paid tier, a sale or any other price for the software or for
   services around it;
2. a legal person or organisation takes over the project, supports it
   systematically for commercial use, or funds its development in exchange for
   influence on it (steward role);
3. integration of the software into a commercial product, or a commercial
   partnership, by the maintainer or an employer;
4. donations or sponsorship that cover costs beyond running the project, or
   that are tied to the software's roadmap;
5. a change in the law, a Commission guideline or an authority's position that
   alters the reading of recitals 15–20 or Article 24;
6. a reported actively exploited vulnerability or a severe incident, to decide
   whether any notification is advisable.

Besides these events, the page is checked at the quarterly review of
[evidence.md](evidence.md) (first on 2027-02-16).

## 6. Disposition of the checklist in #18

Dispositions: **Adopted** = kept voluntarily as due diligence, with evidence;
**Open** = adopted in principle, work still planned (not yet evidenced);
**Not applicable** = a manufacturer obligation that the current scope does not
trigger, with the reason. "S2", "S3", "S4" are the work packages of the plan
under #18: S2 is this change, S3 the risk analysis and vulnerability-handling
exercise (0.16.x), S4 the security gate in the release workflow (0.16.0).

### 6.1 Scope

| Item | Disposition | Reason and evidence |
|---|---|---|
| Assess whether the integration is made available in the course of a commercial activity; record outcome in `SECURITY.md` | Adopted | Sections 1–3 above; summary in [SECURITY.md](../../SECURITY.md) ("Scope and the Cyber Resilience Act"). Facts in section 2 confirmed by the maintainer. |
| Classify the product (default category, self-assessment) | Adopted (for planning) | Section 4. No assessment is run while the project is out of scope. |

### 6.2 Essential requirements – product (Annex I, part I)

| Item | Disposition | Reason and evidence |
|---|---|---|
| Documented risk assessment (data sources, network exposure, untrusted XML, Recorder writes) | Open | Summary in [SECURITY.md](../../SECURITY.md) ("What the integration does"). The full analysis is S3 (0.16.x). |
| No known exploitable vulnerabilities at release (bandit, CodeQL, pip-audit, gitleaks) | Open | The checks run on every pull request and on `main` ([security.yml](../../.github/workflows/security.yml), [run](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671)), but they are not a gate on the tagged release commit yet. S4, 0.16.0; it needs the maintainer's authorisation as a workflow change. A green scanner is not proof of absence of vulnerabilities. |
| Secure by default; minimal attack surface (HTTPS only, no listening ports, no credentials) | Adopted | The integration only makes outbound HTTPS requests to fixed ARPAV and METAR endpoints ([const.py](../../custom_components/arpav_meteo_idro/const.py), [hydro.py](../../custom_components/arpav_meteo_idro/hydro.py), [metar.py](../../custom_components/arpav_meteo_idro/metar.py)), opens no port and needs no credentials. |
| Integrity and confidentiality of data in transit (TLS verification on, no custom certificates) | Adopted for the hydrometric part; Open for the weather part | The hydrometric part uses the Home Assistant session ([hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py)). The weather part still creates its own `aiohttp` sessions with default TLS verification; moving it to the Home Assistant session is tracked in [#7](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/7) (pull request [#60](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/60), open at the time of writing). No code disables certificate verification. |
| Limit the impact of incidents (bounded requests, timeouts, size limits, back-off) | Adopted for the hydrometric part; Open for the weather part | 30 s request timeout, at most 5 concurrent stations and back-off in [hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py); 5 MiB document limit and HTML rejection in [hydro.py](../../custom_components/arpav_meteo_idro/hydro.py), tested in [test_hydro.py](../../tests/test_hydro.py) and fuzzed in [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py). Equivalent timeouts for the weather part are part of [#7](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/7). |
| Security information logging without personal data | Adopted | The integration processes no personal data; failures are logged through the Home Assistant logger; diagnostics redact coordinates ([diagnostics.py](../../custom_components/arpav_meteo_idro/diagnostics.py)). Not a security event log in the CRA sense; none is planned. |

### 6.3 Vulnerability handling (Annex I, part II)

| Item | Disposition | Reason and evidence |
|---|---|---|
| SBOM for every release | Adopted | CycloneDX file in every release since 0.15.4 ([0.15.5 SBOM](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.cdx.json)); it covers the runtime requirements, not the build tools. |
| Coordinated disclosure policy and contact, with response times | Adopted | [SECURITY.md](../../SECURITY.md) ("Reporting a vulnerability", "Response targets"): GitHub private vulnerability reporting, acknowledgement within 7 days, triage within 2 weeks; internal targets, not SLAs. |
| Security updates without delay, separate from features where possible; advisories published | Adopted on a best-effort basis | Only the latest release is supported; a fix is released as a patch version where practical, with a GitHub Security Advisory when a vulnerability is confirmed ([SECURITY.md](../../SECURITY.md)). No remediation time is promised. Upgrade guidance for older releases: S3. |
| Regular testing and review | Adopted | Security workflow on every change and weekly ([security.yml](../../.github/workflows/security.yml)); Scorecard weekly ([scorecard.yml](../../.github/workflows/scorecard.yml)); quarterly review of [evidence.md](evidence.md). |
| Secure distribution of updates (signed artefacts or provenance, checksums) | Adopted | [SHA256SUMS](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/SHA256SUMS) and a build provenance attestation with the offline bundle ([intoto.jsonl](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.intoto.jsonl)); verification steps in [SECURITY.md](../../SECURITY.md). |

### 6.4 Manufacturer obligations

| Item | Disposition | Reason and evidence |
|---|---|---|
| Declared support period (at least 5 years) and end-of-support date | Not applicable | Manufacturer obligation; the project is not a manufacturer now. A five-year commitment cannot be sustained by a single volunteer maintainer and is deliberately not made. The only statement is that the latest release receives fixes ([SECURITY.md](../../SECURITY.md)). Revisit if trigger 1, 2 or 3 occurs. |
| Reporting to ENISA / CSIRT (24 h early warning, 72 h notification, final report) | Not applicable now; decision point defined | No mandatory reporting duty is assumed. Trigger 6 requires a documented decision on whether a voluntary notification is advisable. A procedure is prepared only if the scope changes. |
| Technical documentation (Annex VII), EU declaration of conformity (Annex V), CE marking | Not applicable | Reserved to manufacturers. None is issued or implied; this page and [evidence.md](evidence.md) must not be quoted as such. |
| User information (Annex II): contact point, purpose, support period, how to install security updates | Partly adopted | Voluntary: security contact and update policy in [SECURITY.md](../../SECURITY.md), intended purpose and installation in [README.md](../../README.md). The support period is not stated (see above). |
| Third-party component due diligence (upstream fork, `defusedxml`, Home Assistant, GitHub Actions) | Adopted, with a gap | Upstream and licences in [NOTICE](../../NOTICE); `defusedxml` and test/CI tools in the SBOM and hashed requirements; actions pinned to commit SHAs; Dependabot ([dependabot.yml](../../.github/dependabot.yml)). A written evaluation of each supplier is part of S3. |

## 7. What this page does not do

* It does not declare the project a CRA manufacturer or steward, nor claim
  conformity of any kind.
* It does not promise a support period, a fix time or the availability of
  the maintainer beyond the internal targets in [SECURITY.md](../../SECURITY.md).
* It does not replace legal advice. If a trigger in section 5 occurs, the
  maintainer should obtain it before publishing a revised position.

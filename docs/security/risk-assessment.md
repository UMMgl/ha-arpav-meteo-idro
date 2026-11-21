<!-- SPDX-License-Identifier: Apache-2.0 -->
# Risk assessment

Tracking issue: [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18)
(work package S3). Related: [#21](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/21),
[#28](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/28).
Register of evidence: [evidence.md](evidence.md). Scope decision:
[cra-scope.md](cra-scope.md).

**Status: draft prepared by an AI agent from the repository on 2026-11-21, to be
validated by the maintainer (`@UMMgl`).** It is the project's own proportionate
analysis for a non-commercial integration. It is not a CRA risk assessment under
Article 13, it does not claim conformity with Regulation (EU) 2024/2847, and a
control listed here is a control that exists on `main` (commit `18740e3`) and can
be followed through its link; anything else is listed as a gap with a due date.
The due dates marked *proposed* are not yet confirmed by the maintainer.

## 1. Scope and risk tolerance

In scope: this repository, the integration `arpav_meteo_idro` as installed in a
user's Home Assistant through HACS, the example dashboards in
[examples/](../../examples), and the GitHub workflows, credentials and release
process that produce the releases.

Out of scope: Home Assistant itself and its Recorder, HACS, the Lovelace cards
that the examples use, ARPAV's and the METAR service's own systems, and the
users' networks. They appear below only as dependencies and trust boundaries.

**Risk tolerance (draft, for the maintainer to confirm).** The integration reads
public data, holds no credentials and no personal data, and opens no port. The
worst realistic outcome of a flaw is a Home Assistant instance that misbehaves
(memory or CPU exhaustion, a crash, a wrong water level shown or recorded), or a
tampered release reaching users. The project therefore tolerates low residual
risk in availability and data accuracy of a public-data display, tolerates no
known exploitable runtime vulnerability at release (the security gate), and
treats the integrity of the release artefacts and of the maintainer's and
agents' credentials as the risks to keep lowest. The integration is not an
official warning service and ARPAV gives no guarantee on its data (see the
disclaimers in [README.md](../../README.md)); it must not be the only source for
safety decisions.

## 2. Assets

| Asset | Why it matters |
|---|---|
| Users' Home Assistant instance (process, memory, Recorder database) | The integration runs inside it with Home Assistant's privileges; a flaw there affects the whole instance. |
| Integrity of the data shown and recorded (levels, thresholds, long-term statistics) | Wrong data may mislead people who look at river levels; statistics written to the Recorder persist. |
| Release artefacts (ZIP, SBOM, checksums, attestation) | They are what HACS installs into users' systems: the supply-chain target. |
| Repository, workflows and branch settings | Control what is built and released. |
| Credentials: the maintainer's GitHub login, the private keys of the two GitHub Apps (`ummgl-claude-code`, `ummgl-chatgpt`), the short-lived tokens derived from them | Give write access to the repository. The project has no runtime secrets and no API keys. |
| Maintainer's time and availability | A single person triages, fixes and releases. |

## 3. Trust boundaries

| Boundary | Untrusted side | What crosses it |
|---|---|---|
| B1: ARPAV XML (`meteo.arpa.veneto.it`) | Remote server and the network path | Station registry and station files (XML); file names taken from the registry. [hydro.py](../../custom_components/arpav_meteo_idro/hydro.py) |
| B2: ARPAV REST API (`api.arpa.veneto.it`) and aviationweather.gov | Remote servers | JSON for the weather part and for METAR. [const.py](../../custom_components/arpav_meteo_idro/const.py), [metar.py](../../custom_components/arpav_meteo_idro/metar.py) |
| B3: Home Assistant Recorder | Trusted platform, but written to with data derived from B1 | Hourly statistics imported for the integration's own level sensors. [hydro_statistics.py](../../custom_components/arpav_meteo_idro/hydro_statistics.py) |
| B4: the user's browser | Dashboard code that the user pastes from the examples | JavaScript in `data_generator` fields and a third-party card (card-mod), fed by sensor attributes. [examples/](../../examples) |
| B5: package index and GitHub Actions marketplace | Third-party code | Python packages and actions pulled by users, CI and the release. |
| B6: GitHub and the maintainer's workstation | Credentials at rest and in use | Tokens, private keys, approvals. |

The transport is HTTPS to fixed hosts; no request target is user-supplied. The
only part of a URL that comes from remote data is the station file name
(control C2 below).

## 4. Security objectives and design principles

Written down here for the first time (they were implicit in the code):

1. **No credentials and no personal data** are held, requested or logged by the
   integration; diagnostics redact coordinates ([diagnostics.py](../../custom_components/arpav_meteo_idro/diagnostics.py)).
2. **Untrusted input is parsed defensively**: XML only through `defusedxml`,
   document size and type checked, every number, instant and file name validated
   before use ([hydro.py](../../custom_components/arpav_meteo_idro/hydro.py)).
3. **Bounded outbound behaviour**: fixed hosts, HTTPS, the shared Home Assistant
   session, a 30 s timeout per request, back-off after failures.
4. **Least privilege everywhere**: no listening ports, workflows with explicit
   `permissions:`, tokens limited to this repository and to the needed scopes.
5. **Verifiable releases**: built by one workflow from a tag, gated on security
   and quality checks, published with SBOM, checksums and provenance.
6. **Fail visible**: a failed fetch or parse makes the sensor unavailable or
   keeps the last good value flagged as stale; it never raises an unhandled error
   into Home Assistant ([hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py)).

## 5. Risk table

Likelihood and impact are the agent's qualitative estimate (L/M/H) for this
project's context; *residual* is the risk left after the existing controls,
including the gaps. Owner is `@UMMgl` for every row: the project has one
maintainer, and agents only prepare changes through their own App identity.

### Controls referenced

| Id | Control | Where it is implemented | Test, workflow or run that evidences it |
|---|---|---|---|
| C1 | XML parsed with `defusedxml` only; entity declarations refused; HTML and wrong root element rejected | [hydro.py:33](../../custom_components/arpav_meteo_idro/hydro.py#L33), [`_root`](../../custom_components/arpav_meteo_idro/hydro.py#L199) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_entities_are_not_expanded`, `test_html_is_refused`, `test_wrong_root_is_refused`, arbitrary and mutated bytes, deep nesting), [test_hydro.py](../../tests/test_hydro.py) |
| C2 | Station file name accepted only as `NNNN.xml` (digits), otherwise derived from a numeric station ID; the URL is always under the fixed ARPAV base | [`station_file`](../../custom_components/arpav_meteo_idro/hydro.py#L47), [`STATION_FILE`](../../custom_components/arpav_meteo_idro/hydro.py#L40) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_station_file_never_leaves_the_pattern`, `test_station_file_rejects_hostile_links`, `test_station_file_rejects_invalid_ids`) |
| C3 | Document larger than 5 MiB refused **after it has been downloaded** | [`MAX_XML_BYTES`](../../custom_components/arpav_meteo_idro/hydro.py#L67), [`_root`](../../custom_components/arpav_meteo_idro/hydro.py#L199) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_oversized_document_is_refused`). See gap G1: this is not a download limit. |
| C4 | Numbers, instants and station IDs validated with strict patterns and finite/positive checks; invalid values become "no value" | [hydro.py](../../custom_components/arpav_meteo_idro/hydro.py) (`INSTANT`, `STATION_ID`, `parse_number`) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_parse_number_*`, `test_parse_instant_*`) |
| C5 | Shared Home Assistant session and a 30 s total timeout on every request, weather part included | `REQUEST_TIMEOUT` in [hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py#L35), [coordinator.py](../../custom_components/arpav_meteo_idro/coordinator.py#L33), [metar.py](../../custom_components/arpav_meteo_idro/metar.py#L29), [config_flow.py](../../custom_components/arpav_meteo_idro/config_flow.py#L59), [brightness_statistics.py](../../custom_components/arpav_meteo_idro/brightness_statistics.py#L35); `git grep "ClientSession("` finds nothing in the package | [test_weather_flow_http.py](../../tests/test_weather_flow_http.py), [test_silver_ha.py](../../tests/test_silver_ha.py) (timeout paths) |
| C6 | Hydrometric part: at most 5 stations fetched concurrently (semaphore) | [hydro_coordinator.py:101](../../custom_components/arpav_meteo_idro/hydro_coordinator.py#L101) | No dedicated test of the limit (gap G4) |
| C7 | Hydrometric part: per-station exponential back-off (2x, 4x, 8x the polling interval, 30 min cap, jitter) after repeated failures; last good observation kept | [`_async_update_station`](../../custom_components/arpav_meteo_idro/hydro_coordinator.py#L122) | [test_hydro_ha.py](../../tests/test_hydro_ha.py) (retry time and recovery, about lines 396-417) |
| C8 | Statistics written only for the integration's own level sensors, resolved through the entity registry, complete past hours only, and only hours the Recorder does not already hold | [hydro_statistics.py](../../custom_components/arpav_meteo_idro/hydro_statistics.py#L54) | [test_hydro_statistics.py](../../tests/test_hydro_statistics.py) |
| C9 | `samples_24h` is capped at 288 points and excluded from the Recorder | [`MAX_RECENT_SAMPLES`](../../custom_components/arpav_meteo_idro/hydro.py#L78), [`_unrecorded_attributes`](../../custom_components/arpav_meteo_idro/hydro_sensor.py#L113) | [test_hydro.py](../../tests/test_hydro.py) (`test_recent_samples_is_bounded`), [test_hydro_ha.py](../../tests/test_hydro_ha.py) (`test_level_sensor_exposes_unrecorded_samples`) |
| C10 | The examples' JavaScript is static text in the repository; the only data it receives are sensor attributes that the integration builds from validated numbers and ISO timestamps (no free text from the remote side reaches the code) | [generate_hydro_dashboard.py](../../examples/generate_hydro_dashboard.py), [examples/](../../examples) | [test_example_dashboards.py](../../tests/test_example_dashboards.py) |
| C11 | Runtime dependency is only `defusedxml`; SBOM of the runtime requirements in every release | [manifest.json](../../custom_components/arpav_meteo_idro/manifest.json), [release.yml](../../.github/workflows/release.yml) | [0.16.0 SBOM](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.16.0/ha-arpav-meteo-idro.cdx.json) |
| C12 | CI and release tools installed from hashed lock files (`--require-hashes`); pip-audit on every requirements file in every run and weekly; Dependabot for actions and pip | [requirements_security.txt](../../requirements_security.txt), [requirements_release.txt](../../requirements_release.txt), [requirements_ci.txt](../../requirements_ci.txt), [requirements_test.txt](../../requirements_test.txt), [security.yml](../../.github/workflows/security.yml), [dependabot.yml](../../.github/dependabot.yml) | [`main` Security run](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671) |
| C13 | Dated waivers for the 43 Pillow 12.3.0 advisories in the test lock only: each entry has a reason and expires on 2027-02-28; the two lists are kept in step | [osv-scanner.toml](../../osv-scanner.toml), [pip-audit-ignore-test.txt](../../.github/pip-audit-ignore-test.txt), [SECURITY.md](../../SECURITY.md) ("Accepted findings") | pip-audit step of [security.yml](../../.github/workflows/security.yml); Scorecard honours `osv-scanner.toml` |
| C14 | Workflows: actions pinned to commit SHAs, `permissions:` set per workflow, `persist-credentials: false`, no `pull_request_target`, zizmor on every change | [.github/workflows](../../.github/workflows) | [`main` Security run](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671) (zizmor job) |
| C15 | Release security gate: the Security workflow (gitleaks, bandit, pip-audit, zizmor, CodeQL for python and actions) must pass on the tagged commit for every tag, pre-releases included; the release job needs it | [release.yml](../../.github/workflows/release.yml) (`security` and `release` jobs), [security.yml](../../.github/workflows/security.yml) (`workflow_call`) | [Release run 44845687536](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/44845687536) (all gate jobs passed before *Release*). A failing gate has not been exercised yet (gap G6). |
| C16 | Quality ratchet: a stable release needs the quality tier declared in `pyproject.toml` (Silver now), which may only rise, with per-module coverage | [release.yml](../../.github/workflows/release.yml) (`tier`, `quality` jobs), [check_quality_scale.py](../../scripts/check_quality_scale.py), [pyproject.toml](../../pyproject.toml) | [Release run 44845687536](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/44845687536) (jobs *Release quality tier*, *Release quality*) |
| C17 | Release provenance: build attestation of the ZIP (OIDC), `SHA256SUMS`, SBOM, offline attestation bundle as release assets; verification steps published | [release.yml](../../.github/workflows/release.yml), [SECURITY.md](../../SECURITY.md) ("Verifying a release") | [0.16.0 release assets](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/tag/0.16.0) |
| C18 | Agents act only through a dedicated GitHub App identity and never approve or merge; changes reach `main` only through pull requests | [CONTRIBUTING.md](../../CONTRIBUTING.md) | Commit authorship of agent branches (`ummgl-claude-code[bot]`); branch protection and required checks: **confirmed by the maintainer on 2026-11-21** (a statement; the App token gets HTTP 403 on those endpoints, so it cannot be checked independently); next check 2027-02-16 (see [evidence.md](evidence.md), `repo_track`) |
| C19 | App tokens are minted on demand by a local script, limited to this one repository and to a subset of the App's permissions, and expire after one hour (GitHub's lifetime for installation tokens); `workflows: write` is added only by an explicit opt-in flag for one work package at a time | A local script outside the repository, **not verifiable from this repository** | Read by the agent on 2026-11-21 (permission lists and repository restriction); the one-hour lifetime is GitHub's, not set by the script; handling of the keys confirmed by the maintainer on 2026-11-21 (section 5, "App credentials") |
| C20 | Gitleaks over the full history on every change; GitHub secret scanning with push protection | [security.yml](../../.github/workflows/security.yml) (`secrets` job) | Secret scanning with push protection **confirmed by the maintainer on 2026-11-21** (setting not readable by the App token); next check 2027-02-16 |

### Risks

| Id | Risk | Cause | Existing controls | Residual risk | Gap and due date | Owner |
|---|---|---|---|---|---|---|
| R1 | Malicious or broken XML from the registry or a station file exploits the parser (entity expansion, external entity, deep nesting) | B1 is remote and HTTPS only protects the path, not the source; a compromised or spoofed ARPAV host or a faulty publication | C1, C4; fuzzing in CI | **Low** | None for expansion and nesting. Continuous fuzzing (Scorecard *Fuzzing*) is not adopted ([#29](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/29)) | @UMMgl |
| R2 | Registry metadata makes the integration request an arbitrary URL (path traversal, other host, query injection) | `LINKSTAZ` comes from the remote registry and is placed in the request path | C2 (digits-only name, fixed base URL), fuzzed; registry station IDs validated by C4 | **Low** | None | @UMMgl |
| R3 | An oversized or endless response exhausts the memory of the Home Assistant host | The 5 MiB limit (C3) is checked after `response.read()` has buffered the whole body, and `response.json()` in the weather and METAR parts has no limit; only the 30 s timeout (C5) bounds the download | C3 (partial), C5 | **Medium for availability** (a hostile or faulty endpoint could send hundreds of MB within the timeout; the fixed hosts make it unlikely) | **G1**: cap the download while streaming (read in chunks and stop at the limit, or check `Content-Length`) for the XML and bound the JSON paths. Proposed: 2027-01-31 | @UMMgl |
| R4 | Outbound requests overload ARPAV's servers or the user's network, or the integration is used as an amplifier | Many stations, many installations, retry storms | C5 (shared session), C6, C7 | **Low** for the hydrometric part. **Medium** for the weather and METAR parts: they have no concurrency limit and no back-off | **G2**: back-off and concurrency limit for the weather and METAR coordinators. Proposed: 2027-02-28 (with the Gold work) | @UMMgl |
| R5 | A well-formed but false document writes wrong history into the Recorder, or the import is abused to write for other entities | B3: statistics are queued with `source="recorder"` for entity IDs resolved from the registry; ARPAV data is accepted as is | C8, C4; import skips hours the Recorder already holds | **Low** for abuse of other entities. **Low–Medium** for wrong values: a false value that is imported is not corrected by a later fix of the source, because existing hours are never overwritten | None proposed: the integrity of the upstream data cannot be verified by the integration. Documented here and in the README disclaimer | @UMMgl |
| R6 | Example dashboards run JavaScript in the user's browser that has been tampered with, or that executes remote content | B4: `data_generator` is arbitrary JavaScript run by the ApexCharts card with the user's Lovelace privileges; users copy the YAML from the repository | C10: static code, numeric inputs only; the generator and the examples are covered by tests | **Low** for the shipped examples. **Medium** for users who edit or adopt examples from elsewhere: any dashboard editor can run code | **G3**: say in the README that the examples contain JavaScript executed in the browser and that the YAML must be reviewed like code. Proposed: 2026-12-31 | @UMMgl |
| R7 | Third-party Lovelace resources (card-mod, apexcharts-card) are compromised or change behaviour | The examples require two HACS frontend resources that run with full frontend privileges; they are not pinned by the integration | None in the repository (users install them through HACS) | **Medium**, outside the project's control | **G3**: document that both are third-party code the user must trust and keep updated; the examples need only the card-mod rule `#graph-wrapper { min-width: 0; }` and can be used without it. Proposed: 2026-12-31 | @UMMgl |
| R8 | A vulnerable or malicious dependency reaches users or CI | B5: `defusedxml>=0.7.1` is installed by Home Assistant at the latest version; test and CI tooling is large and transitive | C11, C12, C13, C14 | **Low** for the runtime (one dependency, SBOM, audited every run). **Low** for test tooling: 43 Pillow advisories are waived with expiry (C13) | **G5**: the waivers expire on 2027-02-28; remove them when the pytest plugin moves to Home Assistant 2026.11, or renew each with a reviewed reason. Review at the 2027-02-16 quarterly review. The runtime requirement has no upper bound (a deliberate choice, recorded here) | @UMMgl |
| R9 | A compromised pipeline or action publishes a tampered release | B5 and B6: third-party actions, token scope in workflows, release triggered by a tag | C14, C15, C16, C17, C12 | **Low–Medium**: the gate and provenance make tampering detectable by users who verify; most users install through HACS without verifying | **G6**: the gate has never been seen to block a release; run a negative test (a branch tag on a throw-away commit with a deliberately failing check, without publishing) and record it. Proposed: 2027-01-31, needs the maintainer's authorisation as it touches a tag | @UMMgl |
| R10 | Credentials of the GitHub Apps are stolen or misused (private key, derived token, opt-in `workflows` token) | B6: each App has one private key kept by the maintainer outside the repository; tokens give `contents: write` and `pull_requests: write` on this repository | C19 (short-lived, repository-scoped tokens; `workflows` is opt-in); C18; C20 for secrets in the repository | **Medium**: a stolen key allows an attacker to push branches and open pull requests as the bot until revoked. Merging still needs the maintainer (branch protection confirmed on 2026-11-21) | **G7 documented** on 2026-11-21 (section 5, "App credentials"); next action: first rotation, 2027-11. The App permissions are re-read at each quarterly review | @UMMgl |
| R11 | The maintainer's personal login is compromised or misused: it is the only identity that approves and merges, and it can change settings and publish tags | B6: single human identity with administrative rights; the approval of agent pull requests depends on it | C18 (approval by a human, not by agents); GitHub account protection is the maintainer's own (two-factor authentication on the personal account **confirmed by the maintainer on 2026-11-21**, a statement) | **Medium**: a takeover defeats every control above | **G8 closed** by the maintainer's confirmation of 2026-11-21; next check 2027-02-16. The personal login is not used for scripts or agents; approvals are done by hand | @UMMgl |
| R12 | Single-maintainer availability: a vulnerability report or a broken release waits for a person who is absent | One maintainer; `codeowners` lists a second person (`@davidecavestro`) for the weather part only; no backup contact or continuity plan | Response targets in [SECURITY.md](../../SECURITY.md) are explicitly not SLAs; only the latest release is supported; `SECURITY.md` states that there is no backup contact | **Medium, accepted**: reports and releases wait for the maintainer | **G9 closed: decided on 2026-11-21, there is no backup contact** (stated in `SECURITY.md`). The residual risk stays in this table and is reviewed at each quarterly review | @UMMgl |
| R13 | Release workflow is changed in a way that silently weakens the gate (for example a skipped job counted as success) | Tag patterns and `if:` conditions in [release.yml](../../.github/workflows/release.yml) are intricate: pre-release detection uses `contains(ref_name, 'b')` / `'rc'` | C14 (zizmor), C15 (security always runs), review of every workflow change by the maintainer, who must authorise it explicitly | **Low** | None beyond G6 | @UMMgl |

### Gaps, with due dates

| Gap | Risk | Action | Due (proposed unless stated) |
|---|---|---|---|
| G1 | R3 | Stream the download with a byte limit instead of reading the whole body; bound the JSON responses | 2027-01-31 |
| G2 | R4 | Back-off and concurrency limit for the weather and METAR coordinators | 2027-02-28 |
| G3 | R6, R7 | README note on the JavaScript in the examples and on card-mod and apexcharts-card as third-party code | 2026-12-31 |
| G4 | C6 | A test that no more than five stations are fetched at once | 2027-01-31 |
| G5 | R8 | Remove or renew the Pillow waivers | 2027-02-28 (fixed by the waivers' expiry; reviewed on 2027-02-16) |
| G6 | R9 | Demonstrate that a failing security gate blocks publication | 2027-01-31 |
| G7 | R10 | Document key storage, rotation and revocation of the App keys | Documented 2026-11-21; next action: rotation, 2027-11 (proposed) |
| G8 | R11 | Confirm and record the protection of the personal account | Closed: confirmed by the maintainer on 2026-11-21; next check 2027-02-16 |
| G9 | R12 | Backup contact decision | Closed: decided on 2026-11-21, none; residual risk kept in R12 |
| G10 | Evidence | Branch protection, required checks, two-factor authentication and secret-scanning settings are readable only by the maintainer: confirmed by the maintainer on 2026-11-21 (a statement, not a screenshot); to be confirmed again at each quarterly review | 2027-02-16 |

### App credentials: handling and procedure

Statement of the maintainer, 2026-11-21. Each of the two GitHub Apps
(`ummgl-claude-code`, `ummgl-chatgpt`) has **one private key**, generated on
2026-11-15, kept outside the repository in the maintainer's private storage,
with a backup. Keys are never stored in CI secrets or in the repository.
Agents receive only short-lived installation tokens: one hour, limited to one
repository, with minimal permissions; the `workflows` permission only through an
explicit opt-in.

* **Rotation**: generate a new key in the App's settings, replace the key file
  in the private storage, delete the old key in the App's settings. Rotate at
  least yearly (first: 2027-11) and after any suspected exposure.
* **Revocation in an incident**: delete the key in the App's settings and, if
  needed, suspend or uninstall the App. Then review the repository's recent
  activity and rotate any other credential that could be affected.
* The App permissions are re-read at each quarterly review.

## 6. Suppliers and platforms

| Supplier | What is used | Assessment |
|---|---|---|
| ARPAV (Agenzia Regionale per la Prevenzione e Protezione Ambientale del Veneto) | Public open data (CC BY 4.0) from `meteo.arpa.veneto.it` (XML) and `api.arpa.veneto.it` (REST) | No contract, no service level and no integrity guarantee; HTTPS with the hosts' certificates; formats are not versioned. Data is treated as untrusted (B1, B2) and presented as informative only. |
| aviationweather.gov (US National Weather Service) | Public METAR service, JSON | Public API with usage limits; treated as untrusted (B2). |
| `defusedxml` | The only runtime dependency (`>=0.7.1`) | Small, widely used library whose purpose is safe XML parsing; in the SBOM and audited by pip-audit on every run. |
| Home Assistant and HACS | Platform, Recorder, session, installation channel | Trusted platform; the integration relies on Home Assistant's TLS handling and update mechanism. HACS shows no security advisories to users (see the [exercise](exercises/2026-11-vulnerability-report.md)). |
| GitHub | Hosting, Actions, code scanning, private reporting, attestations | Platform trusted for the build and the reporting channel; actions are pinned and audited (C14). |
| Upstream project `davidecavestro/arpa-veneto-weather` | The weather part of the fork | Recorded in [NOTICE](../../NOTICE); no coordination channel for security issues; the second `codeowners` entry is the upstream author. |

## 7. Review

Reviewed when permissions, pipelines, critical dependencies or the
vulnerability process change, and every quarter with
[evidence.md](evidence.md) (first on **2027-02-16**), limited to the rows that
changed and the open gaps. The rows above are checked against the code at each
review: a control whose link no longer resolves becomes a gap.

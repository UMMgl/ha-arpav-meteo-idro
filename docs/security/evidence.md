<!-- SPDX-License-Identifier: Apache-2.0 -->
# Security evidence register

One register for the OpenSSF Best Practices *passing* criteria and the OWASP
SAMM baseline ([#28](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/28),
shared with [#21](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/21) and
[#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18)).

This register is evidence, not a certification: a badge or a self-assessment
is a declaration, the links below are what can be checked. Nothing here claims
conformity with the Cyber Resilience Act (see [cra-scope.md](cra-scope.md)).

## How to read it

* **Evidence** is a link to a file, a test, a merged pull request, a workflow
  run or a release asset. Relative links point to the repository at the
  commit you are reading; `main` runs and releases are pinned by URL.
* **Owner** is the person accountable for the control. The project has one
  maintainer, `@UMMgl`; AI agents prepare changes through their own GitHub App
  identity and never approve or merge (see
  [CONTRIBUTING.md](../../CONTRIBUTING.md)).
* **Reviewed** is the date the row was last checked against its evidence.
* **Gap / due** is empty when the evidence covers the criterion. Due dates were
  confirmed by the maintainer on 2026-11-16.
* Review cadence: after relevant changes (permissions, pipelines, critical
  dependencies, vulnerability handling) and quarterly, limited to changed
  rows and open gaps. First fixed review: **2027-02-16**.

Reviewed on **2026-11-16** against `main` (merge of
[#39](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/39)).

## Reference runs and releases

| Short name | Link |
|---|---|
| `main` Security run | [run 43775005671](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671) (gitleaks, bandit, pip-audit, zizmor, CodeQL) |
| `main` Tests run | [run 43775005676](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005676) |
| `main` Lint run | [run 43775005621](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005621) |
| `main` Validate run | [run 43775005780](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005780) (hassfest, HACS) |
| `main` Scorecard run | [run 43775005629](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005629) |
| Release 0.16.0 | [release](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/tag/0.16.0), [Release run 44845687536](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/44845687536) on tag `0.16.0` (commit `663fb0b`; jobs *Release security gate* – gitleaks, bandit and pip-audit, zizmor, CodeQL for python and actions – and *Release quality tier* – Silver ratchet and per-module coverage – all passed before *Release* published); assets: ZIP, [SBOM](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.16.0/ha-arpav-meteo-idro.cdx.json), [SHA256SUMS](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.16.0/SHA256SUMS), [attestation bundle](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.16.0/ha-arpav-meteo-idro.intoto.jsonl); published 2026-11-21 |
| Release 0.15.5 | [release](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/tag/0.15.5), [Release run 43774490878](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43774490878); assets: ZIP, [SBOM](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.cdx.json), [SHA256SUMS](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/SHA256SUMS), [attestation bundle](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.intoto.jsonl) |

Overall declaration (not proof by itself):
[OpenSSF Best Practices, project 16742](https://www.bestpractices.dev/en/projects/16742),
*passing* earned on 2026-11-15; the README carries the badge.

## 1. OpenSSF Best Practices – passing criteria

Answers follow the draft kept by the maintainer (`OPENSSF_BESTPRACTICES_PASSING.md`,
outside the repository) after the two documentation gaps were closed by
[#40](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/40). *Met* = evidence
exists; *N/A* = not applicable with the reason given.

### Basics

| Criterion | Status | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| description_good | Met | [README.md](../../README.md) (introduction) | @UMMgl | 2026-11-16 | |
| interact | Met | [Issues](https://github.com/UMMgl/ha-arpav-meteo-idro/issues), [CONTRIBUTING.md](../../CONTRIBUTING.md), [SECURITY.md](../../SECURITY.md) | @UMMgl | 2026-11-16 | |
| contribution | Met | [CONTRIBUTING.md](../../CONTRIBUTING.md) ("GitHub is used for everything") | @UMMgl | 2026-11-16 | |
| contribution_requirements | Met | [CONTRIBUTING.md](../../CONTRIBUTING.md) ("Requirements for acceptable contributions", licensing); closed by [#40](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/40) | @UMMgl | 2026-11-16 | |
| floss_license | Met | [LICENSE](../../LICENSE) (Apache-2.0), [LICENSE-BSD-3-Clause](../../LICENSE-BSD-3-Clause), [NOTICE](../../NOTICE) | @UMMgl | 2026-11-16 | |
| floss_license_osi | Met | Apache-2.0 and BSD-3-Clause are both OSI-approved (SPDX expression in [pyproject.toml](../../pyproject.toml)) | @UMMgl | 2026-11-16 | |
| license_location | Met | [LICENSE](../../LICENSE), [LICENSE-BSD-3-Clause](../../LICENSE-BSD-3-Clause) at the repository root; both also inside the release ZIP ([release.yml](../../.github/workflows/release.yml)) | @UMMgl | 2026-11-16 | |
| documentation_basics | Met | [README.md](../../README.md) (installation, configuration, troubleshooting) | @UMMgl | 2026-11-16 | |
| documentation_interface | Met | [README.md](../../README.md) (entities, attributes, actions), [services.yaml](../../custom_components/arpav_meteo_idro/services.yaml) | @UMMgl | 2026-11-16 | |
| sites_https | Met | Repository, issues and releases are served by GitHub over HTTPS | @UMMgl | 2026-11-16 | |
| discussion | Met | [Issues](https://github.com/UMMgl/ha-arpav-meteo-idro/issues) and [pull requests](https://github.com/UMMgl/ha-arpav-meteo-idro/pulls) | @UMMgl | 2026-11-16 | |
| english | Met | Documentation, issues and code are in English (Italian UI translation in [it.json](../../custom_components/arpav_meteo_idro/translations/it.json)) | @UMMgl | 2026-11-16 | |
| maintained | Met | [Releases](https://github.com/UMMgl/ha-arpav-meteo-idro/releases) 0.15.0–0.15.5 in November 2026 | @UMMgl | 2026-11-16 | Single maintainer, no continuity plan; revisit at each quarterly review |

### Change control

| Criterion | Status | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| repo_public | Met | <https://github.com/UMMgl/ha-arpav-meteo-idro> | @UMMgl | 2026-11-16 | |
| repo_track | Met | Git history; changes reach `main` through [merged pull requests](https://github.com/UMMgl/ha-arpav-meteo-idro/pulls?q=is%3Apr+is%3Amerged) | @UMMgl | 2026-11-16 | Branch protection settings are not readable by the App token; maintainer-confirmed on 2026-11-16; the repository has no rulesets (API `rules/branches/main` returned an empty list) |
| repo_interim | Met | Work happens on branches and pull requests before merge (e.g. [#39](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/39)) | @UMMgl | 2026-11-16 | |
| repo_distributed | Met | Git | @UMMgl | 2026-11-16 | |
| version_unique | Met | Unique tags 0.15.0–0.15.5 ([releases](https://github.com/UMMgl/ha-arpav-meteo-idro/releases)); the manifest version is set from the tag in [release.yml](../../.github/workflows/release.yml) | @UMMgl | 2026-11-16 | |
| version_semver | Met | MAJOR.MINOR.PATCH tags, `b`/`rc` pre-release suffixes ([SECURITY.md](../../SECURITY.md), "Verifying a release") | @UMMgl | 2026-11-16 | |
| version_tags | Met | One git tag per release | @UMMgl | 2026-11-16 | |
| release_notes | Met | GitHub release notes generated per tag ([release.yml](../../.github/workflows/release.yml), changelog step); [CHANGELOG.md](../../CHANGELOG.md) | @UMMgl | 2026-11-16 | |
| release_notes_vulns | Met (no applicable case) | No publicly known runtime vulnerability has been fixed in a release. The 0.15.4 hardening ([#22](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/22), [#16](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/16)) is described in the pull requests but is not a security entry in the [0.15.4 notes](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/tag/0.15.4) | @UMMgl | 2026-11-16 | Add a "Security" section to the release notes when a vulnerability is fixed; due: first such release |

### Reporting

| Criterion | Status | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| report_process | Met | [CONTRIBUTING.md](../../CONTRIBUTING.md) ("Report bugs"), [issue template](../../.github/ISSUE_TEMPLATE/bug_report.md) | @UMMgl | 2026-11-16 | |
| report_tracker | Met | [GitHub issues](https://github.com/UMMgl/ha-arpav-meteo-idro/issues) | @UMMgl | 2026-11-16 | |
| report_responses | Met | Issues answered by the maintainer in [the public history](https://github.com/UMMgl/ha-arpav-meteo-idro/issues?q=is%3Aissue) | @UMMgl | 2026-11-16 | |
| enhancement_responses | Met | Enhancements are triaged in [ROADMAP.md](../../ROADMAP.md) and issues | @UMMgl | 2026-11-16 | |
| report_archive | Met | Issues are public and searchable | @UMMgl | 2026-11-16 | |
| vulnerability_report_process | Met | [SECURITY.md](../../SECURITY.md) ("Reporting a vulnerability") | @UMMgl | 2026-11-16 | |
| vulnerability_report_private | Met | GitHub private vulnerability reporting, enabled (repository API `private-vulnerability-reporting` returned `enabled: true` on 2026-11-16); link in [SECURITY.md](../../SECURITY.md) | @UMMgl | 2026-11-16 | |
| vulnerability_report_response | Met | Targets in [SECURITY.md](../../SECURITY.md) ("Response targets"): acknowledgement within 7 days, triage within 2 weeks; no report received so far | @UMMgl | 2026-11-16 | Targets are internal, not SLAs; backup contact not defined, due with S3 (0.16.x) |

### Quality

| Criterion | Status | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| build | N/A | Python integration without a build step; the release workflow only packages the ZIP ([release.yml](../../.github/workflows/release.yml)) | @UMMgl | 2026-11-16 | |
| build_common_tools | Met | GitHub Actions, pip | @UMMgl | 2026-11-16 | |
| build_floss_tools | Met | Python, pip, pytest, Ruff (all FLOSS) | @UMMgl | 2026-11-16 | |
| test | Met | [tests/](../../tests), [Tests run on `main`](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005676) | @UMMgl | 2026-11-16 | |
| test_invocation | Met | `python -m pytest tests` in [CONTRIBUTING.md](../../CONTRIBUTING.md) and [tests.yml](../../.github/workflows/tests.yml) | @UMMgl | 2026-11-16 | |
| test_most | Met | Coverage measured in CI with a floor (`fail_under` in [pyproject.toml](../../pyproject.toml), [#55](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/55)) | @UMMgl | 2026-11-16 | Floor is 70 %; target above 95 % tracked in [#5](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/5) |
| test_continuous_integration | Met | [tests.yml](../../.github/workflows/tests.yml) on every pull request and push to `main` | @UMMgl | 2026-11-16 | |
| test_policy | Met | [CONTRIBUTING.md](../../CONTRIBUTING.md) ("Tests"); [#40](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/40) | @UMMgl | 2026-11-16 | |
| tests_are_added | Met | Recent pull requests add tests, e.g. [#34](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/34), [#35](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/35), [#37](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/37) | @UMMgl | 2026-11-16 | |
| tests_documented_added | Met | [CONTRIBUTING.md](../../CONTRIBUTING.md) ("Tests") | @UMMgl | 2026-11-16 | |
| warnings | Met | Ruff ([lint.yml](../../.github/workflows/lint.yml), [.ruff.toml](../../.ruff.toml)), bandit and zizmor ([security.yml](../../.github/workflows/security.yml)) | @UMMgl | 2026-11-16 | |
| warnings_fixed | Met | Checks green on `main`: [Security](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671), [Lint](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005621) | @UMMgl | 2026-11-16 | |
| warnings_strict | Met | Findings fail the checks; the required checks are listed in [CONTRIBUTING.md](../../CONTRIBUTING.md) | @UMMgl | 2026-11-16 | Required-check settings are confirmed by the maintainer only |

### Security

| Criterion | Status | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| know_secure_design | Met | OWASP review in [#21](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/21); `defusedxml` and size limit in [hydro.py](../../custom_components/arpav_meteo_idro/hydro.py); least-privilege `permissions:` in the [workflows](../../.github/workflows) | @UMMgl | 2026-11-16 | |
| know_common_errors | Met | Same; fuzzing of the parser ([test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py)) | @UMMgl | 2026-11-16 | |
| crypto_published, crypto_call, crypto_floss, crypto_keylength, crypto_working, crypto_weaknesses, crypto_pfs, crypto_password_storage, crypto_random | N/A | The integration implements no cryptography and stores no passwords; HTTPS is handled by Home Assistant's aiohttp session | @UMMgl | 2026-11-16 | |
| delivery_mitm | Met | Releases over HTTPS from GitHub; [SHA256SUMS](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/SHA256SUMS) and [attestation bundle](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.intoto.jsonl) | @UMMgl | 2026-11-16 | |
| delivery_unsigned | Met | No hash is fetched over plain HTTP; verification steps in [SECURITY.md](../../SECURITY.md) ("Verifying a release") | @UMMgl | 2026-11-16 | |
| vulnerabilities_fixed_60_days | Met | pip-audit on every requirements file in every CI run and weekly ([security.yml](../../.github/workflows/security.yml), [`main` run](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671)); the one accepted finding (test tooling only) is documented in [SECURITY.md](../../SECURITY.md) | @UMMgl | 2026-11-16 | Accepted Pillow findings in `requirements_test.txt` expire when the pytest plugin moves to Home Assistant 2026.11 ([ignore list](../../.github/pip-audit-ignore-test.txt)) |
| vulnerabilities_critical_fixed | Met | Same | @UMMgl | 2026-11-16 | |
| no_leaked_credentials | Met | The integration needs no credentials; gitleaks over the full history ([security.yml](../../.github/workflows/security.yml), `secrets` job) | @UMMgl | 2026-11-16 | GitHub secret scanning with push protection is enabled per the maintainer; the setting is not readable by the App token |

### Analysis

| Criterion | Status | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| static_analysis | Met | CodeQL (Python, Actions), bandit, Ruff: [security.yml](../../.github/workflows/security.yml), [lint.yml](../../.github/workflows/lint.yml) | @UMMgl | 2026-11-16 | |
| static_analysis_common_vulnerabilities | Met | CodeQL `security-extended` queries, bandit | @UMMgl | 2026-11-16 | |
| static_analysis_fixed | Met | Required checks must pass before merge | @UMMgl | 2026-11-16 | |
| static_analysis_often | Met | Every pull request, every push to `main`, weekly schedule | @UMMgl | 2026-11-16 | |
| dynamic_analysis | Met | Hypothesis property-based fuzzing of the XML parser: [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py), [#34](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/34) | @UMMgl | 2026-11-16 | Continuous fuzzing (Scorecard *Fuzzing*) not adopted; see [#29](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/29) |
| dynamic_analysis_unsafe | N/A | Python is memory-safe | @UMMgl | 2026-11-16 | |
| dynamic_analysis_enable_assertions | Met | pytest runs with assertions enabled | @UMMgl | 2026-11-16 | |
| dynamic_analysis_fixed | Met | The fuzzing found one parser bug (`parse_instant`), fixed in [#34](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/34) ([CHANGELOG.md](../../CHANGELOG.md)) | @UMMgl | 2026-11-16 | |

## 2. OWASP SAMM v2 – level 1 baseline

> **Status: draft – to be validated by the maintainer.** Prepared by an AI
> agent from repository evidence on 2026-11-16. The ratings are a first
> proposal for a one-off validation session with the maintainer; they have not
> been confirmed and must not be quoted as a SAMM assessment result.

Scale used: **Yes** = the level-1 activity is in place and evidenced;
**Partial** = in place for part of the scope or not formalised; **No** = not
in place. Activity wording is the level-1 objective of each stream in the
[SAMM v2 model](https://owaspsamm.org/model/). Scope: this repository, its CI
and its releases (one maintainer, no organisation).

### Governance

| Practice – stream (level-1 activity) | Rating | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| Strategy & Metrics – Create and Promote (identify organisational drivers related to risk tolerance) | Partial | Drivers recorded in [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18) (scope decision 2026-11-15) and [cra-scope.md](cra-scope.md) | @UMMgl | 2026-11-16 | Risk tolerance not stated explicitly; state it in the S3 risk analysis, 0.16.x |
| Strategy & Metrics – Measure and Improve (define metrics) | Partial | Indicators proposed in [#28](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/28) (releases with complete evidence, expired exceptions); Scorecard runs weekly ([run](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005629)) | @UMMgl | 2026-11-16 | Metrics not yet collected; first values at the 2027-02-16 review |
| Policy & Compliance – Policy and Standards (security baseline of policies and standards) | Yes | [SECURITY.md](../../SECURITY.md), [CONTRIBUTING.md](../../CONTRIBUTING.md) (requirements for contributions), [quality_scale.yaml](../../custom_components/arpav_meteo_idro/quality_scale.yaml) | @UMMgl | 2026-11-16 | |
| Policy & Compliance – Compliance Management (identify third-party compliance drivers) | Yes | [cra-scope.md](cra-scope.md) (CRA), data licence in [README.md](../../README.md) ("Data provenance", CC BY 4.0), [NOTICE](../../NOTICE) | @UMMgl | 2026-11-16 | |
| Education & Guidance – Training and Awareness (security awareness training for developers) | No | None; the maintainer applies OWASP practices ([#21](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/21)) | @UMMgl | 2026-11-16 | Record a short self-study (e.g. OWASP CI/CD Top 10) at the 2027-02-16 review |
| Education & Guidance – Organization and Culture (security champion in each team) | Yes (trivially) | Single-maintainer project: the maintainer is the security contact ([SECURITY.md](../../SECURITY.md)) | @UMMgl | 2026-11-16 | Maintainer to confirm that this counts |

### Design

| Practice – stream (level-1 activity) | Rating | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| Threat Assessment – Application Risk Profile (basic assessment of likelihood and impact) | Partial | Summary in [SECURITY.md](../../SECURITY.md) ("What the integration does"); OWASP review in [#21](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/21) | @UMMgl | 2026-11-16 | Documented risk assessment: S3, 0.16.x |
| Threat Assessment – Threat Modeling (best-effort, risk-based modelling) | No | None beyond the points above | @UMMgl | 2026-11-16 | Brainstorm-level threat list (remote XML, outbound requests, Recorder writes, dependencies, CI/CD, App credentials) in S3, 0.16.x |
| Security Requirements – Software Requirements (security objectives mapped to functional requirements) | Partial | Input limits and parsing rules in [hydro.py](../../custom_components/arpav_meteo_idro/hydro.py); tests in [test_hydro.py](../../tests/test_hydro.py) | @UMMgl | 2026-11-16 | Objectives not written down as requirements; S3 |
| Security Requirements – Supplier Security (evaluate the supplier) | Partial | Data source is ARPAV open data (CC BY 4.0, [README.md](../../README.md) "Data provenance"); runtime dependency `defusedxml` ([manifest.json](../../custom_components/arpav_meteo_idro/manifest.json)); upstream fork recorded in [NOTICE](../../NOTICE) | @UMMgl | 2026-11-16 | No documented evaluation of ARPAV, the METAR service and `defusedxml` as suppliers; S3 |
| Secure Architecture – Architecture Design (basic security principles during design) | Partial | Least-privilege workflows; bounded requests ([hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py): timeout, concurrency limit); no listening ports, no credentials | @UMMgl | 2026-11-16 | Principles not written down; S3 |
| Secure Architecture – Technology Management (elicit technologies and integrations to identify risk) | Yes | [SBOM of every release](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.cdx.json); hashed tool requirements (`requirements_*.txt`); [diagnostics.py](../../custom_components/arpav_meteo_idro/diagnostics.py) redacts location data | @UMMgl | 2026-11-16 | |

### Implementation

| Practice – stream (level-1 activity) | Rating | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| Secure Build – Build Process (formal, repeatable build) | Yes | [release.yml](../../.github/workflows/release.yml), actions pinned to full commit SHAs, tools installed with `--require-hashes`; [Release run 43774490878](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43774490878) | @UMMgl | 2026-11-16 | `requirements_test.txt` is not hash-pinned yet (Scorecard alerts #2, #3, #8): planned for 0.16.0 |
| Secure Build – Software Dependencies (BOM of applications, opportunistic analysis) | Yes | [SBOM (CycloneDX)](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.cdx.json) in every release since 0.15.4; pip-audit and Dependabot ([dependabot.yml](../../.github/dependabot.yml)) | @UMMgl | 2026-11-16 | |
| Secure Deployment – Deployment Process (formalise the deployment, secure tooling) | Yes | Tag-triggered [release.yml](../../.github/workflows/release.yml); Gold quality gate before publishing ([#39](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/39)); [SHA256SUMS](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/SHA256SUMS) and [attestation](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.15.5/ha-arpav-meteo-idro.intoto.jsonl) | @UMMgl | 2026-11-16 | Security checks are not yet a release gate on the tagged commit: S4, 0.16.0 (workflow change, needs maintainer authorisation) |
| Secure Deployment – Secret Management (limit access to production secrets) | Partial | The project has no runtime secrets; release uses the workflow `GITHUB_TOKEN` and OIDC with narrow `permissions:`; AI agents act through a dedicated GitHub App ([#27](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/27), [CONTRIBUTING.md](../../CONTRIBUTING.md)) | @UMMgl | 2026-11-16 | Handling of the App credentials to be written up in S3 |
| Defect Management – Defect Tracking (structured tracking of security defects) | Yes | GitHub issues, code scanning alerts, private vulnerability reports; response targets in [SECURITY.md](../../SECURITY.md) | @UMMgl | 2026-11-16 | |
| Defect Management – Metrics and Feedback (review recorded defects, derive quick wins) | Yes | Scorecard findings turned into issues #24–#27 ([#21](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/21)), all closed | @UMMgl | 2026-11-16 | Repeat at each quarterly review |

### Verification

| Practice – stream (level-1 activity) | Rating | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| Architecture Assessment – Architecture Validation (identify components, review basic security provisioning) | Partial | Component list in [README.md](../../README.md) and [hydro_topology.md](../hydro_topology.md); no security review of it | @UMMgl | 2026-11-16 | Fold into the S3 risk analysis, 0.16.x |
| Architecture Assessment – Architecture Mitigation (ad-hoc review for unmitigated threats) | Partial | OWASP review in [#21](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/21) produced fixes ([#22](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/22)) | @UMMgl | 2026-11-16 | Repeat after the S3 analysis |
| Requirements-driven Testing – Control Verification (test for software security controls) | Partial | Parser limits and rejection of HTML/oversized documents are tested ([test_hydro.py](../../tests/test_hydro.py)); the weather part's network handling is not covered | @UMMgl | 2026-11-16 | Weather-part session and error-path tests, 0.16.0 (pull request [#60](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/60) open at the time of writing; [#7](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/7), [#5](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/5)) |
| Requirements-driven Testing – Misuse/Abuse Testing (security fuzz testing) | Yes | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py), [#34](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/34) | @UMMgl | 2026-11-16 | |
| Security Testing – Scalable Baseline (automated security testing tools) | Yes | [Security run on `main`](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671): CodeQL, bandit, pip-audit, gitleaks, zizmor | @UMMgl | 2026-11-16 | |
| Security Testing – Deep Understanding (manual testing of high-risk components) | No | None | @UMMgl | 2026-11-16 | Manual review of `hydro.py` against the S3 threat list, 0.16.x |

### Operations

| Practice – stream (level-1 activity) | Rating | Evidence | Owner | Reviewed | Gap / due |
|---|---|---|---|---|---|
| Incident Management – Incident Detection (best-effort detection from log data) | Partial | Code scanning and Dependabot alerts; the integration logs failed requests ([hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py)); Home Assistant owns the runtime logs | @UMMgl | 2026-11-16 | No detection in users' installations (outside the project's control) |
| Incident Management – Incident Response (roles and responsibilities) | Partial | Maintainer is the single contact ([SECURITY.md](../../SECURITY.md)); acknowledgement 7 days, triage 2 weeks as internal targets | @UMMgl | 2026-11-16 | No backup contact; no simulated report: S3 exercise, 0.16.x |
| Environment Management – Configuration Hardening (best-effort hardening) | Partial | Workflows with least-privilege `permissions:` and zizmor; secret scanning with push protection (maintainer-confirmed) | @UMMgl | 2026-11-16 | Branch protection and required checks are not readable by the App token: maintainer-confirmed on 2026-11-16 (the App token gets HTTP 403 on these endpoints) |
| Environment Management – Patching and Updating (best-effort patching) | Yes | [dependabot.yml](../../.github/dependabot.yml), weekly pip-audit, lock refresh procedure in [SECURITY.md](../../SECURITY.md) | @UMMgl | 2026-11-16 | |
| Operational Management – Data Protection (basic data protection practices) | Yes | No personal data processed; diagnostics redact coordinates ([diagnostics.py](../../custom_components/arpav_meteo_idro/diagnostics.py)); [SECURITY.md](../../SECURITY.md) ("What the integration does") | @UMMgl | 2026-11-16 | |
| Operational Management – System Decommissioning / Legacy Management (decommission unused services; manage upgrades individually) | Partial | Only the latest release is supported ([SECURITY.md](../../SECURITY.md)); deprecation of the manual station order announced a release ahead ([#38](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/38)) | @UMMgl | 2026-11-16 | Upgrade guidance for users of older releases to be written with S3 |

Summary of the draft ratings (30 level-1 activities): 13 Yes, 14 Partial, 3 No.

## 3. Gaps linked to other work

| Gap | Where it is tracked | Target |
|---|---|---|
| Security checks as release gate on the tagged SHA | S4 under [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18) | 0.16.0 |
| Hash-pinned test requirements (Scorecard alerts #2, #3, #8) | code scanning | 0.16.0 |
| Weather part on the Home Assistant session, coverage | [#7](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/7), [#5](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/5) | 0.16.0 / 0.16.x |
| Risk analysis, threat list, simulated vulnerability report, backup contact | S3 under [#18](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/18) | 0.16.x |
| SAMM baseline validation, first dated review | [#28](https://github.com/UMMgl/ha-arpav-meteo-idro/issues/28) | 2027-02-16 |

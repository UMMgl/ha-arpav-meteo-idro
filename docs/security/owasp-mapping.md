<!-- SPDX-License-Identifier: Apache-2.0 -->
# OWASP mapping

Where the OWASP controls are built into the code and the CI/CD pipeline of this
project, in one place: the OWASP Top 10 (2021), the OWASP Top 10 CI/CD Security
Risks, and the OWASP ASVS 5.0 level 1 identifiers that correspond to the
[security requirements](security-requirements.md) (SR-n).

This page maps; it does not certify. It is evidence of the same kind as
[evidence.md](evidence.md): every control below is a file, a workflow or a test
that exists on `main` and can be followed through its link, and anything that is
missing is listed as a gap or as *Partial* or *Open*, never as a control. It
claims no conformity with the OWASP Top 10, the ASVS or the Cyber Resilience Act
(see [cra-scope.md](cra-scope.md)). The ASVS is written for web applications; the
integration is not one (it has no user interface and opens no port), so most of
its chapters do not apply and only a few identifiers are mapped.

Written on **2026-11-26** against `main` at `13bd977` (pull request
[#83](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/83) is merged). Review
with the evidence register: every quarter (first review **2027-02-16**) and
whenever a workflow or a requirement changes. A link that no longer resolves
turns the row into a gap.

How to read the columns of the tables: *When it runs* is read from the `on:`
block of the workflow; *Required on `main`* says whether the job is in the list
of [section 4](#4-required-checks-on-main); *Status* is **Met** (the control
exists and is evidenced), **Partial** (it exists but does not cover the whole
category, said in the row), **Open** (a gap, linked) or **Not applicable**
(with the reason).

## 1. OWASP Top 10 (2021)

Category list checked on 2026-11-26 against the official repository
[OWASP/Top10](https://github.com/OWASP/Top10/tree/master/2021/docs/en)
(`2021/docs/en`, files `A01_2021` to `A10_2021`).

| Category | Applicable? | Requirements | Control (file, tool, test) | When it runs | Required on `main` | Status |
|---|---|---|---|---|---|---|
| **A01** Broken Access Control | **No, nothing to control.** The integration opens no port and serves no endpoint ([design principle P1](design-principles.md)); access to entities and to the config flow is enforced by Home Assistant. | None | Nothing to test. The only data it writes are the states of its own entities and the Recorder statistics of its own sensors (SR-12, [`hydro_statistics.py`](../../custom_components/arpav_meteo_idro/hydro_statistics.py)) | – | – | Not applicable |
| **A02** Cryptographic Failures | **Limited.** The integration implements no cryptography and stores no secret or personal data. Transport security is the Home Assistant web session talking to fixed `https://` hosts ([`const.py`](../../custom_components/arpav_meteo_idro/const.py), [`hydro.py`](../../custom_components/arpav_meteo_idro/hydro.py), [`metar.py`](../../custom_components/arpav_meteo_idro/metar.py)). | SR-4 (fixed base URL), SR-10 (no credentials, no personal data) | gitleaks over the whole history ([security.yml `secrets`](../../.github/workflows/security.yml#L19-L34)); bandit ([security.yml `python`](../../.github/workflows/security.yml#L53-L54)) flags weak cryptography and unverified TLS in the code. No test asserts that every URL is `https://`: it is checked by reading the code | push to `main`, pull request, tag (release gate), weekly | Yes (Secrets, Code and dependencies) | Met (partly by review) |
| **A03** Injection | **Yes**, for what the integration reads from outside: remote XML and JSON, the station file name taken from the registry, and the sensor attributes read by the example dashboards. There is no SQL, no shell and no HTML in the integration. | SR-1, SR-2, SR-4, SR-5 | `defusedxml` only, entities refused, document type and size checked ([`hydro.py`](../../custom_components/arpav_meteo_idro/hydro.py)); file name accepted only as digits plus `.xml`; strict number, instant and ID patterns. CodeQL `security-extended` for Python and for Actions ([security.yml `codeql`](../../.github/workflows/security.yml#L97-L122)); bandit; [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (entities, arbitrary and mutated bytes, nesting, hostile file names, numbers and instants), [test_hydro.py](../../tests/test_hydro.py), [test_example_dashboards.py](../../tests/test_example_dashboards.py) for the JavaScript of the examples. The release workflow reads the tag as data, never in a shell or `sed` program ([release.yml](../../.github/workflows/release.yml#L97-L101), [#77](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/77)) | CodeQL, bandit: push to `main`, pull request, tag, weekly. Tests: push to `main` and `feature/**`, pull request, tag (stable releases) | Yes (CodeQL python and actions, Code and dependencies, Pytest) | Met |
| **A04** Insecure Design | **Yes.** Security objectives, design principles, trust boundaries and a risk assessment are written down and reviewed. | All SR-n ([security-requirements.md](security-requirements.md)) | [design-principles.md](design-principles.md) (P1-P9), [risk-assessment.md](risk-assessment.md) (assets, trust boundaries B1-B6, risks R1-R13, controls C1-C20, gaps), the tabletop [exercise](exercises/2026-11-vulnerability-report.md). The requirements are tested where the SR table says so; SR-6, SR-10 are partly checked by review. Open requirement: SR-8 (G2) | Reviewed quarterly and on change; tests as in A03 | Pytest: yes. The documents are not checked by CI | Partial (SR-8 open, see [section 5](#5-open-gaps)) |
| **A05** Security Misconfiguration | **Yes**, for the pipelines and the repository; the integration has no server configuration. | SR-17 | Workflows with `permissions:` set, actions pinned to commit SHAs, `persist-credentials: false`, no `pull_request_target` ([.github/workflows](../../.github/workflows)); zizmor on every change ([security.yml `workflows`](../../.github/workflows/security.yml#L76-L95)); CodeQL for Actions; hassfest and HACS validation ([validate.yaml](../../.github/workflows/validate.yaml#L18-L28)); OpenSSF Scorecard ([scorecard.yml](../../.github/workflows/scorecard.yml)). Repository settings (branch protection, secret scanning, push protection) are the maintainer's statement of 2026-11-21 ([risk assessment](risk-assessment.md), C18, C20, gap G10): the App token cannot read them | zizmor and CodeQL: as A03. Validate: push to `main` and `feature/**`, pull request. Scorecard: push to `main`, weekly, branch protection change | Yes (Workflows, CodeQL actions, validate, validate-hacs). Scorecard: no | Met (settings by statement) |
| **A06** Vulnerable and Outdated Components | **Yes.** One runtime dependency (`defusedxml`), plus the test, CI and release tooling. | SR-16 | pip-audit on the manifest requirements and on every `requirements*.txt`, a finding fails the check ([security.yml `python`](../../.github/workflows/security.yml#L56-L74)); Dependabot, daily, for GitHub Actions and pip ([dependabot.yml](../../.github/dependabot.yml)); OSV through the Scorecard *Vulnerabilities* check ([scorecard.yml](../../.github/workflows/scorecard.yml), waivers in [osv-scanner.toml](../../osv-scanner.toml)); CycloneDX SBOM in every release ([release.yml](../../.github/workflows/release.yml#L127-L155)); dated waivers for the 43 Pillow advisories in the test lock, expiring 2027-02-28 (C13, G5) | pip-audit: push to `main`, pull request, tag, weekly (Monday). Dependabot: daily. Scorecard: push to `main`, weekly | Yes (Code and dependencies). Dependabot and Scorecard: no | Met (waivers for test tooling only: G5) |
| **A07** Identification and Authentication Failures | **No.** The integration has no authentication, no account and no session, and stores no credentials (SR-10). The users and the access to Home Assistant belong to Home Assistant. | SR-10 (no credential is held, asked for or logged) | No credential field in the config flows ([config_flow.py](../../custom_components/arpav_meteo_idro/config_flow.py), [hydro_config_flow.py](../../custom_components/arpav_meteo_idro/hydro_config_flow.py)); gitleaks as in A02. Authentication of the *maintainer and agents* is a pipeline matter: see CICD-SEC-2 and CICD-SEC-6 | – | – | Not applicable |
| **A08** Software and Data Integrity Failures | **Yes**, for the release artefacts and the CI tooling, and for the data written to the Recorder. | SR-12, SR-14, SR-15, SR-16, SR-17 | Tools installed with `--require-hashes` from lock files; actions pinned by SHA; build provenance attestation of the ZIP, `SHA256SUMS`, SBOM and offline attestation bundle ([release.yml](../../.github/workflows/release.yml#L127-L187)), verification steps in [SECURITY.md](../../SECURITY.md#verifying-a-release); release only after the security gate on the tagged commit ([release.yml](../../.github/workflows/release.yml#L12-L20)); statistics written only for the integration's own sensors and never over existing hours ([test_hydro_statistics.py](../../tests/test_hydro_statistics.py)). No unsafe deserialisation: the integration parses XML with `defusedxml` and JSON with the standard parser | Lock files: every install. Release steps: on a tag. Gate: on a tag | The gate runs the Security jobs, which are required checks; the release job itself is not a pull request check | Partial: the gate has never been seen to block a release (G6, SR-14 negative proof). Most users install through HACS without verifying the attestation (risk R9) |
| **A09** Security Logging and Monitoring Failures | **Partly.** The integration is a client and writes only to the Home Assistant log; there is no audit trail of its own and no monitoring of the users' installations (outside the project's control, accepted: SAMM *Incident Detection*, Partial in [evidence.md](evidence.md)). | SR-9 (a failure is handled and visible, never silent), SR-10 (log content), SR-11 (diagnostics redacted) | Failures keep the last good value and flag it as stale ([hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py), [test_hydro_ha.py](../../tests/test_hydro_ha.py)); diagnostics redact location data ([diagnostics.py](../../custom_components/arpav_meteo_idro/diagnostics.py), [test_gold_ha.py](../../tests/test_gold_ha.py)); gitleaks. No automated test of the log content: the log calls were read on 2026-11-21 (SR-10) | Tests: as in A03. gitleaks: as in A02 | Yes (Pytest, Secrets) | Partial (monitoring of installations out of scope; SR-10 partly by review) |
| **A10** Server-Side Request Forgery (SSRF) | **Yes, in a limited form.** No request target is supplied by the user; the hosts are fixed. The only part of a URL that comes from remote data is the station file name (SR-4). The remaining exposure is that `aiohttp` follows redirects by default, so a redirect answered by an ARPAV host could lead to another destination. | SR-4 | Fixed `https://` base URLs, station file name restricted to digits plus `.xml` and fuzzed ([test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py)); CodeQL `security-extended` (as in A03). No request in the package disables or restricts redirects (`git grep allow_redirects` finds nothing in `custom_components`). Pull request [#82](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/82) proposes to follow redirects manually and re-check every hop against the ARPAV host: **open, not on `main`** | CodeQL: as in A03 | Yes (CodeQL python and actions) | Partial (redirects not restricted until #82 is merged; the risk assessment rates R2 Low and has no gap for this) |

### The newer edition (2025)

The OWASP Top 10 site now leads with the **2025** edition
([top10.owasp.org/2025](https://top10.owasp.org/2025/), read on 2026-11-26),
whose categories are: A01 Broken Access Control, A02 Security Misconfiguration,
A03 Software Supply Chain Failures, A04 Cryptographic Failures, A05 Injection,
A06 Insecure Design, A07 Authentication Failures, A08 Software or Data Integrity
Failures, A09 Security Logging and Alerting Failures, A10 Mishandling of
Exceptional Conditions. This page keeps the 2021 numbering of the table above;
the rows are not renumbered. No row-by-row mapping to the 2025 edition has been
done. As a pointer only: the supply-chain controls of A06 and A08 above are the
ones most relevant to its A03 (Software Supply Chain Failures), and the error
handling of SR-9 to its A10 (Mishandling of Exceptional Conditions).

## 2. OWASP Top 10 CI/CD Security Risks

List checked on 2026-11-26 on
[owasp.org/www-project-top-10-ci-cd-security-risks](https://owasp.org/www-project-top-10-ci-cd-security-risks/)
(an OWASP lab project; the page shows no version number). The workflow files are
in [.github/workflows](../../.github/workflows).

| Risk | Control | Evidence | Status |
|---|---|---|---|
| **CICD-SEC-1** Insufficient Flow Control Mechanisms | **A documented choice.** Changes reach `main` only through pull requests, with required status checks that are strict (the branch must be up to date) and enforced for administrators, as reported by the maintainer's session ([section 4](#4-required-checks-on-main)). Required approvals are **0**, deliberately, until a second contributor exists (a single maintainer cannot approve their own pull request). In practice the maintainer explicitly approves every pull request before it is merged, and agents never approve or merge. A release is published only after the security gate on the tagged commit | [CONTRIBUTING.md](../../CONTRIBUTING.md), [risk-assessment.md](risk-assessment.md) (C18, R11, R13), [release.yml](../../.github/workflows/release.yml#L12-L20) | Met as a documented choice. The settings are the maintainer's statement; whether tags are protected is not verified |
| **CICD-SEC-2** Inadequate Identity and Access Management | One human identity with administrative rights (R11, two-factor authentication stated by the maintainer on 2026-11-21); agents act only through a GitHub App, with short-lived tokens limited to this repository (C19, not verifiable from the repository); no CI secret other than the automatic `GITHUB_TOKEN` | [risk-assessment.md](risk-assessment.md) (C18, C19, R10, R11, App credentials), `git grep "secrets\."` in [.github/workflows](../../.github/workflows) | Partial: the identity controls are statements of the maintainer; keys rotate yearly (first rotation 2027-11, G7) |
| **CICD-SEC-3** Dependency Chain Abuse | Runtime dependency only `defusedxml`; CI, test and release tools installed from hashed lock files; pip-audit on every requirements file; Dependabot daily; SBOM in every release. One step is not hash-checked: the SBOM step of the release installs the manifest requirement (`defusedxml>=0.7.1`) into a throw-away environment without `--require-hashes`, restricted to binary wheels since [#78](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/78) so that no build backend runs on the release runner ([release.yml](../../.github/workflows/release.yml#L150-L152)) | [security.yml](../../.github/workflows/security.yml#L50-L74), [dependabot.yml](../../.github/dependabot.yml), [requirements_security.txt](../../requirements_security.txt), [requirements_release.txt](../../requirements_release.txt), [requirements_ci.txt](../../requirements_ci.txt), [requirements_test.txt](../../requirements_test.txt), SR-16 | Partial (the SBOM install is wheels-only but not hash-checked: a known limitation without a gap number) |
| **CICD-SEC-4** Poisoned Pipeline Execution (PPE) | No `pull_request_target`; `permissions: contents: read` on the pull request workflows; `persist-credentials: false` on every checkout; the release workflow runs only on a tag or by hand and passes the tag through an environment variable, not through the shell; zizmor and CodeQL for Actions on every change; a change to a workflow needs the maintainer's explicit authorisation | [lint.yml](../../.github/workflows/lint.yml#L17-L19), [tests.yml](../../.github/workflows/tests.yml#L17-L18), [release.yml](../../.github/workflows/release.yml#L95-L101), [security.yml](../../.github/workflows/security.yml#L76-L122), SR-17 | Met |
| **CICD-SEC-5** Insufficient PBAC (Pipeline-Based Access Controls) | `permissions: {}` at the top of the release workflow and the permissions of each job set to what it needs (`contents: write`, `id-token: write`, `attestations: write` only in the release job); `contents: read` in the other workflows; `read-all` plus two write scopes in Scorecard. Two open pull requests propose to tighten further: [#79](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/79) (changelog action) and [#80](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/80) (Scorecard permissions); they are not on `main` | [release.yml](../../.github/workflows/release.yml#L9), [release.yml](../../.github/workflows/release.yml#L77-L81), [scorecard.yml](../../.github/workflows/scorecard.yml#L13-L21) | Met, with two proposals pending |
| **CICD-SEC-6** Insufficient Credential Hygiene | gitleaks over the whole history on every change; GitHub secret scanning with push protection (maintainer's statement); no credential stored in the repository or in CI secrets; App keys kept outside the repository, rotated yearly; short-lived App tokens | [security.yml `secrets`](../../.github/workflows/security.yml#L19-L34), [risk-assessment.md](risk-assessment.md) (C19, C20, R10, G7, G10) | Met (push protection and key handling by statement) |
| **CICD-SEC-7** Insecure System Configuration | Jobs run on GitHub-hosted, ephemeral runners (`ubuntu-latest`); no self-hosted runner; hashed tool installs; zizmor; OpenSSF Scorecard published in code scanning. Repository and branch settings are not readable by the App token (gap G10) | [.github/workflows](../../.github/workflows), [scorecard.yml](../../.github/workflows/scorecard.yml), [risk-assessment.md](risk-assessment.md) (G10) | Partial (settings by statement) |
| **CICD-SEC-8** Ungoverned Usage of 3rd Party Services | Every third-party action is pinned to a commit SHA with its version in a comment and updated by Dependabot; zizmor checks the pinning. The pin of the HACS action carries the comment `# main` (a SHA, not a moving reference). The two GitHub Apps are listed in the risk assessment (assets) | [.github/workflows](../../.github/workflows), [dependabot.yml](../../.github/dependabot.yml), [validate.yaml](../../.github/workflows/validate.yaml#L22), [#84](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/84) (hassfest pinned to the `2026.11.0` tag) | Met |
| **CICD-SEC-9** Improper Artifact Integrity Validation | Release ZIP verified at build (expected files, manifest version equal to the tag); build provenance attestation (OIDC), `SHA256SUMS`, CycloneDX SBOM and an offline attestation bundle as release assets; verification steps published. The gate has not yet been seen to block a release (G6) | [release.yml](../../.github/workflows/release.yml#L103-L187), [SECURITY.md](../../SECURITY.md#verifying-a-release), [0.16.0 release](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/tag/0.16.0), SR-14, SR-15 | Met; the negative proof of the gate is open (G6) |
| **CICD-SEC-10** Insufficient Logging and Visibility | Workflow run logs and code scanning alerts (CodeQL, Scorecard) on GitHub; every release run is linked from [evidence.md](evidence.md). There is no alert on a change to branch protection, secrets or workflows beyond the review of every pull request; the GitHub audit log is the maintainer's to read | [evidence.md](evidence.md#reference-runs-and-releases), [scorecard.yml](../../.github/workflows/scorecard.yml) | Partial (accepted for a single-maintainer project) |

## 3. ASVS 5.0 level 1 for the security requirements

Source and version: **OWASP Application Security Verification Standard 5.0.0**,
read from the official repository
[OWASP/ASVS](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/docs_en), tag
`v5.0.0` (commit `180622b1329ee7ed349c9f5ce5e14fa91f42c359`), file
`5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv`,
on 2026-11-26. Only requirements whose level is 1 are listed, and each
identifier below was checked against that file, text and level included. A
requirement without a clear counterpart is written **not mapped**: that is not a
claim that it is met or unmet, only that no level-1 identifier clearly
corresponds. ASVS chapters about passwords, sessions, tokens, OAuth, cookies,
CORS and WebSockets do not apply (no accounts, no sessions, no web interface).

| Requirement | ASVS 5.0 level 1 | Why it corresponds |
|---|---|---|
| SR-1 XML only with `defusedxml` | **V1.5.1** (XML parsers use a restrictive configuration, external entities disabled) | Same objective; entities are refused and tested |
| SR-2 size, type and root element checked | **V2.2.1** (input validated against business or functional expectations, positive validation) | The root element and the document type are checked against what is expected. The size limit is not mapped to V5.2.1, which is about uploaded files |
| SR-3 size limited while downloading | Not mapped | V5.2.1 concerns files accepted by the application, not responses it downloads |
| SR-4 station file name restricted | **V2.2.1** | Positive validation (digits plus `.xml`) of a value taken from outside |
| SR-5 numbers, instants and IDs validated | **V2.2.1** | Positive validation with strict patterns |
| SR-6 timeout and shared session | Not mapped | |
| SR-7 bounded polling and back-off | Not mapped | V6.1.1 is about anti-automation of authentication |
| SR-8 weather and METAR back-off (open) | Not mapped | |
| SR-9 failures never raise into Home Assistant | Not mapped | |
| SR-10 no credentials, no personal data | Not mapped | |
| SR-11 diagnostics redacted | Not mapped | |
| SR-12 Recorder statistics only for own sensors | Not mapped | |
| SR-13 sample list capped and unrecorded | Not mapped | |
| SR-14 release only after the security gate | Not mapped | No level-1 identifier covers the release process |
| SR-15 attestation, checksums, SBOM | Not mapped | |
| SR-16 hashed lock files, pip-audit | **V15.1.1**, **V15.2.1** (partly) | Components with known vulnerabilities fail the check and a waiver expires within a quarter ([SECURITY.md](../../SECURITY.md#pinned-tools-and-dependency-audit)); the project defines no remediation time frames by severity, so V15.1.1 is met only through that waiver rule |
| SR-17 least privilege in workflows | Not mapped | |

## 4. Required checks on `main`

**As reported by the maintainer's session on 2026-11-26.** The GitHub App token
cannot read branch protection (HTTP 403, see C18 and G10 in the
[risk assessment](risk-assessment.md)), so this list is a statement, **not
verified by the author of this page**; the job names below were read in the
workflow files. The maintainer's session reported that the checks are strict
(the branch must be up to date), enforced for administrators, with 0 required
approvals by documented choice (CICD-SEC-1).

| Required check | Workflow and job | What it runs |
|---|---|---|
| Ruff | [lint.yml](../../.github/workflows/lint.yml#L22-L44) `ruff` | `ruff check .` and `mypy` (strict, modules without Home Assistant) |
| Pytest | [tests.yml](../../.github/workflows/tests.yml#L21-L47) `pytest` | The test suite with coverage, then the quality tier check |
| validate | [validate.yaml](../../.github/workflows/validate.yaml#L25-L28) `validate` | hassfest (Home Assistant manifest and integration validation) |
| validate-hacs | [validate.yaml](../../.github/workflows/validate.yaml#L18-L24) `validate-hacs` | HACS validation (category: integration) |
| Secrets (gitleaks) | [security.yml](../../.github/workflows/security.yml#L19-L34) `secrets` | gitleaks over the full history |
| Code and dependencies (bandit, pip-audit) | [security.yml](../../.github/workflows/security.yml#L36-L74) `python` | bandit on `custom_components` and `examples`; pip-audit on the manifest requirements and every `requirements*.txt` |
| CodeQL (python) | [security.yml](../../.github/workflows/security.yml#L97-L122) `codeql` | CodeQL, query suite `security-extended`, Python |
| CodeQL (actions) | [security.yml](../../.github/workflows/security.yml#L97-L122) `codeql` | The same, for the GitHub Actions workflows |
| Workflows (zizmor) | [security.yml](../../.github/workflows/security.yml#L76-L95) `workflows` | zizmor on `.github/workflows`, minimum severity low |

Not required: OpenSSF Scorecard ([scorecard.yml](../../.github/workflows/scorecard.yml):
push to `main`, weekly, on a branch protection change) and Dependabot.

## 5. Open gaps

| Gap | State on 2026-11-26 | Record |
|---|---|---|
| Bounded downloads | **Closed.** Every response is read in chunks and cut at 5 MiB (XML) or 10 MiB (JSON); merged in pull request [#83](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/83) (G1, SR-3, control C3) | [risk-assessment.md](risk-assessment.md#gaps-with-due-dates), [security-requirements.md](security-requirements.md) |
| Back-off and concurrency limit for the weather and METAR coordinators | **Open.** G2, SR-8, risk R4; proposed due 2027-02-28 | [risk-assessment.md](risk-assessment.md#gaps-with-due-dates), [security-requirements.md](security-requirements.md#open-requirements) |
| Negative proof of the release security gate | **Open.** G6, SR-14, risk R9; proposed due 2027-01-31; it needs a tag, so the maintainer's authorisation | [risk-assessment.md](risk-assessment.md#gaps-with-due-dates), [security-requirements.md](security-requirements.md#open-requirements) |
| Redirect restriction of the hydrometric requests | **Open, not on `main`.** Pull request [#82](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/82) proposes it; it has no gap number in the risk assessment (A10 above) | [#82](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/82) |
| VulnCheck scan | **Dropped.** A report-only VulnCheck scan was tried in pull request [#85](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/85), closed on 2026-11-26: according to the maintainer's session it needs a paid subscription (the pull request describes a repository secret, `VC_TOKEN`). It is not a control: the vulnerable-components control is pip-audit, Dependabot and OSV through Scorecard (A06) | [#85](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/85) |

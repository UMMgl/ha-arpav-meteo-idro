# Security policy

## Supported versions

Only the latest release of ARPAV Meteo e Idro receives fixes. No support
period is promised: this is a volunteer project and fixes are made on a
best-effort basis. In practice, fixes are never backported: a user of an older
release is asked to update to the latest one through HACS (it may include other
changes, see the [changelog](CHANGELOG.md)).

## Scope and the Cyber Resilience Act

ARPAV Meteo e Idro is free and open-source software, developed and distributed
by a private maintainer without monetisation, and no commercialisation is
planned (maintainer decision of 2026-11-15). The project therefore treats
itself as outside the commercial scope of the EU Cyber Resilience Act
(Regulation (EU) 2024/2847) and pursues its security practices voluntarily, as
proportionate due diligence. It does not claim conformity with the Act, carries
no CE marking, issues no declaration of conformity and makes no support-period
commitment.

The scope is reviewed if paid support, a sale, an organisation supporting the
project for commercial use or integration into a commercial product appears.
The assessment, its factual basis, the reassessment triggers and the treatment
of each requirement are in [docs/security/cra-scope.md](docs/security/cra-scope.md);
the evidence for the security practices is in
[docs/security/evidence.md](docs/security/evidence.md), the risk analysis with
its open gaps in [docs/security/risk-assessment.md](docs/security/risk-assessment.md)
and the first paper exercise of the process below in
[docs/security/exercises/](docs/security/exercises/2026-11-vulnerability-report.md).

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/UMMgl/ha-arpav-meteo-idro/security/advisories/new),
not in public issues. Include the version, what you observed and how to
reproduce it. A report that reaches the project in another way (a public
issue, a comment) is moved to private reporting, and the public text is removed
or reduced on request.

### What to expect

* The report is read by the maintainer only, and is not shared with anyone else.
  Unpublished details and proofs of concept are not given to AI tools unless the
  maintainer decides so for that report.
* You get an acknowledgement, then the outcome of the triage: whether it is a
  vulnerability, which versions are affected, how severe it is, and whether and
  how it will be fixed.
* No fixing time and no embargo length are promised. You are told the planned
  date of publication beforehand, and are credited if you wish.

### Response targets

These are internal targets of a volunteer project, not service-level
agreements, and they promise no fixing time:

* **acknowledgement** of a report within **7 days**;
* **triage** (is it a vulnerability, how severe, which versions) within
  **2 weeks**;
* a vulnerability that is confirmed to be actively exploited is handled with
  immediate priority;
* when a vulnerability is confirmed, the fix is released in the latest release
  and announced with a GitHub Security Advisory, whatever its severity, unless
  it has no effect on users of a released version. HACS does not show advisories
  to users: the advisory and the release notes are the channels.

## What the integration does

* It only reads public ARPAV open data over HTTPS (no credentials, no personal
  data) and the public METAR service, using the Home Assistant web session.
* XML is parsed with `defusedxml` only (no entity expansion, no external
  resources); documents larger than 5 MB or HTML pages are rejected. The size
  check is made after the document has been downloaded: the download itself is
  bounded only by a 30 second timeout, and the JSON responses of the weather and
  METAR parts have no size limit (a known gap, see
  [docs/security/risk-assessment.md](docs/security/risk-assessment.md)).
* It writes only to the Home Assistant entity states and to the Recorder
  statistics of its own sensors.

## Checks in CI

Every pull request and every push to `main` runs: secret scanning of the whole
history (gitleaks), static analysis (bandit, CodeQL for Python and GitHub
Actions), known vulnerabilities of the runtime requirements (pip-audit), and
the Home Assistant validations (hassfest, HACS). Dependabot updates the
workflows and the Python requirements; GitHub secret scanning with push
protection is enabled on the repository.

## Pinned tools and dependency audit

The tools that the workflows install (bandit, pip-audit, zizmor, cyclonedx-bom,
Ruff and the other lint tools) come from `requirements_security.txt`,
`requirements_release.txt` and `requirements_ci.txt`: exact versions with
SHA-256 hashes for Linux and CPython 3.14, installed with `pip install
--require-hashes`. They are generated from the matching `.in` files:

```bash
uv pip compile --generate-hashes --python-version 3.14 --python-platform linux requirements_security.in -o requirements_security.txt
```

The lock files are refreshed by regenerating them with the command above (also
the first line of each file), for example when the weekly pip-audit run reports
a finding. Dependabot's pip ecosystem is enabled for the repository, but it is
not relied on for these files: it is not verified that it updates hashed
compiled files consistently, so review any Dependabot pull request that touches
them and regenerate the file with `uv` before merging.

pip-audit runs on every `requirements*.txt` file and on the `requirements` of
`manifest.json` in each CI run and every Monday; a finding fails the check and is
either fixed by upgrading or listed here with the reason. An accepted finding
states the package and version, whether it is shipped or only used by tests or
the build, why it cannot be exploited here or what compensates for it, and an
expiry date (at most one quarter); it is removed or renewed with a new reason at
the quarterly review.

Accepted findings:

* `requirements_test.txt` (test tooling, never shipped): 43 advisories in
  Pillow 12.3.0 (GitHub advisories and PYSEC identifiers, 42 CVEs in pip-audit
  terms), fixed in Pillow 13.0.0. The file resolves to
  `pytest-homeassistant-custom-component` 0.13.375, the latest release of the
  plugin, which pins `homeassistant==2026.10.4`, which pins `Pillow==12.3.0`;
  overriding that pin would loosen the lock, so it is not done. The integration
  does not use Pillow (it declares only `defusedxml`) and tests do not process
  untrusted images. The identifiers are in `.github/pip-audit-ignore-test.txt`
  (applied to that file only) and in `osv-scanner.toml`, which OpenSSF Scorecard
  honours; every entry there expires on 2027-02-28 and both lists go away when
  the pytest plugin moves to Home Assistant 2026.11.

Fixed by upgrading: `requirements_ha.txt` homeassistant 2026.10.2 to 2026.11.1
(Pillow 13.0.0 and uv 0.13.6; 43 advisories).

## Verifying a release

Tags such as `0.15.5b1` or `0.15.5rc1` are published as GitHub pre-releases:
HACS offers them only to users who enable beta versions for this repository.

Every release from 0.15.4 on carries, next to `ha-arpav-meteo-idro.zip`:

* `ha-arpav-meteo-idro.cdx.json`: software bill of materials (OWASP CycloneDX)
  of the runtime requirements;
* `SHA256SUMS`: SHA-256 checksums of the ZIP and of the SBOM;
* a build provenance attestation of the ZIP, signed by GitHub Actions, also
  published as `ha-arpav-meteo-idro.intoto.jsonl` (Sigstore bundle, in-toto
  provenance) so it can be checked offline.

```bash
sha256sum -c SHA256SUMS
gh attestation verify ha-arpav-meteo-idro.zip --repo UMMgl/ha-arpav-meteo-idro
# offline, with the bundle downloaded from the same release
gh attestation verify ha-arpav-meteo-idro.zip --repo UMMgl/ha-arpav-meteo-idro --bundle ha-arpav-meteo-idro.intoto.jsonl
```

Workflows are checked by zizmor; OpenSSF Scorecard results are published in code scanning.

# Security policy

## Supported versions

Only the latest release of ARPAV Meteo e Idro receives fixes.

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/UMMgl/ha-arpav-meteo-idro/security/advisories/new),
not in public issues. Include the version, what you observed and how to
reproduce it. You will get an answer as soon as possible.

## What the integration does

* It only reads public ARPAV open data over HTTPS (no credentials, no personal
  data) and the public METAR service, using the Home Assistant web session.
* XML is parsed with `defusedxml` only (no entity expansion, no external
  resources); documents larger than 5 MB or HTML pages are rejected.
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
either fixed by upgrading or listed here with the reason.

Accepted findings:

* `requirements_test.txt` (test tooling, never shipped): 42 advisories in
  Pillow 12.3.0, fixed in Pillow 13.0.0. The file is unpinned; it resolves to
  `pytest-homeassistant-custom-component` 0.13.375, which pins
  `homeassistant==2026.10.4`, which pins `Pillow==12.3.0`. The integration does
  not use Pillow and tests do not process untrusted images. The identifiers are
  in `.github/pip-audit-ignore-test.txt`, applied to that file only; the list
  goes away when the pytest plugin moves to Home Assistant 2026.11.

Fixed by upgrading: `requirements_ha.txt` homeassistant 2026.10.2 to 2026.11.1
(Pillow 13.0.0 and uv 0.13.6; 43 advisories).

## Verifying a release

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

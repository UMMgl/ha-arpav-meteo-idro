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

## Verifying a release

Every release from 0.15.4 on carries, next to `ha-arpav-meteo-idro.zip`:

* `ha-arpav-meteo-idro.cdx.json`: software bill of materials (OWASP CycloneDX)
  of the runtime requirements;
* `SHA256SUMS`: SHA-256 checksums of the ZIP and of the SBOM;
* a build provenance attestation of the ZIP, signed by GitHub Actions.

```bash
sha256sum -c SHA256SUMS
gh attestation verify ha-arpav-meteo-idro.zip --repo UMMgl/ha-arpav-meteo-idro
```

Workflows are checked by zizmor; OpenSSF Scorecard results are published in code scanning.

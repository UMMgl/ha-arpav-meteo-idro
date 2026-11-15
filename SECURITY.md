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

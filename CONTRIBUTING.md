# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## GitHub is used for everything

GitHub is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. Add or update tests for every change in behaviour (see [Tests](#tests)).
3. If you've changed something users can see, update the documentation (README, `CHANGELOG.md`).
4. Make sure the code lints (`scripts/lint`, i.e. `ruff check .`) and the tests pass.
5. Open the pull request against `main` and describe what you changed and how you tested it.

## Requirements for acceptable contributions

A pull request is merged only when:

- every required check on `main` is green: Ruff, Pytest, the Home Assistant
  validations (hassfest, HACS), secret scanning (gitleaks), bandit and pip-audit,
  CodeQL (Python and GitHub Actions) and zizmor for the workflows;
- the tests cover the change (see [Tests](#tests));
- the Home Assistant quality scale does not regress
  (`python scripts/check_quality_scale.py bronze`; rule status in
  `custom_components/arpav_meteo_idro/quality_scale.yaml`, see
  [docs/quality_scale.md](docs/quality_scale.md));
- new GitHub Actions are pinned to a full commit SHA, and tools installed by the
  workflows come from the hashed requirements files (see [SECURITY.md](SECURITY.md));
- the code follows the style below and the documentation is updated.

`main` is protected: changes reach it only through pull requests.

AI agents must use their dedicated GitHub App identity. They must not approve or
merge pull requests.

## Coding style

The code is checked with [Ruff](https://docs.astral.sh/ruff/) (configuration in
`.ruff.toml`); `scripts/lint` runs it and `scripts/lint-fix` applies the safe fixes.
Follow the Home Assistant
[integration guidelines](https://developers.home-assistant.io/docs/creating_component_index/):
`async` I/O through the Home Assistant session, config entries, translated
user-facing messages. New files start with an `SPDX-License-Identifier` line.

## Tests

**New functionality must come with automated tests, and bug fixes with a test
that fails without the fix.** Pull requests without tests for new behaviour are
not merged.

- Tests live in `tests/` and use pytest; run them with `python -m pytest tests`.
- The ARPAV XML parser (`hydro.py`) is tested without Home Assistant
  (`tests/test_hydro.py`) and fuzzed with Hypothesis (`tests/test_hydro_fuzz.py`).
- The Home Assistant tests use `pytest-homeassistant-custom-component` and run on
  Linux (as in CI); on Windows run the parser tests with
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_hydro.py tests/test_hydro_fuzz.py`.
- Recorded ARPAV documents for the tests are in `tests/fixtures/`; never call the
  live ARPAV services from tests.
- Coverage is measured in CI and raised release by release (see the roadmap).

There is no development container: develop in a local virtual environment
(`python -m venv .venv`, then install `requirements_test.txt`) and let CI run the
full suite on Linux. `requirements_test.txt` is a hash-pinned lock compiled from
`requirements_test.in`; regenerate it with
`uv pip compile --generate-hashes --python-version 3.14.10 --python-platform linux requirements_test.in -o requirements_test.txt`. Add `--upgrade` to refresh the pinned versions (Python 3.14.2+ is required by current Home Assistant).

## Report bugs using GitHub's [issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy!

Security vulnerabilities must not be reported in public issues: follow
[SECURITY.md](SECURITY.md) (GitHub private vulnerability reporting).

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough bug reports. I'm not even kidding.

## License

This project is a fork of
[davidecavestro/arpa-veneto-weather](https://github.com/davidecavestro/arpa-veneto-weather).
The original code remains under the BSD 3-Clause License
([LICENSE-BSD-3-Clause](LICENSE-BSD-3-Clause)); new files and modifications are
under the Apache License 2.0 ([LICENSE](LICENSE)); [NOTICE](NOTICE) lists the
attributions.

By contributing, you agree that your contributions are licensed under the
Apache License 2.0. Changes that are meant to be offered back to the original
project may also be made available under BSD-3-Clause, as that project requires;
say so in the pull request.

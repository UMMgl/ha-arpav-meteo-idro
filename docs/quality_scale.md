# Integration quality scale – self-assessment

The official tiers (Bronze → Platinum) of the
[Home Assistant integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
are assigned to core integrations only; for this HACS integration they are used
as a checklist. They apply to the **whole** integration, including the weather
part inherited from the original project. Rule status per rule:
[`custom_components/arpav_meteo_idro/quality_scale.yaml`](../custom_components/arpav_meteo_idro/quality_scale.yaml).
Open items are listed in [ROADMAP.md](../ROADMAP.md).

## Release gates

Every release (stable and pre-release) passes two gates in the Release workflow
before anything is built or published:

1. **Security gate**: the Security workflow (gitleaks, bandit, pip-audit,
   zizmor, CodeQL) runs on the tagged commit. The `release` job starts only if
   it succeeded. Beta and release candidate tags do not skip it.
2. **Quality gate** (stable tags only): the Tests workflow runs the test suite and
   requires the tier declared in `pyproject.toml` (`release_tier` under
   `[tool.arpav_meteo_idro]`) on the candidate commit. Each tier includes all
   the lower ones. The workflow checks the rule declarations and requires
   measured coverage above 95% in every integration module.

Beta and release candidate tags (e.g. `0.16.0b1`, `0.16.0rc1`) are published as
pre-releases without the quality gate, so they can be tested through HACS before
the stable release.

To preflight a candidate branch, run the Release workflow on that branch. Branch
runs perform verification only. Release assets are published by tag runs.

### Tier plan and ratchet

| Release | Minimum tier |
|---|---|
| 0.16.0 | Silver |
| 0.17.0 | Gold |

The minimum tier is a ratchet: it may rise, never fall. `release_tier` is
validated by `python scripts/check_quality_scale.py --ratchet`, which fails when
it is lower than the highest tier in `[tool.arpav_meteo_idro.released]`, the
list of tiers of the stable releases already published. Both values are
versioned in `pyproject.toml`, so the check needs no network access and runs in
the same Release workflow job that passes the tier to the Tests workflow.

After each stable release, the first pull request adds the entry for that version
(for example `"0.16.0" = "silver"`). Raising `release_tier` to `gold` is part
of the 0.17.0 preparation; lowering it is rejected by the check.

## Bronze (enforced in pull request CI)

`scripts/check_quality_scale.py bronze` runs in the Tests workflow and fails
when a Bronze rule is open; higher tiers are reported.

| Rule | Status | Notes |
|---|---|---|
| action-setup | ✅ | actions registered in `async_setup` |
| appropriate-polling | ✅ | 5 minutes (weather and hydro), METAR at most every 10 minutes |
| brands | ✅ | `custom_components/arpav_meteo_idro/brand/icon.png` |
| common-modules | ✅ | coordinators in `coordinator.py` / `hydro_coordinator.py`, base entities in `entity.py` |
| config-flow | ✅ | menu: weather location / hydrometric stations |
| config-flow-test-coverage | ✅ | weather and hydrometric flows and options, including network errors |
| dependency-transparency | ✅ | defusedxml from PyPI |
| docs-actions, docs-high-level-description, docs-installation-instructions, docs-removal-instructions | ✅ | README |
| entity-event-setup, docs-conditions, docs-triggers | ➖ | not applicable |
| entity-unique-id, has-entity-name | ✅ | |
| runtime-data | ✅ | `ConfigEntry.runtime_data` for both parts |
| test-before-configure, test-before-setup | ✅ | |
| unique-config-entry | ✅ | river (hydro), zone + station (weather) |

## Silver

✅ action-exceptions (translated errors), config-entry-unloading, docs-configuration-parameters,
docs-installation-parameters, entity-unavailable, integration-owner, log-when-unavailable,
parallel-updates. ➖ reauthentication-flow (public open data, no credentials).
⚠️ test-coverage > 95%: the weather modules are not covered yet.

## Gold

✅ devices, diagnostics (config entry diagnostics for both entry types, coordinates and
municipality redacted), docs-data-update, docs-examples (`examples/`),
docs-known-limitations, docs-supported-functions, docs-troubleshooting, docs-use-cases,
entity-category, entity-device-class, entity-disabled-by-default (Observed at and Level
change, new installations only), entity-translations, exception-translations,
icon-translations, stale-devices (devices of deselected stations are removed when the entry
reloads, and can be deleted by hand). ➖ discovery, discovery-update-info,
docs-supported-devices, dynamic-devices.
To do: reconfiguration-flow, repair-issues (e.g. a station that stops publishing).

## Platinum

✅ async-dependency, inject-websession (every request goes through the Home Assistant
shared session, with a 30 s timeout). To do: strict-typing (mypy strict).

## Testing

* Parser tests (`tests/test_hydro.py`) run anywhere: `pytest tests/test_hydro.py`.
* Home Assistant tests (`tests/test_hydro_ha.py`) need a POSIX system (the
  `pytest-homeassistant-custom-component` harness imports `fcntl`/`resource` and
  blocks sockets the Windows event loop needs): they run in GitHub Actions
  (`Tests` workflow) or under WSL/Linux.
* `Validate` workflow: HACS validation and hassfest. `Lint` workflow: ruff.

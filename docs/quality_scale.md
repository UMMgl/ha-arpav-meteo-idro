# Integration quality scale – self-assessment

The official tiers (Bronze → Platinum) of the
[Home Assistant integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
are assigned to core integrations only; for this HACS integration they are used
as a checklist. They apply to the **whole** integration, including the weather
part inherited from the original project. Rule status per rule:
[`custom_components/arpav_meteo_idro/quality_scale.yaml`](../custom_components/arpav_meteo_idro/quality_scale.yaml).
Open items are listed in [ROADMAP.md](../ROADMAP.md).

## Bronze (target)

| Rule | Status | Notes |
|---|---|---|
| action-setup | ✅ | actions registered in `async_setup` |
| appropriate-polling | ✅ | 5 minutes (weather and hydro), METAR at most every 10 minutes |
| brands | ✅ | `custom_components/arpav_meteo_idro/brand/icon.png` |
| common-modules | ⚠️ | coordinators in `coordinator.py` / `hydro_coordinator.py`; no shared `entity.py` yet |
| config-flow | ✅ | menu: weather location / hydrometric stations |
| config-flow-test-coverage | ⚠️ | hydrometric steps tested (including errors); weather steps not yet |
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

✅ devices, docs-data-update, docs-examples (`examples/`), docs-known-limitations,
docs-supported-functions, entity-category, entity-device-class, entity-translations,
icon-translations. ➖ discovery, discovery-update-info, docs-supported-devices, dynamic-devices.
To do: diagnostics, docs-troubleshooting (basics present), docs-use-cases,
entity-disabled-by-default, exception-translations (complete them),
reconfiguration-flow, repair-issues (e.g. a station that stops publishing),
stale-devices (remove the devices of deselected stations).

## Platinum

✅ async-dependency. To do: inject-websession (the weather part still opens its own
aiohttp sessions), strict-typing (mypy strict).

## Testing

* Parser tests (`tests/test_hydro.py`) run anywhere: `pytest tests/test_hydro.py`.
* Home Assistant tests (`tests/test_hydro_ha.py`) need a POSIX system (the
  `pytest-homeassistant-custom-component` harness imports `fcntl`/`resource` and
  blocks sockets the Windows event loop needs): they run in GitHub Actions
  (`Tests` workflow) or under WSL/Linux.
* `Validate` workflow: HACS validation and hassfest. `Lint` workflow: ruff.

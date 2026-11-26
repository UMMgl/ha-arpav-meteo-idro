<!-- SPDX-License-Identifier: Apache-2.0 -->
# Security requirements

The security objectives of the integration, written as numbered requirements
that can be tested. They answer the SAMM level-1 activity *Security
Requirements – Software Requirements* in [evidence.md](evidence.md) and turn the
objectives listed in section 4 of the [risk assessment](risk-assessment.md) into
checkable statements. The principles behind them are in
[design-principles.md](design-principles.md).

How to read it:

* **Met** means the requirement is true on `main` and the *Implemented in* and
  *Verified by* links can be followed. A requirement whose verification is
  weaker than a test says so in its row.
* **Open** means the requirement is not met yet. It is listed so that it is not
  forgotten, and linked to the matching gap (G1 to G10) of the
  [risk assessment](risk-assessment.md#gaps-with-due-dates). An open requirement
  is never counted as evidence.
* The requirements are reviewed with the evidence register, every quarter
  (first review: **2027-02-16**) and whenever a control changes. A link that no
  longer resolves turns the requirement into a gap.

Code links point to the repository at the commit you are reading.

## Input from outside

| Id | Requirement | Implemented in | Verified by | Status |
|---|---|---|---|---|
| SR-1 | Remote XML is parsed only with `defusedxml`; entity declarations are refused and the standard-library parser is never used. | [hydro.py:33](../../custom_components/arpav_meteo_idro/hydro.py#L33), [`_root`](../../custom_components/arpav_meteo_idro/hydro.py#L199) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_entities_are_not_expanded`, arbitrary and mutated bytes, `test_deep_nesting`); bandit in [security.yml](../../.github/workflows/security.yml) flags the unsafe parsers | Met |
| SR-2 | A document larger than 5 MiB is rejected, and so is an HTML page or a document with an unexpected root element, before any value is read from it. | [`MAX_XML_BYTES`](../../custom_components/arpav_meteo_idro/hydro.py#L67), [`_root`](../../custom_components/arpav_meteo_idro/hydro.py#L199) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_oversized_document_is_refused`, `test_html_is_refused`, `test_wrong_root_is_refused`), [test_hydro.py](../../tests/test_hydro.py) (`test_html_and_wrong_root_are_rejected`) | Met (a second barrier behind the streaming limit of SR-3) |
| SR-3 | The size of a response is limited while it is downloaded, for the XML and for the JSON of the weather and METAR parts, not after the whole body is in memory. | [`read_limited`, `read_json_limited`](../../custom_components/arpav_meteo_idro/http_limits.py): the body is read in chunks and the download is aborted over 5 MiB (XML) or 10 MiB (JSON); a `Content-Length` over the limit is refused before reading; `ResponseTooLargeError` is an `aiohttp.ClientError`, handled like any failed request | [test_http_limits.py](../../tests/test_http_limits.py), and one test per request path ([test_weather_entry.py](../../tests/test_weather_entry.py), [test_weather_flow_http.py](../../tests/test_weather_flow_http.py), [test_metar.py](../../tests/test_metar.py), [test_weather_coverage.py](../../tests/test_weather_coverage.py), [test_brightness_statistics.py](../../tests/test_brightness_statistics.py), [test_hydro_ha.py](../../tests/test_hydro_ha.py), [test_silver_ha.py](../../tests/test_silver_ha.py)) | Met – gap **G1** closed on 2026-11-26 ([#83](https://github.com/UMMgl/ha-arpav-meteo-idro/pull/83)), risk R3 in the [risk assessment](risk-assessment.md) |
| SR-4 | A station file name taken from the registry is accepted only as 1 to 6 digits plus `.xml`; otherwise it is derived from a validated numeric station ID. The request URL is always under the fixed ARPAV base. | [`STATION_FILE`](../../custom_components/arpav_meteo_idro/hydro.py#L40), [`station_file`](../../custom_components/arpav_meteo_idro/hydro.py#L47) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_station_file_never_leaves_the_pattern`, `test_station_file_rejects_hostile_links`, `test_station_file_rejects_invalid_ids`), [test_hydro.py](../../tests/test_hydro.py) (`test_station_file_accepts_only_plain_numeric_names`, `test_registry_skips_stations_with_invalid_ids_and_sanitizes_links`) | Met |
| SR-5 | Numbers, instants and station IDs are validated with strict patterns and finite-value checks; a value that fails validation is turned into "no value". Missing data is never turned into zero. | [`parse_number`](../../custom_components/arpav_meteo_idro/hydro.py#L216), [`parse_instant`](../../custom_components/arpav_meteo_idro/hydro.py#L230), [`evaluate`](../../custom_components/arpav_meteo_idro/hydro.py#L406) | [test_hydro_fuzz.py](../../tests/test_hydro_fuzz.py) (`test_parse_number_total`, `test_parse_number_sentinels`, `test_parse_instant_invalid`), [test_hydro.py](../../tests/test_hydro.py) (`test_vicenza_flow_sentinels_are_skipped`, `test_last_sample_invalid_keeps_last_valid_value`, `test_stale_and_missing`) | Met |

## Outbound requests

| Id | Requirement | Implemented in | Verified by | Status |
|---|---|---|---|---|
| SR-6 | Every outbound request has a total timeout of 30 seconds and goes through the shared Home Assistant web session, which the integration never closes. | `REQUEST_TIMEOUT` in [hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py#L35), [coordinator.py](../../custom_components/arpav_meteo_idro/coordinator.py#L33), [metar.py](../../custom_components/arpav_meteo_idro/metar.py#L29), [config_flow.py](../../custom_components/arpav_meteo_idro/config_flow.py#L59), [brightness_statistics.py](../../custom_components/arpav_meteo_idro/brightness_statistics.py#L35) | Timeout and network-error paths: [test_weather_flow_http.py](../../tests/test_weather_flow_http.py), [test_silver_ha.py](../../tests/test_silver_ha.py), [test_metar.py](../../tests/test_metar.py). No test asserts the timeout argument of each call: that part is checked by reading the code (`git grep "ClientSession("` finds nothing in the package) | Met (partly by review) |
| SR-7 | Hydrometric polling is bounded: a fixed polling interval, at most five stations fetched at the same time, and a per-station exponential back-off (up to 30 minutes, with jitter) after repeated failures. | `POLL_INTERVAL`, `MAX_RETRY_DELAY`, `MAX_CONCURRENT_STATIONS` in [hydro_coordinator.py](../../custom_components/arpav_meteo_idro/hydro_coordinator.py#L35), [`_async_update_station`](../../custom_components/arpav_meteo_idro/hydro_coordinator.py#L122) | [test_hydro_ha.py](../../tests/test_hydro_ha.py) (`test_hydro_limits_concurrency_and_keeps_partial_success`, `test_hydro_keeps_last_valid_on_unusable_response`: retry time, back-off and recovery) | Met |
| SR-8 | The weather and METAR coordinators have a concurrency limit and a back-off after failures. | Not implemented: they poll at their own interval without a limit or a back-off | None yet | **Open** – gap **G2**, risk R4 in the [risk assessment](risk-assessment.md) (proposed due 2027-02-28) |
| SR-9 | A failed or unusable response never raises an unhandled error into Home Assistant: the last good observation is kept and flagged, and a station with no usable data is shown as missing or stale, never green. | [`_async_update_station`](../../custom_components/arpav_meteo_idro/hydro_coordinator.py#L122) | [test_hydro_ha.py](../../tests/test_hydro_ha.py) (`test_hydro_keeps_last_valid_on_unusable_response`, `test_old_reading_is_stale`), [test_hydro.py](../../tests/test_hydro.py) (`test_stale_and_missing`) | Met |

## Data and logs

| Id | Requirement | Implemented in | Verified by | Status |
|---|---|---|---|---|
| SR-10 | The integration holds, asks for and logs no credentials and no personal data. | No credential field in the config flows ([config_flow.py](../../custom_components/arpav_meteo_idro/config_flow.py), [hydro_config_flow.py](../../custom_components/arpav_meteo_idro/hydro_config_flow.py)); log messages carry station codes and error text only | gitleaks over the whole history ([security.yml](../../.github/workflows/security.yml), `secrets` job). No automated test of the log content: the `_LOGGER` calls of the package were read for this requirement on 2026-11-21 | Met (partly by review) |
| SR-11 | Diagnostics redact whatever locates the user: coordinates, municipality, nearest weather station, station name and the entry title. | `TO_REDACT` in [diagnostics.py](../../custom_components/arpav_meteo_idro/diagnostics.py#L17) | [test_gold_ha.py](../../tests/test_gold_ha.py) (`test_hydro_diagnostics_are_redacted`, `test_weather_diagnostics_are_redacted`) | Met |
| SR-12 | Recorder statistics are written only for the integration's own level sensors, only for complete past hours, and never over hours the Recorder already holds. | [hydro_statistics.py](../../custom_components/arpav_meteo_idro/hydro_statistics.py#L54) | [test_hydro_statistics.py](../../tests/test_hydro_statistics.py), [test_hydro_ha.py](../../tests/test_hydro_ha.py) (`test_backfill_fills_only_missing_complete_hours`) | Met |
| SR-13 | The 24-hour sample list exposed as a sensor attribute is capped at 288 points and is excluded from the Recorder. | [`MAX_RECENT_SAMPLES`](../../custom_components/arpav_meteo_idro/hydro.py#L78), [`_unrecorded_attributes`](../../custom_components/arpav_meteo_idro/hydro_sensor.py#L113) | [test_hydro.py](../../tests/test_hydro.py) (`test_recent_samples_is_bounded`), [test_hydro_ha.py](../../tests/test_hydro_ha.py) (`test_level_sensor_exposes_unrecorded_samples`) | Met |

## Delivery

| Id | Requirement | Implemented in | Verified by | Status |
|---|---|---|---|---|
| SR-14 | A release is published only after the security gate passes on the tagged commit (gitleaks, bandit, pip-audit, zizmor, CodeQL for Python and Actions), pre-releases included. | [release.yml](../../.github/workflows/release.yml) (`security` job, `needs` of the `release` job), [security.yml](../../.github/workflows/security.yml) (`workflow_call`) | [Release run 44845687536](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/44845687536): the gate jobs passed before *Release* ran. A gate that fails and blocks publication has not been shown yet | Met; the negative proof is open – gap **G6**, risk R9 (proposed due 2027-01-31) |
| SR-15 | Every release carries a build attestation, `SHA256SUMS`, an SBOM and an offline attestation bundle, and the verification steps are published. | [release.yml](../../.github/workflows/release.yml), [SECURITY.md](../../SECURITY.md) ("Verifying a release") | [0.16.0 release assets](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/tag/0.16.0) | Met |
| SR-16 | The only runtime dependency is `defusedxml`; the tools of CI and of the release are installed from lock files with hashes (`--require-hashes`), and every requirements file is audited with pip-audit on every run and weekly. | [manifest.json](../../custom_components/arpav_meteo_idro/manifest.json), [requirements_security.txt](../../requirements_security.txt), [requirements_release.txt](../../requirements_release.txt), [requirements_ci.txt](../../requirements_ci.txt), [requirements_test.txt](../../requirements_test.txt) | [security.yml](../../.github/workflows/security.yml) (pip-audit), [`main` Security run](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671), [0.16.0 SBOM](https://github.com/UMMgl/ha-arpav-meteo-idro/releases/download/0.16.0/ha-arpav-meteo-idro.cdx.json) | Met (dated waivers for the test tooling: gap G5) |
| SR-17 | Workflows run with the least privilege: `permissions:` set per workflow, actions pinned to commit SHAs, no `pull_request_target`, credentials not persisted, zizmor on every change. | [.github/workflows](../../.github/workflows) | zizmor job of the [`main` Security run](https://github.com/UMMgl/ha-arpav-meteo-idro/actions/runs/43775005671) | Met |

## Open requirements

| Id | Gap | Action | Proposed due |
|---|---|---|---|
| SR-8 | G2 | Back-off and concurrency limit for the weather and METAR coordinators | 2027-02-28 |
| SR-14 (negative proof) | G6 | Show that a failing gate blocks publication | 2027-01-31 |

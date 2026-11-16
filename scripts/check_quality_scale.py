# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Fail when a rule of the required quality tier is not done (or exempt with a reason).

Usage: python scripts/check_quality_scale.py [bronze|silver|gold|platinum] --coverage-report coverage.json
       python scripts/check_quality_scale.py --ratchet

--ratchet validates the release tier declared in pyproject.toml
([tool.arpav_meteo_idro] release_tier) and fails when it is lower than the highest
tier recorded for a published stable release ([tool.arpav_meteo_idro.released]).
On success it prints only the declared tier, for the Release workflow to pass to
the Tests workflow. The previous tier is read from the versioned file, so the
check works in CI without network access.

Silver and higher require pytest coverage evidence for every integration module.

The tiers follow https://developers.home-assistant.io/docs/core/integration-quality-scale/rules
and each tier includes the previous ones. The report lists the open rules of
every tier, so the next tier stays visible.
"""

import argparse
import json
import pathlib
import sys
import tomllib

TIERS = {
    "bronze": [
        "action-setup", "appropriate-polling", "brands", "common-modules", "config-flow",
        "config-flow-test-coverage", "dependency-transparency", "docs-actions", "docs-conditions",
        "docs-high-level-description", "docs-installation-instructions", "docs-removal-instructions",
        "docs-triggers", "entity-event-setup", "entity-unique-id", "has-entity-name", "runtime-data",
        "test-before-configure", "test-before-setup", "unique-config-entry",
    ],
    "silver": [
        "action-exceptions", "config-entry-unloading", "docs-configuration-parameters",
        "docs-installation-parameters", "entity-unavailable", "integration-owner", "log-when-unavailable",
        "parallel-updates", "reauthentication-flow", "test-coverage",
    ],
    "gold": [
        "devices", "diagnostics", "discovery", "discovery-update-info", "docs-data-update", "docs-examples",
        "docs-known-limitations", "docs-supported-devices", "docs-supported-functions", "docs-troubleshooting",
        "docs-use-cases", "dynamic-devices", "entity-category", "entity-device-class",
        "entity-disabled-by-default", "entity-translations", "exception-translations", "icon-translations",
        "reconfiguration-flow", "repair-issues", "stale-devices",
    ],
    "platinum": ["async-dependency", "inject-websession", "strict-typing"],
}
PYPROJECT = pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"
FILE = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "arpav_meteo_idro" / "quality_scale.yaml"


def status(rule_value) -> tuple[str, str | None]:
    """Return (status, comment) of a rule entry."""
    if isinstance(rule_value, dict):
        return rule_value.get("status", "todo"), rule_value.get("comment")
    return rule_value or "todo", None


def coverage_passes(report: pathlib.Path) -> bool:
    """Require coverage above 95% for every integration module with statements."""
    try:
        coverage_files = json.loads(report.read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError) as error:
        sys.stdout.write(f"Cannot read integration coverage: {error}" + "\n")
        return False

    root = FILE.parents[2]
    measured = {pathlib.Path(name).resolve(): stats["summary"] for name, stats in coverage_files.items()}
    passed = True
    for source in sorted(FILE.parent.rglob("*.py")):
        name = source.relative_to(root)
        summary = measured.get(source)
        if summary is None:
            sys.stdout.write(f"Coverage missing: {name}" + "\n")
            passed = False
        elif summary["num_statements"] and summary["covered_lines"] * 100 <= summary["num_statements"] * 95:
            sys.stdout.write(f"Coverage must exceed 95%: {name} ({summary['percent_covered']:.2f}%)" + "\n")
            passed = False
    return passed


def check_ratchet(pyproject: pathlib.Path) -> tuple[str | None, list[str]]:
    """Return the declared release tier and the list of problems with it."""
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, [f"Cannot read {pyproject.name}: {error}"]
    section = data.get("tool", {}).get("arpav_meteo_idro", {})
    declared = section.get("release_tier")
    if declared not in TIERS:
        return None, [f"release_tier must be one of {', '.join(TIERS)}, found {declared!r}"]
    errors = []
    released = section.get("released", {})
    for version, tier in released.items():
        if tier not in TIERS:
            errors.append(f"released tier of {version} must be one of {', '.join(TIERS)}, found {tier!r}")
    if not errors and released:
        version, floor = max(released.items(), key=lambda item: list(TIERS).index(item[1]))
        if list(TIERS).index(declared) < list(TIERS).index(floor):
            errors.append(f"release_tier {declared} is lower than {floor}, already released in {version}: "
                          "the tier may only rise")
    return declared, errors


def main() -> int:
    """Check the tier given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tier", nargs="?", default="bronze", choices=tuple(TIERS))
    parser.add_argument("--coverage-report", type=pathlib.Path)
    parser.add_argument("--ratchet", action="store_true", help="validate and print the declared release tier")
    args = parser.parse_args()
    if args.ratchet:
        declared, errors = check_ratchet(PYPROJECT)
        for error in errors:
            sys.stderr.write(f"{error}\n")
        if errors:
            return 1
        sys.stdout.write(f"{declared}\n")
        return 0
    import yaml  # noqa: PLC0415 - only the rule check needs PyYAML; --ratchet runs on a bare interpreter

    target = args.tier
    rules = yaml.safe_load(FILE.read_text(encoding="utf-8"))["rules"]
    failed = False
    for tier, names in TIERS.items():
        missing = [n for n in names if n not in rules]
        open_rules = [n for n in names if n in rules and status(rules[n])[0] not in {"done", "exempt"}]
        unexplained = [n for n in names if n in rules and status(rules[n])[0] == "exempt" and not status(rules[n])[1]]
        done = len(names) - len(missing) - len(open_rules) - len(unexplained)
        sys.stdout.write(f"{tier:9} {done}/{len(names)} done or exempt"
                         + (f" | open: {', '.join(open_rules)}" if open_rules else "")
                         + (f" | missing from the file: {', '.join(missing)}" if missing else "")
                         + (f" | exempt without a reason: {', '.join(unexplained)}" if unexplained else "") + "\n")
        required = list(TIERS).index(tier) <= list(TIERS).index(target)
        if required and (open_rules or missing or unexplained):
            failed = True
    if target != "bronze":
        if args.coverage_report is None:
            sys.stdout.write("Provide --coverage-report for Silver, Gold or Platinum." + "\n")
            failed = True
        elif not coverage_passes(args.coverage_report):
            failed = True
    sys.stdout.write(f"required tier: {target} -> {'FAILED' if failed else 'OK'}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

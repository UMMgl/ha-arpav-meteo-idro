# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Fail when a rule of the required quality tier is not done (or exempt with a reason).

Usage: python scripts/check_quality_scale.py [bronze|silver|gold|platinum] --coverage-report coverage.json

Silver and higher require pytest coverage evidence for every integration module.

The tiers follow https://developers.home-assistant.io/docs/core/integration-quality-scale/rules
and each tier includes the previous ones. The report lists the open rules of
every tier, so the next tier stays visible.
"""

import argparse
import json
import pathlib
import sys

import yaml

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


def main() -> int:
    """Check the tier given on the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tier", nargs="?", default="bronze", choices=tuple(TIERS))
    parser.add_argument("--coverage-report", type=pathlib.Path)
    args = parser.parse_args()
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

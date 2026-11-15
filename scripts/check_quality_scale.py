# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Fail when a rule of the required quality tier is not done (or exempt with a reason).

Usage: python scripts/check_quality_scale.py [bronze|silver|gold|platinum]

The tiers follow https://developers.home-assistant.io/docs/core/integration-quality-scale/rules
and each tier includes the previous ones. The report lists the open rules of
every tier, so the next tier stays visible.
"""

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


def main() -> int:
    """Check the tier given on the command line."""
    target = sys.argv[1] if len(sys.argv) > 1 else "bronze"
    rules = yaml.safe_load(FILE.read_text(encoding="utf-8"))["rules"]
    failed = False
    for tier, names in TIERS.items():
        missing = [n for n in names if n not in rules]
        open_rules = [n for n in names if n in rules and status(rules[n])[0] == "todo"]
        unexplained = [n for n in names if n in rules and status(rules[n])[0] == "exempt" and not status(rules[n])[1]]
        done = len(names) - len(missing) - len(open_rules)
        sys.stdout.write(f"{tier:9} {done}/{len(names)} done or exempt"
                         + (f" | open: {', '.join(open_rules)}" if open_rules else "")
                         + (f" | missing from the file: {', '.join(missing)}" if missing else "")
                         + (f" | exempt without a reason: {', '.join(unexplained)}" if unexplained else "") + "\n")
        required = list(TIERS).index(tier) <= list(TIERS).index(target)
        if required and (open_rules or missing or unexplained):
            failed = True
    sys.stdout.write(f"required tier: {target} -> {'FAILED' if failed else 'OK'}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

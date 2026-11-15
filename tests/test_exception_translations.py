# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Gianluca Nardin (@UMMgl)
"""Static checks of the exception translations (run anywhere, no Home Assistant needed)."""

import json
import pathlib
import re

COMPONENT = pathlib.Path(__file__).parent.parent / "custom_components" / "arpav_meteo_idro"
# translation_domain=DOMAIN, translation_key="..." only appears in exceptions
KEY = re.compile(r"translation_domain=DOMAIN,\s*translation_key=\"([a-z_]+)\"")
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def _used_keys() -> set[str]:
    keys: set[str] = set()
    for path in COMPONENT.glob("*.py"):
        keys.update(KEY.findall(path.read_text(encoding="utf-8")))
    return keys


def test_every_exception_key_is_translated():
    """Each translation_key raised by the code has an en and an it message."""
    used = _used_keys()
    assert {"fetch_failed", "no_station_readable", "entry_not_loaded"} <= used
    for lang in ("en", "it"):
        exceptions = json.loads((COMPONENT / "translations" / f"{lang}.json").read_text(encoding="utf-8"))["exceptions"]
        assert used <= set(exceptions), (lang, used - set(exceptions))


def test_exception_messages_use_the_same_placeholders():
    """The Italian text has the placeholders of the English one."""
    texts = {
        lang: json.loads((COMPONENT / "translations" / f"{lang}.json").read_text(encoding="utf-8"))["exceptions"]
        for lang in ("en", "it")
    }
    for key, entry in texts["en"].items():
        assert set(PLACEHOLDER.findall(entry["message"])) == set(PLACEHOLDER.findall(texts["it"][key]["message"])), key


def test_no_untranslated_user_facing_exception():
    """UpdateFailed and the Home Assistant exceptions always carry a translation key."""
    for path in COMPONENT.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"raise (UpdateFailed|HomeAssistantError|ServiceValidationError|ConfigEntryNotReady)\(", source):
            window = source[match.end():match.end() + 300]
            assert "translation_key" in window, f"{path.name}: {match.group(1)} without translation_key"

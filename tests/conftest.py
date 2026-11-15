# SPDX-License-Identifier: Apache-2.0
"""Fixtures for the tests that need Home Assistant."""

import pytest

try:
    import fcntl  # noqa: F401  Home Assistant's test harness needs a POSIX system
    import pytest_homeassistant_custom_component  # noqa: F401
    HAS_HA = True
except ImportError:  # the parser tests run without Home Assistant (e.g. on Windows)
    HAS_HA = False

if HAS_HA:
    pytest_plugins = ["pytest_homeassistant_custom_component"]

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations):
        """Enable the custom integration in every test."""
        yield

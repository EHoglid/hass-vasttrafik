"""Pytest configuration for pure and Home Assistant integration tests."""

import sys

if sys.platform != "win32":
    pytest_plugins = ["pytest_homeassistant_custom_component"]

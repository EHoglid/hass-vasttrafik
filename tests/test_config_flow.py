"""Tests for the Västtrafik config flow."""

import asyncio

from custom_components.vasttrafik_timetable.config_flow import (
    VasttrafikTimetableConfigFlow,
)
from custom_components.vasttrafik_timetable.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
)


def _run_async(coroutine):
    """Run a coroutine without leaving pytest without a current loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_search_step_ignores_stale_credential_payload() -> None:
    """Show the search form if Home Assistant resubmits credential fields."""
    flow = VasttrafikTimetableConfigFlow()

    result = _run_async(
        flow.async_step_search(
            {
                CONF_CLIENT_ID: "valid-client-id",
                CONF_CLIENT_SECRET: "valid-client-secret",
            }
        )
    )

    assert result["type"] == "form"
    assert result["step_id"] == "search"
    assert result["errors"] == {}

"""Diagnostics support for Västtrafik Timetable."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import VasttrafikConfigEntry
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

TO_REDACT = {CONF_CLIENT_ID, CONF_CLIENT_SECRET}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VasttrafikConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "last_exception": repr(coordinator.last_exception)
        if coordinator.last_exception
        else None,
        "departures": [
            {
                "line": departure.line,
                "direction": departure.direction,
                "planned_time": departure.planned_time.isoformat(),
                "estimated_time": departure.estimated_time.isoformat(),
                "platform": departure.platform,
                "cancelled": departure.cancelled,
                "transport_mode": departure.transport_mode,
                "is_wheelchair_accessible": departure.is_wheelchair_accessible,
            }
            for departure in (coordinator.data or [])
        ],
    }

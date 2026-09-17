"""The Västtrafik Timetable integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VasttrafikClient
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, PLATFORMS
from .coordinator import VasttrafikCoordinator

type VasttrafikConfigEntry = ConfigEntry[VasttrafikCoordinator]


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Register the built-in Västtrafik timetable dashboard card."""
    if hass.data.get("vasttrafik_timetable_frontend_registered"):
        return

    card_path = "/vasttrafik_timetable/vasttrafik-timetable-card.js"
    card_url = f"{card_path}?v=4"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                card_path,
                Path(__file__).parent / "www" / "vasttrafik-timetable-card.js",
                cache_headers=False,
            )
        ]
    )
    add_extra_js_url(hass, card_url)
    hass.data["vasttrafik_timetable_frontend_registered"] = True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up global Västtrafik Timetable resources."""
    await _async_register_frontend_card(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> bool:
    """Set up Västtrafik Timetable from a config entry."""
    await _async_register_frontend_card(hass)
    client = VasttrafikClient(
        async_get_clientsession(hass),
        entry.data[CONF_CLIENT_ID],
        entry.data[CONF_CLIENT_SECRET],
    )
    coordinator = VasttrafikCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VasttrafikConfigEntry) -> bool:
    """Unload a Västtrafik Timetable config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

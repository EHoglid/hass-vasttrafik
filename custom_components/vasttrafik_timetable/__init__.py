"""The Västtrafik Timetable integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VasttrafikClient
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, PLATFORMS
from .coordinator import VasttrafikCoordinator

_LOGGER = logging.getLogger(__name__)

type VasttrafikConfigEntry = ConfigEntry[VasttrafikCoordinator]


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Register the built-in Västtrafik timetable dashboard card."""
    if hass.data.get("vasttrafik_timetable_frontend_registered"):
        return

    card_path = "/vasttrafik_timetable/vasttrafik-timetable-card.js"
    card_file = Path(__file__).parent / "www" / "vasttrafik-timetable-card.js"
    # Bust the browser cache only when the file actually changes, while still
    # allowing it to be cached (cache_headers=False forced an uncached refetch
    # on every load, which raced with Lovelace and caused intermittent
    # "Custom element doesn't exist" errors).
    cache_bust = int(card_file.stat().st_mtime)
    card_url = f"{card_path}?v={cache_bust}"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                card_path,
                str(card_file),
                cache_headers=True,
            )
        ]
    )
    add_extra_js_url(hass, card_url)
    hass.data["vasttrafik_timetable_frontend_registered"] = True
    _LOGGER.debug("Registered dashboard card resource at %s", card_url)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up global Västtrafik Timetable resources."""
    await _async_register_frontend_card(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: VasttrafikConfigEntry
) -> bool:
    """Set up Västtrafik Timetable from a config entry."""
    _LOGGER.debug("Setting up config entry %s", entry.entry_id)
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


async def async_unload_entry(
    hass: HomeAssistant, entry: VasttrafikConfigEntry
) -> bool:
    """Unload a Västtrafik Timetable config entry."""
    _LOGGER.debug("Unloading config entry %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

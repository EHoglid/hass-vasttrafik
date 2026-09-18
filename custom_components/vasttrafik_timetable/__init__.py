"""The Västtrafik Timetable integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import resources as lovelace_resources
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import VasttrafikClient
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, PLATFORMS
from .coordinator import VasttrafikCoordinator

_LOGGER = logging.getLogger(__name__)

type VasttrafikConfigEntry = ConfigEntry[VasttrafikCoordinator]

CARD_PATH = "/vasttrafik_timetable/vasttrafik-timetable-card.js"
DATA_FRONTEND_URL = "vasttrafik_timetable_frontend_url"
DATA_STATIC_PATH_REGISTERED = "vasttrafik_timetable_static_path_registered"
DATA_LOVELACE_RESOURCE_URL = "vasttrafik_timetable_lovelace_resource_url"


async def _async_register_lovelace_resource(
    hass: HomeAssistant, card_url: str
) -> bool:
    """Register the card as a Lovelace module resource."""
    if hass.data.get(DATA_LOVELACE_RESOURCE_URL) == card_url:
        return True

    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.debug("Lovelace is not loaded; skipping card resource setup")
        return False

    if lovelace_data.resource_mode != MODE_STORAGE:
        _LOGGER.warning(
            "Add %s as a Lovelace module resource because resources are in %s "
            "mode",
            card_url,
            lovelace_data.resource_mode,
        )
        return False

    if not isinstance(
        lovelace_data.resources, lovelace_resources.ResourceStorageCollection
    ):
        _LOGGER.warning("Unable to register Lovelace resource automatically")
        return False

    resources = cast(
        lovelace_resources.ResourceStorageCollection, lovelace_data.resources
    )
    await resources.async_get_info()
    items = list(resources.async_items())
    matching_items = [
        item
        for item in items
        if str(item.get(CONF_URL, "")).startswith(CARD_PATH)
    ]
    current_item = next(
        (item for item in matching_items if item.get(CONF_URL) == card_url),
        None,
    )

    kept_item = current_item
    if kept_item is None:
        if matching_items:
            kept_item = await resources.async_update_item(
                matching_items[0]["id"],
                {"res_type": "module", CONF_URL: card_url},
            )
        else:
            kept_item = await resources.async_create_item(
                {"res_type": "module", CONF_URL: card_url}
            )

    for old_item in matching_items:
        if old_item["id"] == kept_item["id"]:
            continue
        await resources.async_delete_item(old_item["id"])

    hass.data[DATA_LOVELACE_RESOURCE_URL] = card_url
    return True


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Register the built-in Västtrafik timetable dashboard card."""
    card_file = Path(__file__).parent / "www" / "vasttrafik-timetable-card.js"
    # Bust the browser cache only when the file actually changes, while still
    # allowing it to be cached (cache_headers=False forced an uncached refetch
    # on every load, which raced with Lovelace and caused intermittent
    # "Custom element doesn't exist" errors).
    cache_bust = int(card_file.stat().st_mtime)
    card_url = f"{CARD_PATH}?v={cache_bust}"
    if not hass.data.get(DATA_STATIC_PATH_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    CARD_PATH,
                    str(card_file),
                    cache_headers=True,
                )
            ]
        )
        hass.data[DATA_STATIC_PATH_REGISTERED] = True

    if hass.data.get(DATA_FRONTEND_URL) != card_url:
        add_extra_js_url(hass, card_url)
        hass.data[DATA_FRONTEND_URL] = card_url

    await _async_register_lovelace_resource(hass, card_url)
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

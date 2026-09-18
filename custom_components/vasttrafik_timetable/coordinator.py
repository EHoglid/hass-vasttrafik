"""Data coordinator for Västtrafik departures."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    Departure,
    VasttrafikApiError,
    VasttrafikAuthenticationError,
    VasttrafikClient,
)
from .const import CONF_STOP_GID, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class VasttrafikCoordinator(DataUpdateCoordinator[list[Departure]]):
    """Poll one Västtrafik stop area."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry[VasttrafikCoordinator],
        client: VasttrafikClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Västtrafik {entry.data[CONF_STOP_GID]}",
            update_interval=UPDATE_INTERVAL,
        )
        self._entry = entry
        self._client = client
        self._stop_gid = entry.data[CONF_STOP_GID]

    async def _async_update_data(self) -> list[Departure]:
        try:
            departures = await self._client.async_get_departures_with_options(
                self._stop_gid, dict(self._entry.data)
            )
        except VasttrafikAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Västtrafik credentials were rejected"
            ) from err
        except VasttrafikApiError as err:
            raise UpdateFailed(
                f"Error communicating with Västtrafik: {err}"
            ) from err

        sorted_departures = sorted(
            departures, key=lambda item: item.estimated_time
        )
        return sorted_departures

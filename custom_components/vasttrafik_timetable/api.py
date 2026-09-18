"""Async client for the Västtrafik Journey Planner v4 API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

TOKEN_URL = "https://ext-api.vasttrafik.se/token"
API_BASE_URL = "https://ext-api.vasttrafik.se/pr/v4"
MAX_DEPARTURE_PAGES = 100


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    """Convert a stored option to an integer within API limits."""
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


class VasttrafikApiError(Exception):
    """Base exception for Västtrafik API errors."""


class VasttrafikAuthenticationError(VasttrafikApiError):
    """Raised when Västtrafik rejects the credentials."""


@dataclass(frozen=True, slots=True)
class StopArea:
    """A Västtrafik stop area."""

    gid: str
    name: str


@dataclass(frozen=True, slots=True)
class Departure:
    """A normalized departure from a stop area."""

    line: str
    line_name: str
    line_background_color: str | None
    line_foreground_color: str | None
    line_border_color: str | None
    direction: str
    planned_time: datetime
    estimated_time: datetime
    platform: str | None
    cancelled: bool
    transport_mode: str | None

    @property
    def delay_minutes(self) -> int:
        """Return the delay compared with the planned time."""
        difference = self.estimated_time - self.planned_time
        return round(difference.total_seconds() / 60)


def _parse_datetime(value: str) -> datetime:
    """Parse an RFC 3339 timestamp."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_departures(payload: dict[str, Any]) -> list[Departure]:
    """Normalize a Journey Planner departures response."""
    departures: list[Departure] = []
    for item in payload.get("results", []):
        planned = item.get("plannedTime")
        if not planned:
            continue

        journey = item.get("serviceJourney") or {}
        line = journey.get("line") or {}
        stop_point = item.get("stopPoint") or {}
        platform = stop_point.get("platform") or {}
        estimated = item.get("estimatedTime") or planned

        try:
            planned_time = _parse_datetime(planned)
            estimated_time = _parse_datetime(estimated)
        except ValueError:
            continue

        departures.append(
            Departure(
                line=str(line.get("designation") or line.get("name") or "?"),
                line_name=str(line.get("name") or ""),
                line_background_color=line.get("backgroundColor"),
                line_foreground_color=line.get("foregroundColor"),
                line_border_color=line.get("borderColor"),
                direction=str(journey.get("direction") or ""),
                planned_time=planned_time,
                estimated_time=estimated_time,
                platform=(
                    str(platform.get("name"))
                    if isinstance(platform, dict) and platform.get("name")
                    else (
                        str(platform)
                        if isinstance(platform, str) and platform
                        else None
                    )
                ),
                cancelled=bool(item.get("isCancelled", False)),
                transport_mode=line.get("transportMode"),
            )
        )

    return departures


class VasttrafikClient:
    """Client for authentication, stop search, and departure boards."""

    def __init__(
        self, session: ClientSession, client_id: str, client_secret: str
    ) -> None:
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._expires_at = 0.0

    async def async_authenticate(self) -> None:
        """Fetch and cache an access token."""
        try:
            async with self._session.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            ) as response:
                if response.status in (400, 401, 403):
                    _LOGGER.warning(
                        "Västtrafik rejected the API credentials (HTTP %s)",
                        response.status,
                    )
                    raise VasttrafikAuthenticationError(
                        "Invalid API credentials"
                    )
                response.raise_for_status()
                data = await response.json()
        except VasttrafikAuthenticationError:
            raise
        except (ClientError, TimeoutError) as err:
            _LOGGER.error(
                "Could not connect to Västtrafik token endpoint: %s", err
            )
            raise VasttrafikApiError(
                "Could not connect to Västtrafik"
            ) from err

        token = data.get("access_token")
        if not token:
            _LOGGER.error(
                "Västtrafik token response contained no access_token"
            )
            raise VasttrafikAuthenticationError(
                "Token response contained no token"
            )
        self._access_token = token
        lifetime = int(data.get("expires_in", 3600))
        self._expires_at = time.monotonic() + lifetime - 300
        _LOGGER.debug(
            "Authenticated with Västtrafik, token valid for %ss", lifetime
        )

    async def _async_headers(self) -> dict[str, str]:
        if self._access_token is None or time.monotonic() >= self._expires_at:
            await self.async_authenticate()
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _async_get(
        self, path: str, params: dict[str, str | int | bool]
    ) -> dict[str, Any]:
        try:
            async with self._session.get(
                f"{API_BASE_URL}{path}",
                headers=await self._async_headers(),
                params=params,
            ) as response:
                if response.status == 401:
                    self._access_token = None
                    _LOGGER.warning(
                        "Västtrafik access token was rejected on %s", path
                    )
                    raise VasttrafikAuthenticationError(
                        "Access token was rejected"
                    )
                response.raise_for_status()
                return await response.json()
        except VasttrafikAuthenticationError:
            raise
        except (ClientError, TimeoutError) as err:
            _LOGGER.error(
                "Could not fetch Västtrafik data from %s: %s", path, err
            )
            raise VasttrafikApiError(
                "Could not fetch Västtrafik data"
            ) from err

    async def async_search_stops(self, query: str) -> list[StopArea]:
        """Search for stop areas by name."""
        query = query.strip()
        if not query:
            return []
        payload = await self._async_get(
            "/locations/by-text",
            {"q": query, "types": "stoparea", "limit": 10},
        )
        return [
            StopArea(gid=item["gid"], name=item["name"])
            for item in payload.get("results", [])
            if item.get("locationType") == "stoparea"
            and item.get("gid")
            and item.get("name")
        ]

    async def async_get_departures(self, stop_gid: str) -> list[Departure]:
        """Return all upcoming departures from a stop area."""
        return await self.async_get_departures_with_options(stop_gid, {})

    async def async_get_departures_with_options(
        self, stop_gid: str, options: dict[str, Any]
    ) -> list[Departure]:
        """Return all upcoming departures using configured API options."""
        departures: list[Departure] = []
        offset = 0
        page_count = 0

        while True:
            page_count += 1
            if page_count > MAX_DEPARTURE_PAGES:
                raise VasttrafikApiError(
                    "Västtrafik returned too many departure pages"
                )

            params: dict[str, str | int | bool] = {
                "timeSpanInMinutes": _bounded_int(
                    options.get("time_span_in_minutes"), 60, 0, 1440
                ),
                "maxDeparturesPerLineAndDirection": _bounded_int(
                    options.get("max_departures_per_line_and_direction"),
                    2,
                    1,
                    20,
                ),
                "limit": _bounded_int(options.get("api_limit"), 10, 1, 100),
                "offset": offset,
            }
            query_keys = {
                "start_date_time": "startDateTime",
                "platforms": "platforms",
                "direction_gid": "directionGid",
            }
            for option_key, query_key in query_keys.items():
                if options.get(option_key):
                    params[query_key] = str(options[option_key])
            if options.get("include_occupancy"):
                params["includeOccupancy"] = True

            payload = await self._async_get(
                f"/stop-areas/{stop_gid}/departures",
                params,
            )
            page = payload.get("results", [])
            departures.extend(parse_departures(payload))

            links = payload.get("links") or {}
            if not page or not links.get("next"):
                break
            next_offset = offset + len(page)
            if next_offset <= offset:
                raise VasttrafikApiError(
                    "Västtrafik returned invalid departure pagination"
                )
            offset = next_offset

        return departures

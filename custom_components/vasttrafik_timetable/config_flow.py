"""Config flow for Västtrafik Journey Planner."""

from __future__ import annotations

from datetime import datetime
from typing import Any, override

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    StopArea,
    VasttrafikApiError,
    VasttrafikAuthenticationError,
    VasttrafikClient,
)
from .const import (
    CONF_API_LIMIT,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DIRECTION_GID,
    CONF_INCLUDE_OCCUPANCY,
    CONF_MAX_DEPARTURES_PER_LINE,
    CONF_PLATFORMS,
    CONF_START_DATE_TIME,
    CONF_STOP_GID,
    CONF_STOP_NAME,
    CONF_TIME_SPAN,
    DEFAULT_API_LIMIT,
    DEFAULT_MAX_DEPARTURES_PER_LINE,
    DEFAULT_TIME_SPAN,
    DOMAIN,
)


def _query_options_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the form schema for departure query options."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_START_DATE_TIME,
                default=defaults.get(CONF_START_DATE_TIME, ""),
            ): str,
            vol.Optional(
                CONF_PLATFORMS, default=defaults.get(CONF_PLATFORMS, "")
            ): str,
            vol.Required(
                CONF_TIME_SPAN,
                default=defaults.get(CONF_TIME_SPAN, DEFAULT_TIME_SPAN),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1440)),
            vol.Required(
                CONF_MAX_DEPARTURES_PER_LINE,
                default=defaults.get(
                    CONF_MAX_DEPARTURES_PER_LINE,
                    DEFAULT_MAX_DEPARTURES_PER_LINE,
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
            vol.Required(
                CONF_API_LIMIT,
                default=defaults.get(CONF_API_LIMIT, DEFAULT_API_LIMIT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional(
                CONF_INCLUDE_OCCUPANCY,
                default=defaults.get(CONF_INCLUDE_OCCUPANCY, False),
            ): bool,
            vol.Optional(
                CONF_DIRECTION_GID,
                default=defaults.get(CONF_DIRECTION_GID, ""),
            ): str,
        }
    )


def _validate_query_options(
    user_input: dict[str, Any], errors: dict[str, str]
) -> None:
    """Validate departure query options in-place."""
    try:
        user_input[CONF_START_DATE_TIME] = (
            VasttrafikTimetableConfigFlow._validate_datetime(
                user_input[CONF_START_DATE_TIME]
            )
        )
    except vol.Invalid:
        errors[CONF_START_DATE_TIME] = "invalid_datetime"
    try:
        user_input[CONF_DIRECTION_GID] = (
            VasttrafikTimetableConfigFlow._validate_stop_gid(
                user_input[CONF_DIRECTION_GID]
            )
        )
    except vol.Invalid:
        errors[CONF_DIRECTION_GID] = "invalid_stop_gid"


class VasttrafikTimetableConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Västtrafik Journey Planner config flow."""

    VERSION = 1

    @staticmethod
    @override
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return VasttrafikTimetableOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}
        self._stops: dict[str, StopArea] = {}
        self._selected_stop: StopArea | None = None
        self._api: VasttrafikClient | None = None

    def _client(self) -> VasttrafikClient:
        if self._api is None:
            self._api = VasttrafikClient(
                async_get_clientsession(self.hass),
                self._credentials[CONF_CLIENT_ID],
                self._credentials[CONF_CLIENT_SECRET],
            )
        return self._api

    @staticmethod
    def _validate_query(value: str) -> str:
        """Reject empty or whitespace-only stop searches."""
        value = value.strip()
        if not value:
            raise vol.Invalid("Stop name is required")
        return value

    @staticmethod
    def _validate_datetime(value: str) -> str:
        """Validate an optional RFC 3339 date-time value."""
        if not value:
            return value
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as err:
            raise vol.Invalid("Expected an RFC 3339 date-time") from err
        return value

    @staticmethod
    def _validate_stop_gid(value: str) -> str:
        """Validate an optional 16-digit stop-area GID."""
        if value and (len(value) != 16 or not value.isdigit()):
            raise vol.Invalid("Expected a 16-digit stop-area GID")
        return value

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate Västtrafik API credentials."""
        errors: dict[str, str] = {}
        if user_input is None and not self._credentials:
            existing_entries = self.hass.config_entries.async_entries(DOMAIN)
            if existing_entries:
                existing_data = existing_entries[0].data
                client_id = existing_data.get(CONF_CLIENT_ID)
                client_secret = existing_data.get(CONF_CLIENT_SECRET)
                if client_id and client_secret:
                    self._credentials = {
                        CONF_CLIENT_ID: str(client_id),
                        CONF_CLIENT_SECRET: str(client_secret),
                    }
                self._api = None
                if self._credentials:
                    try:
                        await self._client().async_authenticate()
                    except (VasttrafikAuthenticationError, VasttrafikApiError):
                        self._credentials = {}
                    else:
                        return await self.async_step_search()

        if user_input is not None:
            self._credentials = {
                CONF_CLIENT_ID: user_input[CONF_CLIENT_ID].strip(),
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET].strip(),
            }
            self._api = None
            try:
                await self._client().async_authenticate()
            except VasttrafikAuthenticationError:
                errors["base"] = "invalid_auth"
            except VasttrafikApiError:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_search()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for a stop area."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                query = self._validate_query(user_input.get("query", ""))
            except vol.Invalid:
                query = ""

            if not query and "query" in user_input:
                errors["query"] = "required"
            elif query:
                try:
                    stops = await self._client().async_search_stops(query)
                except VasttrafikAuthenticationError:
                    return await self.async_step_user()
                except VasttrafikApiError:
                    errors["base"] = "cannot_connect"
                else:
                    if stops:
                        self._stops = {stop.gid: stop for stop in stops}
                        return await self.async_step_select()
                    errors["base"] = "no_stops"

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema(
                {vol.Optional("query"): str}, extra=vol.ALLOW_EXTRA
            ),
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a stop from the search results."""
        if user_input is not None:
            stop = self._stops[user_input[CONF_STOP_GID]]
            self._selected_stop = stop
            await self.async_set_unique_id(stop.gid)
            self._abort_if_unique_id_configured()
            return await self.async_step_options()

        return await self._show_stop_selection()

    async def _show_stop_selection(self) -> ConfigFlowResult:
        """Show the current stop search results."""
        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_GID): vol.In(
                        {gid: stop.name for gid, stop in self._stops.items()}
                    )
                }
            ),
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the departure query for this stop."""
        if self._selected_stop is None:
            return await self.async_step_search()
        errors: dict[str, str] = {}
        if user_input is not None:
            _validate_query_options(user_input, errors)
            if not errors:
                return self.async_create_entry(
                    title=self._selected_stop.name,
                    data={
                        **self._credentials,
                        CONF_STOP_GID: self._selected_stop.gid,
                        CONF_STOP_NAME: self._selected_stop.name,
                        **user_input,
                    },
                )

        return self.async_show_form(
            step_id="options",
            data_schema=_query_options_schema({}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate replacement credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._credentials = {
                CONF_CLIENT_ID: user_input[CONF_CLIENT_ID].strip(),
                CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET].strip(),
            }
            self._api = None
            try:
                await self._client().async_authenticate()
            except VasttrafikAuthenticationError:
                errors["base"] = "invalid_auth"
            except VasttrafikApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=self._credentials,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
        )


class VasttrafikTimetableOptionsFlow(config_entries.OptionsFlow):
    """Handle editable Västtrafik query options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage departure query options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _validate_query_options(user_input, errors)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        defaults = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_query_options_schema(defaults),
            errors=errors,
        )

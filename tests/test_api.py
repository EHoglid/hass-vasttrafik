"""Tests for Västtrafik API response normalization."""

import asyncio
import importlib.util
import sys
from pathlib import Path

API_PATH = (
    Path(__file__).parents[1] / "custom_components" / "vasttrafik_timetable" / "api.py"
)
SPEC = importlib.util.spec_from_file_location("vasttrafik_api", API_PATH)
assert SPEC is not None and SPEC.loader is not None
API = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = API
SPEC.loader.exec_module(API)


def _run_async(coroutine):
    """Run a coroutine without leaving pytest without a current loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def test_parse_departures() -> None:
    """Parse the documented Journey Planner v4 departure shape."""
    departures = API.parse_departures(
        {
            "results": [
                {
                    "serviceJourney": {
                        "line": {
                            "name": "Spårvagn 6",
                            "designation": "6",
                            "backgroundColor": "#00f0da",
                            "foregroundColor": "#00435c",
                            "borderColor": "#00435c",
                            "transportMode": "tram",
                        },
                        "direction": "Kortedala",
                    },
                    "plannedTime": "2026-09-16T14:00:00+02:00",
                    "estimatedTime": "2026-09-16T14:03:00+02:00",
                    "stopPoint": {"platform": {"name": "B"}},
                    "isCancelled": False,
                }
            ]
        }
    )

    assert len(departures) == 1
    assert departures[0].line == "6"
    assert departures[0].line_name == "Spårvagn 6"
    assert departures[0].line_background_color == "#00f0da"
    assert departures[0].line_foreground_color == "#00435c"
    assert departures[0].line_border_color == "#00435c"
    assert departures[0].direction == "Kortedala"
    assert departures[0].platform == "B"
    assert departures[0].transport_mode == "tram"
    assert departures[0].delay_minutes == 3


def test_parse_departures_skips_invalid_timestamps() -> None:
    """Ignore malformed API records without losing valid departures."""
    departures = API.parse_departures(
        {
            "results": [
                {"plannedTime": "not-a-timestamp"},
                {
                    "serviceJourney": {
                        "line": {"designation": "10"},
                        "direction": "Guldheden",
                    },
                    "plannedTime": "2026-09-16T14:00:00+02:00",
                },
            ]
        }
    )

    assert len(departures) == 1
    assert departures[0].line == "10"


def test_get_departures_follows_pagination() -> None:
    """Fetch every page returned for the one-hour departure window."""

    async def run_test() -> tuple[int, list[int]]:
        client = API.VasttrafikClient(None, "", "")
        calls: list[int] = []

        async def fake_get(path: str, params: dict[str, str | int | bool]) -> dict:
            calls.append(int(params["offset"]))
            departure = {
                "serviceJourney": {
                    "line": {"designation": "10", "transportMode": "tram"},
                    "direction": "Guldheden",
                },
                "plannedTime": "2026-09-16T14:00:00+02:00",
                "estimatedTime": "2026-09-16T14:00:00+02:00",
                "stopPoint": {"platform": "A"},
            }
            return {
                "results": [departure],
                "links": {"next": "stop-areas/example/departures?offset=1"}
                if len(calls) == 1
                else {},
            }

        client._async_get = fake_get
        departures = await client.async_get_departures("example")
        return len(departures), calls

    departure_count, calls = _run_async(run_test())

    assert departure_count == 2
    assert calls == [0, 1]


def test_get_departures_passes_configured_options() -> None:
    """Translate stored config values into the documented API parameters."""

    async def run_test() -> dict[str, str | int | bool]:
        client = API.VasttrafikClient(None, "", "")
        captured: dict[str, str | int | bool] = {}

        async def fake_get(path: str, params: dict[str, str | int | bool]) -> dict:
            captured.update(params)
            return {"results": []}

        client._async_get = fake_get
        await client.async_get_departures_with_options(
            "example",
            {
                "start_date_time": "2026-09-17T12:00:00+02:00",
                "platforms": "A,C",
                "time_span_in_minutes": 90,
                "max_departures_per_line_and_direction": 3,
                "api_limit": 25,
                "include_occupancy": True,
                "direction_gid": "9021014004490000",
            },
        )
        return captured

    params = _run_async(run_test())

    assert params == {
        "timeSpanInMinutes": 90,
        "maxDeparturesPerLineAndDirection": 3,
        "limit": 25,
        "offset": 0,
        "startDateTime": "2026-09-17T12:00:00+02:00",
        "platforms": "A,C",
        "directionGid": "9021014004490000",
        "includeOccupancy": True,
    }

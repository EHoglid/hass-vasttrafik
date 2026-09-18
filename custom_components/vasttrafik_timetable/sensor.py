"""Sensor platform for Västtrafik Timetable."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import VasttrafikConfigEntry
from .api import Departure
from .const import CONF_STOP_GID, CONF_STOP_NAME, DOMAIN
from .coordinator import VasttrafikCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VasttrafikConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Västtrafik sensors."""
    async_add_entities(
        [
            VasttrafikNextDepartureSensor(entry),
            VasttrafikMinutesSensor(entry),
        ]
    )


def _departure_attributes(departure: Departure) -> dict[str, Any]:
    return {
        "line": departure.line,
        "line_name": departure.line_name,
        "line_background_color": departure.line_background_color,
        "line_foreground_color": departure.line_foreground_color,
        "line_border_color": departure.line_border_color,
        "direction": departure.direction,
        "planned_time": departure.planned_time.isoformat(),
        "estimated_time": departure.estimated_time.isoformat(),
        "platform": departure.platform,
        "delay_minutes": departure.delay_minutes,
        "cancelled": departure.cancelled,
        "transport_mode": departure.transport_mode,
        "is_wheelchair_accessible": departure.is_wheelchair_accessible,
    }


class VasttrafikSensorBase(
    CoordinatorEntity[VasttrafikCoordinator], SensorEntity
):
    """Base class for Västtrafik sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: VasttrafikConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(entry.runtime_data)
        self.entity_description = description
        stop_gid = entry.data[CONF_STOP_GID]
        self._attr_unique_id = f"{stop_gid}_{description.key}"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, stop_gid)},
            name=entry.data[CONF_STOP_NAME],
            manufacturer="Västtrafik",
            model="Departure board",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def next_departure(self) -> Departure | None:
        return self.coordinator.data[0] if self.coordinator.data else None


class VasttrafikNextDepartureSensor(VasttrafikSensorBase):
    """Timestamp and timetable for upcoming departures."""

    def __init__(self, entry: VasttrafikConfigEntry) -> None:
        super().__init__(
            entry,
            SensorEntityDescription(
                key="next_departure",
                translation_key="next_departure",
                device_class=SensorDeviceClass.TIMESTAMP,
                icon="mdi:bus-clock",
            ),
        )

    @property
    def native_value(self):
        departure = self.next_departure
        return departure.estimated_time if departure else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "departures": [
                _departure_attributes(departure)
                for departure in self.coordinator.data
            ]
        }


class VasttrafikMinutesSensor(VasttrafikSensorBase):
    """Minutes until the next departure."""

    def __init__(self, entry: VasttrafikConfigEntry) -> None:
        super().__init__(
            entry,
            SensorEntityDescription(
                key="minutes_until_departure",
                translation_key="minutes_until_departure",
                native_unit_of_measurement=UnitOfTime.MINUTES,
                icon="mdi:timer-outline",
            ),
        )

    @property
    def native_value(self) -> int | None:
        departure = self.next_departure
        if departure is None:
            return None
        now = dt_util.now().astimezone(departure.estimated_time.tzinfo)
        seconds = (departure.estimated_time - now).total_seconds()
        return max(0, int(seconds // 60))

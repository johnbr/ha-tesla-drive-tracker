"""Sensors for a car's drive."""
from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import DriveConfigEntry
from .engine import (
    STATE_ARRIVING,
    STATE_CHARGING,
    STATE_DRIVING,
    STATE_NAVIGATING,
    STATE_OFFLINE,
    STATE_PARKED,
)
from .entity import DriveEntity
from .sources import ROLE_ARRIVAL_BATTERY, ROLE_TRAFFIC_DELAY
from .view import DriveView

PARALLEL_UPDATES = 0


def _eta(view: DriveView) -> datetime | None:
    if view.arrival_at is None:
        return None
    return dt_util.utc_from_timestamp(view.arrival_at)


@dataclass(frozen=True, kw_only=True)
class DriveSensorDescription(SensorEntityDescription):
    """A sensor and the view field it shows."""

    value_fn: Callable[[DriveView], Any]
    needs_role: str | None = None


SENSORS: tuple[DriveSensorDescription, ...] = (
    DriveSensorDescription(
        key="drive_state",
        translation_key="drive_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            STATE_PARKED,
            STATE_DRIVING,
            STATE_NAVIGATING,
            STATE_ARRIVING,
            STATE_CHARGING,
            STATE_OFFLINE,
        ],
        value_fn=lambda view: view.state,
    ),
    DriveSensorDescription(
        key="destination",
        translation_key="destination",
        value_fn=lambda view: view.destination,
    ),
    DriveSensorDescription(
        key="eta",
        translation_key="eta",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_eta,
    ),
    DriveSensorDescription(
        key="time_remaining",
        translation_key="time_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda view: view.minutes,
    ),
    DriveSensorDescription(
        key="distance_remaining",
        translation_key="distance_remaining",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILES,
        suggested_display_precision=1,
        value_fn=lambda view: view.distance,
    ),
    DriveSensorDescription(
        key="arrival_battery",
        translation_key="arrival_battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        needs_role=ROLE_ARRIVAL_BATTERY,
        value_fn=lambda view: view.arrival_battery,
    ),
    DriveSensorDescription(
        key="traffic_delay",
        translation_key="traffic_delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        needs_role=ROLE_TRAFFIC_DELAY,
        value_fn=lambda view: view.traffic_delay,
    ),
    DriveSensorDescription(
        key="trip_distance",
        translation_key="trip_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILES,
        suggested_display_precision=1,
        value_fn=lambda view: view.trip_distance,
    ),
    DriveSensorDescription(
        key="trip_duration",
        translation_key="trip_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda view: view.trip_duration,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DriveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors whose sources this car has."""
    coordinator = entry.runtime_data
    async_add_entities(
        DriveSensor(coordinator, description)
        for description in SENSORS
        if description.needs_role is None
        or description.needs_role in coordinator.sources
    )


class DriveSensor(DriveEntity, SensorEntity):
    """One published figure."""

    entity_description: DriveSensorDescription

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "destination":
            return None
        return {"status": self.coordinator.data.destination_status}

    def _showing(self) -> Hashable:
        attributes = self.extra_state_attributes
        return (self.native_value, attributes and attributes["status"])

"""Binary sensors for a car's drive."""
from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DriveConfigEntry
from .entity import DriveEntity
from .view import DriveView

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class DriveBinarySensorDescription(BinarySensorEntityDescription):
    """A binary sensor and the view field it shows."""

    value_fn: Callable[[DriveView], bool | None]


BINARY_SENSORS: tuple[DriveBinarySensorDescription, ...] = (
    DriveBinarySensorDescription(
        key="driving",
        translation_key="driving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=lambda view: view.driving,
    ),
    DriveBinarySensorDescription(
        key="heading_home",
        translation_key="heading_home",
        value_fn=lambda view: view.heading_home,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DriveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the binary sensors."""
    async_add_entities(
        DriveBinarySensor(entry.runtime_data, description)
        for description in BINARY_SENSORS
    )


class DriveBinarySensor(DriveEntity, BinarySensorEntity):
    """One published yes or no."""

    entity_description: DriveBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)

    def _showing(self) -> Hashable:
        return self.is_on

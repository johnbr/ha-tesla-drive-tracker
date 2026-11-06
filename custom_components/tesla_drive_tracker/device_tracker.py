"""The destination, on a map only when its coordinates are paired with its name."""
from __future__ import annotations

from collections.abc import Hashable

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DriveConfigEntry
from .entity import DriveEntity

PARALLEL_UPDATES = 0

DESTINATION = EntityDescription(key="destination_position", translation_key="destination")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DriveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the destination tracker."""
    async_add_entities([DestinationTracker(entry.runtime_data, DESTINATION)])


class DestinationTracker(DriveEntity, TrackerEntity):
    """Unavailable rather than wrong: no pin beats a wrong pin."""

    _attr_source_type = SourceType.GPS

    @property
    def available(self) -> bool:
        return super().available and self.latitude is not None

    @property
    def latitude(self) -> float | None:
        return self.coordinator.data.destination_latitude

    @property
    def longitude(self) -> float | None:
        return self.coordinator.data.destination_longitude

    def _showing(self) -> Hashable:
        return (self.latitude, self.longitude)

"""Hide the destination."""
from __future__ import annotations

from collections.abc import Hashable
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DriveConfigEntry
from .entity import DriveEntity

PARALLEL_UPDATES = 0

HIDE_DESTINATION = EntityDescription(
    key="hide_destination",
    translation_key="hide_destination",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DriveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the switch."""
    async_add_entities([HideDestinationSwitch(entry.runtime_data, HIDE_DESTINATION)])


class HideDestinationSwitch(DriveEntity, SwitchEntity):
    """Kept by the coordinator, which must know before any entity exists."""

    @property
    def is_on(self) -> bool:
        return self.coordinator.hidden

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_hidden(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_hidden(False)

    def _showing(self) -> Hashable:
        return self.is_on

"""Base entity for a car's drive."""
from __future__ import annotations

from collections.abc import Hashable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DriveCoordinator


class DriveEntity(CoordinatorEntity[DriveCoordinator]):
    """An entity that writes only when what it shows has changed.

    The coordinator publishes on every fix, about once a second on a drive, and
    these entities change a few times a minute at most.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: DriveCoordinator, description: EntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.vin}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.vin)},
            name=coordinator.config_entry.title,
            manufacturer="Tesla",
        )
        self._shown: Hashable = None

    def _showing(self) -> Hashable:
        """What this entity shows, to compare against the last write."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        showing = self._showing()
        if showing != self._shown:
            self._shown = showing
            self.async_write_ha_state()

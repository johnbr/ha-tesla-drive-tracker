"""Diagnostics, with everything that identifies the car or says where it goes."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_VIN
from .coordinator import DriveConfigEntry

TO_REDACT = {
    CONF_VIN,
    "destination",
    "destination_latitude",
    "destination_longitude",
    "latitude",
    "longitude",
    "route",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DriveConfigEntry
) -> dict[str, Any]:
    """What the integration found and what it makes of the car."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "sources": {
            role: [entity_id for entity_id, _ in candidates]
            for role, candidates in coordinator.sources.items()
        },
        "trail_points": len(coordinator.trail.points),
        "view": async_redact_data(coordinator.data.as_wire(), TO_REDACT),
    }

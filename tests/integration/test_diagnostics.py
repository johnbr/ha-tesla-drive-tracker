"""Diagnostics keep the car and where it goes out."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.tesla_drive_tracker.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import VIN, Car


async def test_nothing_identifying_gets_out(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await car.report("speed", "40")
    await car.report("destination", "Cafe", {"latitude": 10.25, "longitude": 20.75})
    await car.report("position", "not_home", {"latitude": 11.25, "longitude": 21.75})
    result = str(await async_get_config_entry_diagnostics(hass, car.entry))
    for secret in (VIN, "Cafe", "10.25", "20.75", "11.25", "21.75"):
        assert secret not in result
    assert "driving" in result
    await car.stop()

"""A car made of the entities a source integration would register."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.tesla_drive_tracker import DATA_STARTED_AT
from custom_components.tesla_drive_tracker.const import CONF_VIN, DOMAIN
from custom_components.tesla_drive_tracker.engine import DriveEvent

VIN = "5YJSA1E40AA000000"  # invented
FIXTURES = Path(__file__).parents[1] / "fixtures"
START = "2026-01-15T20:00:00+00:00"
TICK = 15

TELEMETRY_ENTITIES = {
    "position": ("device_tracker", "_location_telemetry"),
    "destination": ("device_tracker", "_route_telemetry"),
    "speed": ("sensor", "_vehicle_speed_telemetry"),
    "gear": ("sensor", "_gear_telemetry"),
    "arrival": ("sensor", "_time_to_arrival_telemetry"),
    "distance": ("sensor", "_miles_to_arrival_telemetry"),
    "battery": ("sensor", "_battery_level_telemetry"),
    "odometer": ("sensor", "_odometer_telemetry"),
    "charging": ("sensor", "_charging_state_telemetry"),
    "occupancy": ("binary_sensor", "_user_present_telemetry"),
    "route_line": ("sensor", "_signal_RouteLine"),
    "arrival_battery": ("sensor", "_signal_ExpectedEnergyPercentAtTripArrival"),
}


def invented_position(name: str) -> dict[str, float]:
    """A made-up place for each destination, far from any real one."""
    index = sum(ord(letter) for letter in name)
    return {"latitude": 10 + index / 1000, "longitude": 20 + index / 1000}


@dataclass
class Car:
    """Reports values the way the source entities would, on a frozen clock."""

    hass: HomeAssistant
    freezer: FrozenDateTimeFactory
    entry: MockConfigEntry
    entity_ids: dict[str, str]
    events: list[DriveEvent] = field(default_factory=list)
    clock: float = 0

    @property
    def coordinator(self):
        return self.entry.runtime_data

    @property
    def types(self) -> list[str]:
        return [event.type for event in self.events]

    async def start(self) -> None:
        """Load the integration and listen to its events."""
        await self.hass.config_entries.async_setup(self.entry.entry_id)
        await self.hass.async_block_till_done()
        self.listen()

    def listen(self) -> None:
        self.coordinator.async_add_event_listener(self.events.append)

    async def reload(self) -> None:
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        await self.hass.async_block_till_done()
        self.listen()

    async def restart(self) -> None:
        """What a restart does: everything reported so far becomes restored."""
        await self.stop()
        self.freezer.tick(timedelta(seconds=30))
        self.clock += 30
        self.hass.data[DATA_STARTED_AT] = dt_util.utcnow().timestamp()
        await self.hass.config_entries.async_setup(self.entry.entry_id)
        await self.hass.async_block_till_done()
        self.listen()

    async def stop(self) -> None:
        await self.hass.config_entries.async_unload(self.entry.entry_id)
        await self.hass.async_block_till_done()

    async def report(
        self, role: str, value: Any, attributes: dict[str, Any] | None = None
    ) -> None:
        self.hass.states.async_set(self.entity_ids[role], value, attributes or {})
        await self.hass.async_block_till_done()

    async def wait(self, seconds: float) -> None:
        """Let time pass, ticking the way the coordinator's interval would."""
        target = self.clock + seconds
        while self.clock < target:
            step = min(TICK, target - self.clock)
            self.freezer.tick(timedelta(seconds=step))
            self.clock += step
            await self.coordinator.async_refresh()
            await self.hass.async_block_till_done()

    async def wait_without_integration(self, seconds: float) -> None:
        self.freezer.tick(timedelta(seconds=seconds))
        self.clock += seconds

    async def replay(
        self,
        name: str,
        *,
        watch=None,
        until: float | None = None,
        start_at: float = 0,
    ) -> None:
        """Play a recorded window, calling ``watch`` after each step."""
        fixture = json.loads((FIXTURES / f"{name}.json").read_text())
        base = self.clock - start_at
        for offset, role, value in fixture["rows"]:
            if offset < start_at:
                continue
            if until is not None and offset > until:
                return
            await self.wait(base + offset - self.clock)
            if role == "arrival":
                value = (
                    "unknown"
                    if value is None
                    else dt_util.utc_from_timestamp(
                        dt_util.parse_datetime(START).timestamp() + base + value
                    ).isoformat()
                )
            if role == "destination" and value.startswith("Place"):
                await self.report(role, value, invented_position(value))
            else:
                await self.report(role, value)
            if watch is not None:
                watch()
        if until is None:
            await self.wait(base + fixture["duration"] - self.clock)
            if watch is not None:
                watch()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration under test."""


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    config = MockConfigEntry(
        domain=DOMAIN, unique_id=VIN, title="Test Car", data={CONF_VIN: VIN}
    )
    config.add_to_hass(hass)
    return config


@pytest.fixture
def source_entry(hass: HomeAssistant) -> MockConfigEntry:
    config = MockConfigEntry(domain="tesla_telemetry")
    config.add_to_hass(hass)
    return config


@pytest.fixture
def car(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    source_entry: MockConfigEntry,
) -> Car:
    """A car with every telemetry source, at a fixed moment."""
    freezer.move_to(START)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source_entry.entry_id,
        identifiers={("tesla_telemetry", VIN)},
        name="Test Car",
    )
    registry = er.async_get(hass)
    entity_ids = {
        role: registry.async_get_or_create(
            domain, "tesla_telemetry", f"{VIN}{suffix}", device_id=device.id
        ).entity_id
        for role, (domain, suffix) in TELEMETRY_ENTITIES.items()
    }
    return Car(hass, freezer, entry, entity_ids)

"""Loading, unloading and following the registry."""
from __future__ import annotations

from typing import Any

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.tesla_drive_tracker.const import CONF_ROLES, DOMAIN

from .conftest import VIN, Car


async def test_a_trail_is_kept_during_a_trip(car: Car) -> None:
    await car.start()
    await car.report("speed", "40")
    for step in range(3):
        await car.report(
            "position", "not_home", {"latitude": 10 + step / 100, "longitude": 20.0}
        )
    assert len(car.coordinator.trail.points) == 3
    await car.stop()


async def test_a_new_trip_starts_a_new_trail(car: Car) -> None:
    await car.start()
    await car.report("speed", "40")
    await car.report("position", "not_home", {"latitude": 10.0, "longitude": 20.0})
    await car.report("speed", "0")
    await car.report("gear", "P")
    await car.wait(200)
    assert car.types == ["drive_started", "drive_ended"]
    await car.report("position", "not_home", {"latitude": 11.0, "longitude": 21.0})
    await car.report("speed", "40")
    assert car.coordinator.trail.points == [(11.0, 21.0)]
    await car.stop()


async def test_a_parked_car_keeps_its_place_after_a_restart(car: Car) -> None:
    await car.report("position", "home", {"latitude": 10.0, "longitude": 20.0})
    await car.wait_without_integration(5)
    await car.start()
    assert car.coordinator.data.latitude == 10.0
    await car.stop()


async def test_the_interval_ends_a_trip_nothing_reports_on(
    car: Car, hass: HomeAssistant, freezer
) -> None:
    await car.start()
    await car.report("speed", "40")
    await car.report("speed", "0")
    await car.report("gear", "P")
    for _ in range(14):
        freezer.tick(15)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert car.types == ["drive_started", "drive_ended"]
    await car.stop()


async def test_no_sources_raises_a_repair(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"no_sources_{entry.entry_id}")
    assert issue is not None
    assert issue.translation_key == "no_sources"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_a_found_source_clears_the_repair(
    car: Car, hass: HomeAssistant
) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"no_sources_{car.entry.entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="no_sources",
    )
    await car.start()
    issues = ir.async_get(hass).issues
    assert (DOMAIN, f"no_sources_{car.entry.entry_id}") not in issues
    await car.stop()


async def test_an_added_signal_is_picked_up(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    assert hass.states.get("sensor.test_car_traffic_delay") is None
    er.async_get(hass).async_get_or_create(
        "sensor",
        "tesla_telemetry",
        f"{VIN}_signal_RouteTrafficMinutesDelay",
    )
    await car.wait(10)
    await hass.async_block_till_done()
    await car.coordinator._resolver.async_call()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_car_traffic_delay") is not None
    await car.stop()


async def test_an_override_replaces_the_found_source(
    car: Car, hass: HomeAssistant
) -> None:
    hass.config_entries.async_update_entry(
        car.entry, options={CONF_ROLES: {"arrival": "sensor.waze"}}
    )
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await car.report("speed", "40")
    await car.report("destination", "Cafe", {"latitude": 1.0, "longitude": 2.0})
    hass.states.async_set("sensor.waze", "21")
    await car.wait(1)
    assert car.coordinator.data.minutes == 21
    await car.stop()


async def test_removal_deletes_the_trail(
    car: Car, hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    await car.start()
    await car.report("speed", "40")
    await car.stop()
    key = f"{DOMAIN}.{car.entry.entry_id}"
    assert key in hass_storage
    await hass.config_entries.async_remove(car.entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_unload(car: Car) -> None:
    await car.start()
    assert car.entry.state is ConfigEntryState.LOADED
    await car.stop()
    assert car.entry.state is ConfigEntryState.NOT_LOADED

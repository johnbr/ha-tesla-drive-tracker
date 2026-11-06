"""Entities, redaction and the destination's position."""
from __future__ import annotations

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import METRIC_SYSTEM

from custom_components.tesla_drive_tracker.const import DOMAIN

from .conftest import VIN, Car

PLACE = {"latitude": 10.0, "longitude": 20.0}
DESTINATION = "sensor.test_car_destination"
PIN = "device_tracker.test_car_destination"
HIDE = "switch.test_car_hide_destination"


async def driving_to(car: Car, name: str = "Cafe", position=PLACE) -> None:
    await car.report("speed", "40")
    await car.report("destination", name, position)


async def test_entities_exist_and_say_parked(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    assert hass.states.get("sensor.test_car_drive_state").state == "parked"
    assert hass.states.get("binary_sensor.test_car_driving").state == "off"
    assert hass.states.get(PIN).state == STATE_UNAVAILABLE
    await car.stop()


async def test_optional_sensors_need_a_source(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    assert hass.states.get("sensor.test_car_arrival_battery") is not None
    assert hass.states.get("sensor.test_car_traffic_delay") is None
    await car.stop()


async def test_a_new_install_shows_the_destination(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    assert hass.states.get(HIDE).state == "off"
    await driving_to(car)
    assert hass.states.get(DESTINATION).state == "Cafe"
    await car.stop()


async def test_a_damaged_saved_state_fails_hidden(
    car: Car, hass: HomeAssistant, hass_storage
) -> None:
    hass_storage[f"{DOMAIN}.{car.entry.entry_id}"] = {
        "version": 1,
        "key": f"{DOMAIN}.{car.entry.entry_id}",
        "data": {"hide": "maybe"},
    }
    await car.start()
    assert hass.states.get(HIDE).state == "on"
    await car.stop()


async def test_hidden_publishes_no_destination(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(True)
    await driving_to(car)
    assert hass.states.get(DESTINATION).state == STATE_UNKNOWN
    assert hass.states.get(DESTINATION).attributes["status"] == "hidden"
    assert hass.states.get(PIN).state == STATE_UNAVAILABLE
    await car.stop()


async def test_the_switch_shows_and_hides(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": HIDE}, blocking=True
    )
    await driving_to(car)
    await car.report("arrival", "12")
    assert hass.states.get(DESTINATION).state == "Cafe"
    assert hass.states.get(PIN).attributes["latitude"] == 10.0

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": HIDE}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(DESTINATION).state == STATE_UNKNOWN
    assert hass.states.get(PIN).state == STATE_UNAVAILABLE
    assert hass.states.get("binary_sensor.test_car_heading_home").state == STATE_UNKNOWN
    assert hass.states.get("sensor.test_car_time_remaining").state == "12"
    await car.stop()


async def test_the_hide_switch_survives_a_restart(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await car.reload()
    assert hass.states.get(HIDE).state == "off"
    await car.stop()


async def test_events_are_redacted_while_hidden(car: Car) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(True)
    await car.report("speed", "40")
    await car.report("destination", "Cafe", PLACE)
    await car.wait(125)
    await car.report("speed", "41")
    event = car.events[-1]
    assert event.type == "destination_set"
    assert "destination" not in event.data
    assert "home" not in event.data
    await car.stop()


async def test_a_name_gets_only_its_own_coordinates(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await car.report("destination", "not_home", PLACE)
    await car.wait(30)
    await driving_to(car, "Cafe", {"latitude": 11.0, "longitude": 21.0})
    await car.wait(30)
    # The next stop's location signal never comes: the tracker still holds Cafe's.
    await car.report("destination", "Bakery", {"latitude": 11.0, "longitude": 21.0})
    assert hass.states.get(DESTINATION).state == "Bakery"
    assert hass.states.get(DESTINATION).attributes["status"] == "unpaired"
    assert hass.states.get(PIN).state == STATE_UNAVAILABLE
    await car.stop()


async def test_a_lowercase_zone_verdict_is_not_a_destination(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await driving_to(car, "home")
    assert hass.states.get(DESTINATION).state == STATE_UNKNOWN
    await car.stop()


async def test_a_destination_named_home_uses_the_home_zone(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    hass.states.async_set(
        "zone.home",
        "0",
        {"latitude": 1.5, "longitude": 2.5, "radius": 100, "passive": False},
    )
    await driving_to(car, "Home", {})
    assert hass.states.get(PIN).attributes["latitude"] == 1.5
    assert hass.states.get(PIN).attributes["longitude"] == 2.5
    await car.stop()


async def test_arrival_figures_end_with_the_route(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await driving_to(car)
    await car.report("arrival_battery", "71")
    assert hass.states.get("sensor.test_car_arrival_battery").state == "71.0"
    await car.report("destination", "not_home", PLACE)
    assert hass.states.get("sensor.test_car_arrival_battery").state == STATE_UNKNOWN
    await car.stop()


async def test_a_metric_source_is_read_in_its_own_units(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    await car.report("speed", "12", {"unit_of_measurement": "km/h"})
    assert car.events == []
    await car.report("speed", "20", {"unit_of_measurement": "km/h"})
    assert car.types == ["drive_started"]
    await car.stop()


async def test_distance_follows_the_owners_units(
    car: Car, hass: HomeAssistant
) -> None:
    hass.config.units = METRIC_SYSTEM
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await driving_to(car)
    await car.report("distance", "10", {"unit_of_measurement": "mi"})
    state = hass.states.get("sensor.test_car_distance_remaining")
    assert state.attributes["unit_of_measurement"] == "km"
    assert float(state.state) == 16.09344
    await car.stop()


async def test_a_quiet_entity_is_not_rewritten(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    await car.report("speed", "40")
    before = hass.states.get("sensor.test_car_drive_state").last_reported
    car.freezer.tick(1)
    await car.report("speed", "41")
    assert hass.states.get("sensor.test_car_drive_state").last_reported == before
    await car.stop()


async def test_entities_belong_to_one_device(car: Car, hass: HomeAssistant) -> None:
    await car.start()
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, car.entry.entry_id)
    assert len({entry.device_id for entry in entries}) == 1
    assert all(entry.unique_id.startswith(VIN) for entry in entries)
    await car.stop()

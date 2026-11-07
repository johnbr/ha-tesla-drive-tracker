"""Every trip engine rule, through the whole integration.

Most of these replay real windows of a real car, scrubbed: no coordinates, no
real names or dates. The rest build the moment by hand because the recorder no
longer holds it, or because the bug would need a drive that went wrong.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import VIN, Car


async def replay(car: Car, name: str) -> list[tuple[float, str]]:
    """Play a fixture, returning when each event happened."""
    await car.start()
    await car.coordinator.async_set_hidden(False)
    timeline: list[tuple[float, str]] = []

    def watch() -> None:
        while len(timeline) < len(car.events):
            timeline.append((car.clock, car.events[len(timeline)].type))

    await car.replay(name, watch=watch)
    await car.stop()
    return timeline


async def test_speed_proves_driving_when_occupancy_says_nobody_is_there(
    car: Car,
) -> None:
    await replay(car, "false_occupancy")
    assert car.types.count("drive_started") == 1
    assert car.types.count("drive_ended") == 1


async def test_a_gear_stuck_at_p_does_not_end_a_drive(car: Car) -> None:
    await replay(car, "stuck_gear")
    assert car.types.count("drive_started") == 1
    assert car.types.count("drive_ended") == 1


async def test_parking_ends_the_trip_when_the_car_goes_quiet(car: Car) -> None:
    timeline = await replay(car, "home_arrival")
    assert [kind for _, kind in timeline] == [
        "drive_started",
        "destination_set",
        "heading_home",
        "arriving",
        "drive_ended",
    ]


async def test_arrival_fires_once_per_trip_on_a_stable_route(car: Car) -> None:
    await replay(car, "home_arrival")
    arriving = [event for event in car.events if event.type == "arriving"]
    assert len(arriving) == 1
    assert arriving[0].data["threshold"] == 5
    assert arriving[0].data["home"] is True


async def test_a_replayed_route_fires_no_arrival(car: Car) -> None:
    """Routes were replaced and replayed through this drive."""
    timeline = await replay(car, "stale_route_replay")
    changes = [
        at
        for at, kind in timeline
        if kind.startswith("destination_") and kind != "destination_cleared"
    ]
    arrivals = [at for at, kind in timeline if kind == "arriving"]
    assert len(changes) >= 6
    # The one arrival in over 90 minutes of replays, and nothing lands on a change.
    assert len(arrivals) == 1
    assert all(at not in changes for at in arrivals)


async def test_a_parked_car_setting_nav_home_is_not_a_trip(
    car: Car, hass: HomeAssistant
) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    seen: list[str | None] = []
    await car.replay(
        "phantom_nav",
        watch=lambda: seen.append(hass.states.get(
            "sensor.test_car_destination"
        ).state),
    )
    assert car.events == []
    assert set(seen) == {"unknown"}
    assert hass.states.get("binary_sensor.test_car_heading_home").state == "off"
    await car.stop()


async def test_a_dead_zone_pauses_the_trip(car: Car) -> None:
    await replay(car, "stream_drop")
    assert car.types.count("drive_started") == 1
    assert car.types.count("drive_ended") == 1


async def test_a_stream_that_dies_at_speed_drops_the_trip_silently(car: Car) -> None:
    await car.start()
    await car.report("gear", "D")
    await car.report("speed", "60")
    assert car.types == ["drive_started"]
    await car.wait(120 + 1800 + 30)
    assert car.coordinator.data.trip_started_at is None
    assert car.coordinator.data.driving is False
    assert car.types == ["drive_started"]
    await car.stop()


async def test_a_short_silence_keeps_the_trip(car: Car) -> None:
    await car.start()
    await car.report("speed", "60")
    await car.wait(300)
    assert car.coordinator.data.driving is True
    await car.report("speed", "55")
    assert car.coordinator.data.driving is True
    assert car.types == ["drive_started"]
    await car.stop()


async def test_a_stale_charging_state_cannot_veto_a_moving_car(car: Car) -> None:
    await car.start()
    await car.report("charging", "charging")
    await car.report("speed", "40")
    assert car.types == ["drive_started"]
    await car.stop()


async def test_a_restart_mid_drive_does_not_start_it_again(car: Car) -> None:
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await car.replay("home_arrival", until=300)
    assert car.types == ["drive_started"]
    await car.restart()
    await car.replay("home_arrival", start_at=300)
    assert car.types.count("drive_started") == 1
    assert car.types.count("drive_ended") == 1
    await car.stop()


async def test_a_drive_that_ended_across_a_restart_stays_silent(car: Car) -> None:
    await car.start()
    await car.report("speed", "40")
    await car.restart()
    await car.report("speed", "0")
    await car.report("gear", "P")
    await car.wait(240)
    assert car.types == ["drive_started"]
    assert car.coordinator.data.trip_started_at is None
    await car.stop()


async def test_restored_values_never_count(car: Car) -> None:
    await car.report("speed", "60")
    await car.report("gear", "D")
    await car.wait_without_integration(5)
    await car.start()
    await car.wait(60)
    assert car.coordinator.data.driving is False
    assert car.events == []
    await car.stop()


async def test_a_poll_on_the_way_home_keeps_the_route(
    car: Car, hass: HomeAssistant
) -> None:
    """The timing of the first real drive: the owner changed the route to home,
    and twelve seconds later a poll of the route tracker said ``home``."""
    car.entity_ids["polled_route"] = (
        er.async_get(hass)
        .async_get_or_create("device_tracker", "tesla_fleet", f"{VIN}-route")
        .entity_id
    )
    await car.report("polled_route", "unknown")
    await car.start()
    await car.coordinator.async_set_hidden(False)
    await car.report("speed", "40")
    await car.report("destination", "Home", {"latitude": 10.0, "longitude": 20.0})
    await car.wait(12)
    await car.report("speed", "41")
    await car.report("polled_route", "home", {"latitude": 10.0, "longitude": 20.0})
    assert car.coordinator.data.destination == "Home"
    for _ in range(9):
        await car.wait(15)
        await car.report("speed", "40")
    assert "heading_home" in car.types
    assert car.coordinator.data.heading_home is True
    await car.stop()


async def test_a_trip_with_no_odometer_is_measured_by_its_trail(car: Car) -> None:
    await car.start()
    await car.report("speed", "40")
    for step in range(1, 5):
        await car.report(
            "position", "not_home", {"latitude": 10 + step / 100, "longitude": 20.0}
        )
        await car.wait(15)
        await car.report("speed", "40")
    assert car.coordinator.data.trip_distance is not None
    await car.report("speed", "0")
    await car.wait(200)
    assert car.types == ["drive_started", "drive_ended"]
    assert car.events[-1].data["distance"] > 0
    assert car.events[-1].data["average_speed"] > 0
    await car.stop()

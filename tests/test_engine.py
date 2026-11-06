"""Replay the drives behind each trip engine rule.

Each scenario follows a real incident, with invented names and no positions.
Fixtures in this repo must never hold a real home or a real destination.
"""
from __future__ import annotations

from tesla_drive_tracker_isolated.engine import (
    STATE_DRIVING,
    STATE_OFFLINE,
    Reading,
    TripEngine,
    driving_evidence,
)

MOVING = {"speed": 60.0, "gear": "D", "occupied": True}
PARKED = {"speed": 0.0, "gear": "P", "occupied": False}


def feed(engine: TripEngine, start: int, stop: int, step: int = 10, **fields):
    """Send identical readings from ``start`` to ``stop`` and return the event
    names."""
    names = []
    for now in range(start, stop, step):
        names += [e.type for e in engine.update(Reading(now, **fields))]
    return names


def test_speed_proves_driving_when_occupancy_lies() -> None:
    # Occupancy read off at 82-107 mph.
    assert driving_evidence(Reading(0, speed=95, gear="D", occupied=False))
    assert driving_evidence(Reading(0, speed=95, gear=None, occupied=False))


def test_stuck_park_gear_does_not_hide_a_drive() -> None:
    engine = TripEngine()
    assert feed(engine, 0, 300, speed=60.0, gear="P", occupied=True) == [
        "drive_started"
    ]
    # Stopped at a light with the gear still stuck: one minute of grace.
    assert feed(engine, 300, 350, speed=0.0, gear="P", occupied=True) == []
    assert engine.driving


def test_real_gear_holds_a_drive_through_stopped_traffic() -> None:
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    assert feed(engine, 60, 600, speed=0.0, gear="D", occupied=False) == []
    assert engine.driving


def test_stale_charging_cannot_veto_a_moving_car() -> None:
    # Restored mid-Supercharge, and never updated on the unplug.
    engine = TripEngine()
    assert feed(engine, 0, 60, speed=70.0, gear="D", charging=True) == [
        "drive_started"
    ]


def test_charging_still_vetoes_a_slow_blip() -> None:
    assert not driving_evidence(
        Reading(0, speed=4, gear="P", occupied=True, charging=True)
    )


def test_a_lone_slow_blip_in_an_empty_car_is_not_a_drive() -> None:
    assert not driving_evidence(Reading(0, speed=4, gear="P", occupied=False))


def test_parked_car_setting_nav_home_is_not_a_trip() -> None:
    engine = TripEngine()
    names = feed(
        engine, 0, 2000, destination="Home", minutes_to_arrival=33.0, **PARKED
    )
    assert names == []
    assert engine.trip is None
    assert engine.state == "parked"


def test_route_events_wait_for_a_stable_route() -> None:
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    assert feed(engine, 60, 170, destination="Cafe", **MOVING) == []
    assert feed(engine, 170, 200, destination="Cafe", **MOVING) == ["destination_set"]
    assert engine.state == "navigating"


def test_replayed_route_fires_nothing() -> None:
    """Nav set to home 59 minutes out. The car replayed the previous leg's name
    and a 3-minute arrival, then settled, and the real mark came much later."""
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    names = feed(
        engine, 60, 100, destination="Home", minutes_to_arrival=59.0, **MOVING
    )
    names += feed(
        engine, 100, 130, destination="Home", minutes_to_arrival=3.0, **MOVING
    )
    names += feed(
        engine, 130, 150, destination="Elm Street", minutes_to_arrival=2.0, **MOVING
    )
    names += feed(
        engine, 150, 300, destination="Home", minutes_to_arrival=58.0, **MOVING
    )
    assert "arriving" not in names
    assert names == ["destination_set", "heading_home"]

    # The genuine approach still fires, once.
    names = feed(
        engine, 300, 320, destination="Home", minutes_to_arrival=6.0, **MOVING
    )
    names += feed(
        engine, 320, 500, destination="Home", minutes_to_arrival=5.0, **MOVING
    )
    names += feed(
        engine, 500, 520, destination="Home", minutes_to_arrival=6.0, **MOVING
    )
    names += feed(
        engine, 520, 540, destination="Home", minutes_to_arrival=5.0, **MOVING
    )
    assert names == ["arriving"]
    assert engine.state == "arriving"


def test_a_jump_past_the_threshold_is_not_a_crossing() -> None:
    engine = TripEngine()
    feed(engine, 0, 200, destination="Home", minutes_to_arrival=40.0, **MOVING)
    assert (
        feed(engine, 200, 240, destination="Home", minutes_to_arrival=3.0, **MOVING)
        == []
    )


def test_each_threshold_fires_once() -> None:
    engine = TripEngine(thresholds=(10, 5))
    feed(engine, 0, 200, destination="Cafe", minutes_to_arrival=12.0, **MOVING)
    names = []
    for now, minutes in ((200, 10.0), (210, 8.0), (220, 5.0), (230, 4.0)):
        for event in engine.update(
            Reading(now, destination="Cafe", minutes_to_arrival=minutes, **MOVING)
        ):
            names.append((event.type, event.data["threshold"]))
    assert names == [("arriving", 10), ("arriving", 5)]


def test_drive_ends_with_a_summary() -> None:
    engine = TripEngine()
    engine.update(Reading(0, odometer=1000.0, battery=80.0, at_home=True, **MOVING))
    engine.update(Reading(1800, odometer=1030.0, battery=70.0, **MOVING))
    engine.update(Reading(3600, odometer=1060.0, battery=60.0, **MOVING))
    ended = []
    for now in range(3610, 3800, 10):
        ended += engine.update(Reading(now, odometer=1060.0, battery=60.0, **PARKED))
    assert [e.type for e in ended] == ["drive_ended"]
    assert ended[0].data == {
        "distance": 60.0,
        "duration": 3610,
        "average_speed": 59.8,
        "battery_used": 20.0,
    }
    assert engine.trip is None


def test_car_sleeping_right_after_parking_still_ends_the_drive() -> None:
    """Speed and gear both go unknown within three minutes of parking on about
    a quarter of real drives, and the car then stays silent for hours."""
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    assert feed(engine, 60, 120, **PARKED) == []
    assert feed(engine, 120, 260) == ["drive_ended"]
    assert engine.trip is None
    assert not engine.driving


def test_stream_drop_is_not_parking() -> None:
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    assert feed(engine, 60, 900) == []  # nothing known for 14 minutes
    assert engine.driving
    assert feed(engine, 900, 960, **MOVING) == []
    assert engine.trip is not None


def test_a_trip_silent_for_half_an_hour_is_dropped() -> None:
    """The stream died at speed and the car slept, so nothing says it parked."""
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    assert feed(engine, 60, 2000) == []
    assert engine.trip is None
    assert not engine.driving


def test_stream_drop_then_parked_ends_after_the_full_delay() -> None:
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    feed(engine, 60, 900)
    assert feed(engine, 900, 1070, **PARKED) == []
    assert feed(engine, 1070, 1090, **PARKED) == ["drive_ended"]


def test_restart_mid_drive_does_not_repeat_anything() -> None:
    engine = TripEngine()
    feed(engine, 0, 200, destination="Home", minutes_to_arrival=6.0, **MOVING)
    feed(engine, 200, 210, destination="Home", minutes_to_arrival=5.0, **MOVING)

    restored = TripEngine.from_dict(engine.as_dict())
    names = feed(
        restored, 300, 400, destination="Home", minutes_to_arrival=4.0, **MOVING
    )
    assert names == []
    assert restored.trip.heading_home_sent


def test_restart_cannot_cross_a_threshold_on_its_first_reading() -> None:
    engine = TripEngine()
    feed(engine, 0, 200, destination="Home", minutes_to_arrival=6.0, **MOVING)
    restored = TripEngine.from_dict(engine.as_dict())
    assert (
        feed(restored, 210, 220, destination="Home", minutes_to_arrival=5.0, **MOVING)
        == []
    )


def test_drive_that_ended_across_a_restart_stays_silent() -> None:
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    restored = TripEngine.from_dict(engine.as_dict())
    assert feed(restored, 120, 400, **PARKED) == []
    assert restored.trip is None


def test_long_outage_starts_a_new_trip() -> None:
    engine = TripEngine()
    feed(engine, 0, 60, **MOVING)
    restored = TripEngine.from_dict(engine.as_dict())
    assert feed(restored, 7200, 7230, **MOVING) == ["drive_started"]


def test_lowercase_home_is_a_zone_verdict_not_a_destination() -> None:
    engine = TripEngine()
    assert feed(engine, 0, 300, destination="home", **MOVING) == ["drive_started"]
    assert engine.state == "driving"


def test_offline_and_charging_states() -> None:
    engine = TripEngine()
    assert engine.state == "offline"
    engine.update(Reading(0, speed=0.0, gear="P", charging=True))
    assert engine.state == "charging"
    engine.update(Reading(10, speed=0.0, gear="P", online=False))
    assert engine.state == "offline"


def test_a_driving_car_is_never_offline() -> None:
    engine = TripEngine()
    engine.update(Reading(0, speed=40, online=False))
    assert engine.state == STATE_DRIVING


def test_a_parked_car_can_be_offline() -> None:
    engine = TripEngine()
    engine.update(Reading(0, speed=0, gear="P", online=False))
    assert engine.state == STATE_OFFLINE


def test_a_new_route_cannot_arrive_until_it_has_held() -> None:
    engine = TripEngine()
    engine.update(Reading(0, speed=40, destination="Cafe", minutes_to_arrival=7))
    events = engine.update(
        Reading(30, speed=40, destination="Cafe", minutes_to_arrival=4)
    )
    assert events == []

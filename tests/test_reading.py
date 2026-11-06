"""Build a Reading from the values picked for each role."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tesla_drive_tracker_isolated.reading import build_reading, minutes_until
from tesla_drive_tracker_isolated.sources import (
    ROLE_ARRIVAL,
    ROLE_CHARGING,
    ROLE_GEAR,
    ROLE_OCCUPANCY,
    ROLE_ONLINE,
    ROLE_SPEED,
)

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def test_an_empty_reading_knows_nothing() -> None:
    reading = build_reading({}, NOW.timestamp())
    assert reading.speed is None
    assert reading.gear is None
    assert reading.occupied is None
    assert reading.charging is None
    assert reading.minutes_to_arrival is None
    assert reading.online


def test_fleet_lowercase_gear_is_a_gear() -> None:
    assert build_reading({ROLE_GEAR: "d"}, 0).gear == "D"
    assert build_reading({ROLE_GEAR: "P"}, 0).gear == "P"


def test_an_unknown_gear_is_no_gear() -> None:
    assert build_reading({ROLE_GEAR: "SNA"}, 0).gear is None


def test_speed_arrives_as_text_from_a_state() -> None:
    assert build_reading({ROLE_SPEED: "61.5"}, 0).speed == 61.5
    assert build_reading({ROLE_SPEED: "fast"}, 0).speed is None


def test_starting_counts_as_charging() -> None:
    assert build_reading({ROLE_CHARGING: "starting"}, 0).charging is True
    assert build_reading({ROLE_CHARGING: "complete"}, 0).charging is False


def test_occupancy_and_online() -> None:
    reading = build_reading({ROLE_OCCUPANCY: "off", ROLE_ONLINE: "off"}, 0)
    assert reading.occupied is False
    assert reading.online is False


def test_arrival_timestamp_becomes_minutes() -> None:
    arrival = (NOW + timedelta(minutes=12)).isoformat()
    reading = build_reading({ROLE_ARRIVAL: arrival}, NOW.timestamp())
    assert reading.minutes_to_arrival == 12


def test_a_passed_arrival_is_no_arrival() -> None:
    arrival = (NOW - timedelta(minutes=1)).isoformat()
    assert minutes_until(arrival, NOW.timestamp()) is None
    assert minutes_until("soon", NOW.timestamp()) is None

"""Find a car's sources and pick the freshest usable value."""
from __future__ import annotations

from tesla_drive_tracker_isolated.sources import (
    FLEET,
    ROLE_DESTINATION,
    ROLE_ROUTE_LINE,
    ROLE_SPEED,
    ROLES,
    TELEMETRY,
    Sample,
    pick,
    role_for,
    vin_of,
)

VIN = "5YJSA1E40AA000000"  # invented
PUSHED, POLLED = ROLES[ROLE_SPEED]
STARTED = 1000.0


def test_vin_comes_from_either_platform() -> None:
    assert vin_of(f"{VIN}_location_telemetry") == VIN
    assert vin_of(f"{VIN}-location") == VIN
    assert vin_of("sensor_with_no_vin") is None


def test_roles_are_found_by_unique_id() -> None:
    found = role_for(TELEMETRY, "sensor", f"{VIN}_vehicle_speed_telemetry", VIN)
    assert [role for role, _ in found] == [ROLE_SPEED]
    found = role_for(FLEET, "sensor", f"{VIN}-drive_state_speed", VIN)
    assert [role for role, _ in found] == [ROLE_SPEED]


def test_one_entity_can_fill_two_roles() -> None:
    found = role_for(TELEMETRY, "device_tracker", f"{VIN}_location_telemetry", VIN)
    assert sorted(role for role, _ in found) == ["heading", "position"]


def test_catalog_route_line_is_found() -> None:
    found = role_for(TELEMETRY, "sensor", f"{VIN}_signal_RouteLine", VIN)
    assert [(role, source.attribute) for role, source in found] == [
        (ROLE_ROUTE_LINE, "route_line")
    ]


def test_another_cars_entity_fills_nothing() -> None:
    other = "5YJSA1E40AA000001"
    assert role_for(TELEMETRY, "sensor", f"{other}_gear_telemetry", VIN) == []


def test_freshest_wins() -> None:
    samples = [(PUSHED, Sample(30.0, 2000.0)), (POLLED, Sample(40.0, 2010.0))]
    assert pick(samples, 2020.0, STARTED) == 40.0


def test_a_restored_value_never_counts() -> None:
    assert pick([(PUSHED, Sample(60.0, 900.0))], 2000.0, STARTED) is None


def test_a_parked_cars_push_value_has_no_age_limit() -> None:
    assert pick([(PUSHED, Sample(0.0, 2000.0))], 90000.0, STARTED) == 0.0


def test_an_old_polled_speed_is_not_a_speed() -> None:
    # The poll held 39 mph for a parked car while telemetry went unknown.
    samples = [(PUSHED, Sample("unknown", 2000.0)), (POLLED, Sample(39.0, 2000.0))]
    assert pick(samples, 2300.0, STARTED) is None


def test_invalid_states_are_skipped() -> None:
    samples = [(PUSHED, Sample("unavailable", 2010.0)), (POLLED, Sample(5.0, 2000.0))]
    assert pick(samples, 2020.0, STARTED) == 5.0


ROUTE_PUSHED, ROUTE_POLLED = ROLES[ROLE_DESTINATION]


def test_a_polled_zone_word_does_not_end_a_named_route() -> None:
    """A poll landed mid-drive and blanked the route home on a real drive."""
    for word in ("home", "not_home"):
        samples = [
            (ROUTE_PUSHED, Sample("Home", 2000.0)),
            (ROUTE_POLLED, Sample(word, 2012.0)),
        ]
        assert pick(samples, 2013.0, STARTED) == "Home"


def test_a_polled_route_name_still_wins_when_fresher() -> None:
    samples = [
        (ROUTE_PUSHED, Sample("Place A", 2000.0)),
        (ROUTE_POLLED, Sample("Place B", 2012.0)),
    ]
    assert pick(samples, 2013.0, STARTED) == "Place B"


def test_the_pushed_tracker_can_still_end_a_route() -> None:
    samples = [
        (ROUTE_PUSHED, Sample("home", 2020.0)),
        (ROUTE_POLLED, Sample("Place B", 2012.0)),
    ]
    assert pick(samples, 2021.0, STARTED) == "home"


def test_a_polled_zone_word_counts_when_nothing_else_reports() -> None:
    samples = [(ROUTE_POLLED, Sample("home", 2012.0))]
    assert pick(samples, 2013.0, STARTED) == "home"

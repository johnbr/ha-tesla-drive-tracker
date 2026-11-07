"""What gets published about a car."""
from __future__ import annotations

from tesla_drive_tracker_isolated.engine import Reading, TripEngine
from tesla_drive_tracker_isolated.pairing import (
    STATUS_HIDDEN,
    STATUS_NONE,
    STATUS_PAIRED,
    DestinationFix,
)
from tesla_drive_tracker_isolated.route_line import RouteLine
from tesla_drive_tracker_isolated.view import build_view

PLACE = DestinationFix(STATUS_PAIRED, "Cafe", 10.0, 20.0)
LINE = RouteLine(((10.5, 20.5), (10.0, 20.0)))
OLD_LINE = RouteLine(((10.0, 20.0), (10.5, 20.5)))


def on_a_trip(destination: str = "Cafe") -> TripEngine:
    engine = TripEngine()
    engine.update(Reading(0, speed=40, destination=destination, odometer=100.0))
    engine.update(Reading(130, speed=40, destination=destination))
    return engine


def test_a_route_is_published_during_a_trip() -> None:
    view = build_view(
        on_a_trip(),
        fix=PLACE,
        hidden=False,
        now=130,
        minutes=12.4,
        distance=7.2,
        route_line=LINE,
    )
    assert view.destination == "Cafe"
    assert (view.destination_latitude, view.destination_longitude) == (10.0, 20.0)
    assert view.minutes == 12
    assert view.distance == 7.0
    assert view.route == LINE.points


def test_a_route_set_while_parked_is_not_published() -> None:
    engine = TripEngine()
    engine.update(Reading(0, speed=0, gear="P", destination="Home"))
    view = build_view(
        engine,
        fix=DestinationFix(STATUS_PAIRED, "Home", 1.0, 2.0),
        hidden=False,
        now=0,
        minutes=9,
        distance=3,
        arrival_battery=80,
        traffic_delay=2,
    )
    assert view.destination is None
    assert view.destination_status == STATUS_NONE
    assert view.destination_latitude is None
    assert view.minutes is None
    assert view.distance is None
    assert view.arrival_battery is None
    assert view.traffic_delay is None
    assert view.heading_home is False


def test_hidden_keeps_when_and_drops_where() -> None:
    view = build_view(
        on_a_trip("Home"),
        fix=DestinationFix(STATUS_HIDDEN),
        hidden=True,
        now=130,
        minutes=12,
        distance=7,
        route_line=LINE,
    )
    assert view.minutes == 12
    assert view.arrival_at is not None
    assert view.destination is None
    assert view.distance is None
    assert view.route is None
    assert view.heading_home is None
    assert view.destination_status == STATUS_HIDDEN


def test_a_line_to_somewhere_else_is_not_drawn() -> None:
    view = build_view(
        on_a_trip(), fix=PLACE, hidden=False, now=130, route_line=OLD_LINE
    )
    assert view.route is None


def test_no_pin_means_no_line() -> None:
    fix = DestinationFix("unpaired", "Cafe")
    view = build_view(on_a_trip(), fix=fix, hidden=False, now=130, route_line=LINE)
    assert view.destination == "Cafe"
    assert view.destination_latitude is None
    assert view.route is None


def test_heading_home_goes_off_as_soon_as_the_route_changes() -> None:
    engine = on_a_trip("Home")
    engine.update(Reading(140, speed=40, destination="Home"))
    fix = DestinationFix(STATUS_PAIRED, "Home", 1.0, 2.0)
    assert build_view(engine, fix=fix, hidden=False, now=140).heading_home is True
    engine.update(Reading(150, speed=40, destination="not_home"))
    assert build_view(engine, fix=fix, hidden=False, now=150).heading_home is False


def test_heading_home_goes_off_when_the_car_parks() -> None:
    engine = on_a_trip("Home")
    engine.update(Reading(140, speed=40, destination="Home"))
    fix = DestinationFix(STATUS_PAIRED, "Home", 1.0, 2.0)
    for now in range(150, 230, 10):
        engine.update(Reading(now, speed=0, gear="P", destination="Home"))
    assert engine.trip is not None
    assert build_view(engine, fix=fix, hidden=False, now=230).heading_home is False


def test_trip_figures_run_during_a_trip_and_hold_after_it() -> None:
    fix = DestinationFix(STATUS_NONE)
    view = build_view(on_a_trip(), fix=fix, hidden=False, now=600, odometer=103.0)
    assert view.trip_distance == 3.0
    assert view.trip_duration == 10
    view = build_view(on_a_trip(), fix=fix, hidden=False, now=600, travelled=2.0)
    assert view.trip_distance == 2.0
    view = build_view(
        TripEngine(),
        fix=fix,
        hidden=False,
        now=9000,
        last_trip={"distance": 12.0, "duration": 1500},
    )
    assert view.trip_distance == 12.0
    assert view.trip_duration == 25

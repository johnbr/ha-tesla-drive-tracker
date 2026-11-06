"""What the integration publishes about a car at one moment.

Entities and the websocket both read this one object, so a value hidden here is
hidden everywhere. Two rules are applied on the way in:

- A route exists only during a trip. The car sets navigation home by itself when
  parked, and the arrival figures keep the last route's values after it ends.
- While hidden, nothing that places the destination gets in. Arrival time stays,
  because when isn't where.

This module imports nothing from Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from .engine import TripEngine, is_home
from .pairing import STATUS_HIDDEN, STATUS_NONE, STATUS_PAIRED, DestinationFix
from .privacy import coarse_distance, coarse_minutes
from .route_line import RouteLine, ends_at


@dataclass(frozen=True, slots=True)
class DriveView:
    """One car, ready to publish, with anything unknown as ``None``."""

    state: str
    driving: bool
    hidden: bool
    destination_status: str = STATUS_NONE
    destination: str | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None
    heading_home: bool | None = None
    arrival_at: float | None = None
    minutes: int | None = None
    distance: float | None = None
    arrival_battery: float | None = None
    traffic_delay: float | None = None
    route: tuple[tuple[float, float], ...] | None = None
    latitude: float | None = None
    longitude: float | None = None
    heading: float | None = None
    speed: float | None = None
    battery: float | None = None
    position_at: float | None = None
    trip_started_at: float | None = None
    trip_distance: float | None = None
    trip_duration: int | None = None

    def as_wire(self) -> dict[str, Any]:
        """Plain data for the websocket, sharing the route rather than copying it."""
        return {item.name: getattr(self, item.name) for item in fields(self)}


def build_view(
    engine: TripEngine,
    *,
    fix: DestinationFix,
    hidden: bool,
    now: float,
    minutes: float | None = None,
    distance: float | None = None,
    arrival_battery: float | None = None,
    traffic_delay: float | None = None,
    route_line: RouteLine | None = None,
    odometer: float | None = None,
    last_trip: dict[str, Any] | None = None,
    **position: float | None,
) -> DriveView:
    """The view of a car from what the engine and its sources say now."""
    trip = engine.trip
    routed = trip is not None and bool(engine.route)
    shown = routed and not hidden
    paired = shown and fix.status == STATUS_PAIRED
    destination = (fix.latitude, fix.longitude) if paired else None

    route = None
    line = route_line.points if route_line is not None else ()
    if destination is not None and ends_at(line, destination):
        route = line

    held = last_trip or {}
    trip_distance = held.get("distance")
    trip_duration = held.get("duration")
    if trip is not None:
        trip_duration = now - trip.started_at
        trip_distance = None
        if odometer is not None and trip.start_odometer is not None:
            trip_distance = odometer - trip.start_odometer

    return DriveView(
        state=engine.state,
        driving=engine.driving,
        hidden=hidden,
        destination_status=(
            STATUS_HIDDEN if hidden else fix.status if routed else STATUS_NONE
        ),
        destination=fix.name or None if shown else None,
        destination_latitude=fix.latitude if paired else None,
        destination_longitude=fix.longitude if paired else None,
        # Slow to come on, because the engine waits for a stable route, and
        # immediate to go off.
        heading_home=(
            None
            if hidden
            else trip is not None
            and is_home(trip.destination)
            and is_home(engine.route)
        ),
        arrival_at=(
            round((now + minutes * 60) / 60) * 60
            if routed and minutes is not None
            else None
        ),
        minutes=coarse_minutes(minutes) if routed else None,
        distance=coarse_distance(distance) if shown else None,
        arrival_battery=arrival_battery if routed else None,
        traffic_delay=traffic_delay if routed else None,
        route=route,
        trip_started_at=trip.started_at if trip is not None else None,
        trip_distance=coarse_distance(trip_distance),
        trip_duration=(
            None if trip_duration is None else round(trip_duration / 60)
        ),
        **position,
    )

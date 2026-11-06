"""Decide when a car is on a drive, and what happened during it.

Every rule here comes from a drive that went wrong, and the telemetry lies in
specific ways:

- Occupancy has read ``off`` at 82-107 mph, so speed proves driving on its own.
- Gear fails only by sticking at ``P``, for a whole drive at worst. A real
  ``D``, ``R`` or ``N`` is proof, and ``P`` proves nothing.
- ``charging`` can be restored stale after a restart mid-charge, so it vetoes
  only the slow occupancy test and never a car that is clearly moving.
- A car sets navigation to home by itself on arrival, so a route is never
  evidence of a drive, and nothing about a route is reported outside a trip.
- About 90 s after a new route is set the car can replay the previous route's
  name and arrival time, so a route must hold for two minutes and an arrival
  needs a real downward crossing rather than a jump.

``None`` in a ``Reading`` means the value is unknown or stale, which is different
from a car reporting zero. A stream drop therefore pauses the engine rather than
looking like a parked car, and a trip that stays silent for 30 minutes is dropped
without an event. Silence after the car has stopped is the car going to sleep, so
that keeps counting towards the end of the trip. Restored values must arrive here
as ``None``.

``update`` must also be called on a timer, because a parked car sends nothing and
the delays below only advance when a reading arrives.

This module imports nothing from Home Assistant, so a recorded drive can be
replayed through it directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .pairing import NOT_A_NAME

PROOF_SPEED_MPH = 10
CREEP_SPEED_MPH = 3
MOVING_GEARS = frozenset({"D", "R", "N"})

DRIVING_OFF_SECONDS = 60
TRIP_END_SECONDS = 180
ROUTE_STABLE_SECONDS = 120
SILENT_TRIP_MAX_SECONDS = 1800

# How far above a threshold the previous reading may be and still count as an
# approach. A real approach steps down through it, and a replay jumps in from
# far above or from nothing.
CROSSING_WINDOW_MINUTES = 15
DEFAULT_THRESHOLDS = (5,)

EVENT_DRIVE_STARTED = "drive_started"
EVENT_DRIVE_ENDED = "drive_ended"
EVENT_DESTINATION_SET = "destination_set"
EVENT_DESTINATION_CHANGED = "destination_changed"
EVENT_DESTINATION_CLEARED = "destination_cleared"
EVENT_HEADING_HOME = "heading_home"
EVENT_ARRIVING = "arriving"

STATE_PARKED = "parked"
STATE_DRIVING = "driving"
STATE_NAVIGATING = "navigating"
STATE_ARRIVING = "arriving"
STATE_CHARGING = "charging"
STATE_OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class Reading:
    """The car at one moment, with anything unknown or stale as ``None``."""

    timestamp: float
    speed: float | None = None
    gear: str | None = None
    occupied: bool | None = None
    charging: bool | None = None
    destination: str | None = None
    minutes_to_arrival: float | None = None
    odometer: float | None = None
    battery: float | None = None
    at_home: bool | None = None
    online: bool = True


@dataclass(frozen=True, slots=True)
class DriveEvent:
    """Something an automation can hook."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Trip:
    """One drive, kept across a restart so its events never repeat."""

    started_at: float
    from_home: bool | None = None
    start_odometer: float | None = None
    start_battery: float | None = None
    destination: str = ""
    heading_home_sent: bool = False
    thresholds_sent: list[float] = field(default_factory=list)
    restored: bool = False


def driving_evidence(reading: Reading) -> bool | None:
    """What this reading alone says, or ``None`` when it says nothing."""
    if reading.speed is None and reading.gear is None:
        return None
    speed = reading.speed or 0
    if speed >= PROOF_SPEED_MPH or reading.gear in MOVING_GEARS:
        return True
    return (
        reading.occupied is True
        and not reading.charging
        and speed >= CREEP_SPEED_MPH
    )


def is_home(name: str) -> bool:
    """Whether a destination name means home."""
    return name.lower() == "home"


class TripEngine:
    """Turns a stream of readings into a driving state and drive events."""

    def __init__(self, thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS) -> None:
        self.thresholds = tuple(sorted(thresholds, reverse=True))
        self.driving = False
        self.trip: Trip | None = None
        self._last_evidence_at: float | None = None
        self._idle_since: float | None = None
        self._route = ""
        self._route_since = 0.0
        self._minutes: float | None = None
        self._last: Reading | None = None

    def update(self, reading: Reading) -> list[DriveEvent]:
        """Take one reading and return the events it caused."""
        events: list[DriveEvent] = []
        self._expire_silent_trip(reading)
        route_changed = self._track_route(reading)

        evidence = driving_evidence(reading)
        if evidence is not None:
            self._last_evidence_at = reading.timestamp
        if evidence is True:
            self._on_driving(reading, events)
        elif evidence is False or self._idle_since is not None:
            self._on_idle(reading, events)

        if self.trip is not None:
            self._report_route(reading, events)
            self._report_arrival(reading, route_changed, events)
        if reading.minutes_to_arrival is not None:
            self._minutes = reading.minutes_to_arrival
        self._last = reading
        return events

    def _expire_silent_trip(self, reading: Reading) -> None:
        """Drop a trip nothing has been heard about for a long time.

        A stream that dies at speed leaves the last values looking like a
        drive, and a long outage leaves a restored trip with no meaning.
        """
        if (
            self.trip is not None
            and self._last_evidence_at is not None
            and reading.timestamp - self._last_evidence_at > SILENT_TRIP_MAX_SECONDS
        ):
            self.trip = None
            self.driving = False
            self._idle_since = None

    def _track_route(self, reading: Reading) -> bool:
        """Follow the reported route, returning whether it changed."""
        if reading.destination is None:
            return False
        name = "" if reading.destination in NOT_A_NAME else reading.destination
        if name == self._route:
            return False
        self._route = name
        self._route_since = reading.timestamp
        self._minutes = None
        return True

    def _route_stable(self, reading: Reading) -> bool:
        return reading.timestamp - self._route_since >= ROUTE_STABLE_SECONDS

    def _on_driving(self, reading: Reading, events: list[DriveEvent]) -> None:
        self._idle_since = None
        self.driving = True
        if self.trip is not None:
            self.trip.restored = False
            return
        self.trip = Trip(
            started_at=reading.timestamp,
            from_home=reading.at_home,
            start_odometer=reading.odometer,
            start_battery=reading.battery,
        )
        events.append(
            DriveEvent(
                EVENT_DRIVE_STARTED,
                {
                    "from_home": reading.at_home,
                    "battery": reading.battery,
                    "odometer": reading.odometer,
                },
            )
        )

    def _on_idle(self, reading: Reading, events: list[DriveEvent]) -> None:
        if self._idle_since is None:
            self._idle_since = reading.timestamp
        idle = reading.timestamp - self._idle_since
        if idle >= DRIVING_OFF_SECONDS:
            self.driving = False
        if self.trip is None or idle < TRIP_END_SECONDS:
            return
        trip = self.trip
        self.trip = None
        # A drive that ended across a restart stays silent: the bias here is
        # to miss an event rather than to fire a wrong one.
        if not trip.restored:
            events.append(self._ended(trip, reading))

    def _ended(self, trip: Trip, reading: Reading) -> DriveEvent:
        ended_at = self._idle_since or reading.timestamp
        duration = ended_at - trip.started_at
        distance = None
        if reading.odometer is not None and trip.start_odometer is not None:
            distance = round(reading.odometer - trip.start_odometer, 1)
        battery_used = None
        if reading.battery is not None and trip.start_battery is not None:
            battery_used = round(trip.start_battery - reading.battery, 1)
        average_speed = None
        if distance is not None and duration > 0:
            average_speed = round(distance / (duration / 3600), 1)
        return DriveEvent(
            EVENT_DRIVE_ENDED,
            {
                "distance": distance,
                "duration": round(duration),
                "average_speed": average_speed,
                "battery_used": battery_used,
            },
        )

    def _report_route(self, reading: Reading, events: list[DriveEvent]) -> None:
        trip = self.trip
        if trip is None or self._route == trip.destination:
            return
        if not self._route_stable(reading):
            return
        previous = trip.destination
        trip.destination = self._route
        if not previous:
            kind = EVENT_DESTINATION_SET
        elif not self._route:
            kind = EVENT_DESTINATION_CLEARED
        else:
            kind = EVENT_DESTINATION_CHANGED
        events.append(
            DriveEvent(
                kind, {"destination": self._route, "home": is_home(self._route)}
            )
        )
        if is_home(self._route) and not trip.heading_home_sent:
            trip.heading_home_sent = True
            events.append(
                DriveEvent(
                    EVENT_HEADING_HOME, {"minutes": reading.minutes_to_arrival}
                )
            )

    def _report_arrival(
        self, reading: Reading, route_changed: bool, events: list[DriveEvent]
    ) -> None:
        trip = self.trip
        minutes = reading.minutes_to_arrival
        previous = self._minutes
        if (
            trip is None
            or route_changed
            or not self.driving
            or not self._route
            or minutes is None
            or previous is None
            or not self._route_stable(reading)
        ):
            return
        for threshold in self.thresholds:
            if threshold in trip.thresholds_sent:
                continue
            if minutes <= threshold < previous <= threshold + CROSSING_WINDOW_MINUTES:
                trip.thresholds_sent.append(threshold)
                events.append(
                    DriveEvent(
                        EVENT_ARRIVING,
                        {
                            "threshold": threshold,
                            "minutes": minutes,
                            "home": is_home(self._route),
                        },
                    )
                )

    @property
    def state(self) -> str:
        """The drive state of the last reading."""
        last = self._last
        if last is None or not last.online:
            return STATE_OFFLINE
        if not self.driving:
            return STATE_CHARGING if last.charging else STATE_PARKED
        if not self._route or not self._route_stable(last):
            return STATE_DRIVING
        minutes = last.minutes_to_arrival
        if minutes is not None and self.thresholds and minutes <= self.thresholds[0]:
            return STATE_ARRIVING
        return STATE_NAVIGATING

    def as_dict(self) -> dict[str, Any]:
        """The engine's memory as plain data for ``Store``."""
        return {
            "driving": self.driving,
            "trip": asdict(self.trip) if self.trip is not None else None,
            "last_evidence_at": self._last_evidence_at,
            "idle_since": self._idle_since,
            "route": self._route,
            "route_since": self._route_since,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
    ) -> TripEngine:
        """Rebuild an engine after a restart.

        The trip is marked restored, and the last arrival figure is not kept,
        so the first reading can neither start a drive nor cross a threshold.
        """
        engine = cls(thresholds)
        engine.driving = data.get("driving", False)
        trip = data.get("trip")
        if trip is not None:
            engine.trip = Trip(**{**trip, "restored": True})
        engine._last_evidence_at = data.get("last_evidence_at")
        engine._idle_since = data.get("idle_since")
        engine._route = data.get("route", "")
        engine._route_since = data.get("route_since", 0.0)
        return engine

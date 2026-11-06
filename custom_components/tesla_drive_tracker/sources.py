"""Where each piece of a car's data comes from.

Entities are found through the registry by platform and unique_id, never by
entity_id text, because owners rename things. Both supported platforms embed the
VIN in their unique_ids, which is also how their two devices are paired.

Each role lists its candidates and the freshest valid value wins. Three rules
keep a stale value out:

- A value last reported before ``started_at`` is a restored one, so it never
  counts. Source integrations write restored values during startup, so
  ``started_at`` must be when Home Assistant finished starting, not when it began.
- Push signals hold their last value legitimately, because a parked car doesn't
  repeat itself, so they have no age limit. A moving car does repeat itself, and
  ``reading.stream_silent`` handles a stream that stops mid-drive.
- A polled value does. The poll can hold the speed of the drive long after the
  car parked, which has shown 39 mph for a stationary car.

This module imports nothing from Home Assistant.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

TELEMETRY = "tesla_telemetry"
FLEET = "tesla_fleet"

POLLED_MAX_AGE_SECONDS = 120

ROLE_POSITION = "position"
ROLE_HEADING = "heading"
ROLE_SPEED = "speed"
ROLE_GEAR = "gear"
ROLE_DESTINATION = "destination"
ROLE_ARRIVAL = "arrival"
ROLE_DISTANCE = "distance"
ROLE_TRAFFIC_DELAY = "traffic_delay"
ROLE_BATTERY = "battery"
ROLE_ARRIVAL_BATTERY = "arrival_battery"
ROLE_ROUTE_LINE = "route_line"
ROLE_OCCUPANCY = "occupancy"
ROLE_CHARGING = "charging"
ROLE_ODOMETER = "odometer"
ROLE_ONLINE = "online"
ROLE_PAINT = "paint"
ROLE_ROOF = "roof"
ROLE_CAR_TYPE = "car_type"

INVALID_STATES = frozenset({"unknown", "unavailable", "none", ""})
VIN_PATTERN = re.compile(r"^[0-9A-HJ-NPR-Z]{17}(?=[-_])")


@dataclass(frozen=True, slots=True)
class Source:
    """One entity that can fill a role, found by its unique_id's ending."""

    platform: str
    domain: str
    suffix: str
    attribute: str | None = None
    max_age: float | None = None


def _telemetry(domain: str, suffix: str, attribute: str | None = None) -> Source:
    return Source(TELEMETRY, domain, suffix, attribute)


def _fleet(domain: str, key: str) -> Source:
    return Source(FLEET, domain, f"-{key}", max_age=POLLED_MAX_AGE_SECONDS)


ROLES: dict[str, tuple[Source, ...]] = {
    ROLE_POSITION: (
        _telemetry("device_tracker", "_location_telemetry"),
        _fleet("device_tracker", "location"),
    ),
    ROLE_HEADING: (
        _telemetry("device_tracker", "_location_telemetry", "heading"),
    ),
    ROLE_SPEED: (
        _telemetry("sensor", "_vehicle_speed_telemetry"),
        _fleet("sensor", "drive_state_speed"),
    ),
    ROLE_GEAR: (
        _telemetry("sensor", "_gear_telemetry"),
        _fleet("sensor", "drive_state_shift_state"),
    ),
    ROLE_DESTINATION: (
        _telemetry("device_tracker", "_route_telemetry"),
        _fleet("device_tracker", "route"),
    ),
    ROLE_ARRIVAL: (
        _telemetry("sensor", "_time_to_arrival_telemetry"),
        _fleet("sensor", "drive_state_active_route_minutes_to_arrival"),
    ),
    ROLE_DISTANCE: (
        _telemetry("sensor", "_miles_to_arrival_telemetry"),
        _fleet("sensor", "drive_state_active_route_miles_to_arrival"),
    ),
    ROLE_TRAFFIC_DELAY: (
        _telemetry("sensor", "_signal_RouteTrafficMinutesDelay"),
        _fleet("sensor", "drive_state_active_route_traffic_minutes_delay"),
    ),
    ROLE_BATTERY: (
        _telemetry("sensor", "_battery_level_telemetry"),
        _fleet("sensor", "charge_state_battery_level"),
    ),
    ROLE_ARRIVAL_BATTERY: (
        _telemetry("sensor", "_signal_ExpectedEnergyPercentAtTripArrival"),
        _fleet("sensor", "drive_state_active_route_energy_at_arrival"),
    ),
    ROLE_ROUTE_LINE: (
        _telemetry("sensor", "_signal_RouteLine", "route_line"),
    ),
    ROLE_OCCUPANCY: (
        _telemetry("binary_sensor", "_user_present_telemetry"),
        _fleet("binary_sensor", "vehicle_state_is_user_present"),
    ),
    ROLE_CHARGING: (
        _telemetry("sensor", "_charging_state_telemetry"),
        _fleet("sensor", "charge_state_charging_state"),
    ),
    ROLE_ODOMETER: (
        _telemetry("sensor", "_odometer_telemetry"),
        _fleet("sensor", "vehicle_state_odometer"),
    ),
    # Not a polled limit: a sleeping car's status legitimately holds between polls.
    ROLE_ONLINE: (Source(FLEET, "binary_sensor", "-state"),),
    ROLE_PAINT: (_telemetry("sensor", "_signal_ExteriorColor"),),
    ROLE_ROOF: (_telemetry("sensor", "_signal_RoofColor"),),
    ROLE_CAR_TYPE: (_telemetry("sensor", "_signal_CarType"),),
}


@dataclass(frozen=True, slots=True)
class Sample:
    """A source's current value and when it last reported."""

    value: Any
    reported_at: float
    latitude: float | None = None
    longitude: float | None = None


def vin_of(unique_id: str) -> str | None:
    """The VIN a unique_id starts with, or ``None`` when it has none."""
    match = VIN_PATTERN.match(unique_id)
    return match.group(0) if match else None


def role_for(
    platform: str, domain: str, unique_id: str, vin: str
) -> list[tuple[str, Source]]:
    """Every role one registry entry can fill for a car."""
    if not unique_id.startswith(vin):
        return []
    suffix = unique_id[len(vin) :]
    return [
        (role, source)
        for role, sources in ROLES.items()
        for source in sources
        if (source.platform, source.domain, source.suffix)
        == (platform, domain, suffix)
    ]


def _usable(source: Source, sample: Sample, now: float, started_at: float) -> bool:
    value = sample.value
    if value is None or str(value).lower() in INVALID_STATES:
        return False
    if sample.reported_at < started_at:
        return False
    return source.max_age is None or now - sample.reported_at <= source.max_age


def pick_sample(
    samples: Iterable[tuple[Source, Sample]], now: float, started_at: float
) -> Sample | None:
    """The freshest usable sample of a role, or ``None`` when there isn't one."""
    usable = [
        sample
        for source, sample in samples
        if _usable(source, sample, now, started_at)
    ]
    if not usable:
        return None
    return max(usable, key=lambda sample: sample.reported_at)


def pick(
    samples: Iterable[tuple[Source, Sample]], now: float, started_at: float
) -> Any:
    """The freshest usable value of a role, or ``None`` when there isn't one."""
    sample = pick_sample(samples, now, started_at)
    return None if sample is None else sample.value

"""Turn the values picked for each role into a ``Reading``.

The platforms disagree on case: telemetry reports gear as ``P`` and Fleet as
``p``. Fleet also reports ``p`` when it has no gear at all, which is harmless
because ``P`` proves nothing.

This module imports nothing from Home Assistant.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .engine import (
    CREEP_SPEED_MPH,
    MOVING_GEARS,
    SILENT_TRIP_MAX_SECONDS,
    Reading,
)
from .sources import (
    ROLE_ARRIVAL,
    ROLE_BATTERY,
    ROLE_CHARGING,
    ROLE_DESTINATION,
    ROLE_GEAR,
    ROLE_OCCUPANCY,
    ROLE_ODOMETER,
    ROLE_ONLINE,
    ROLE_SPEED,
)

CHARGING_STATES = frozenset({"charging", "starting"})

# A moving car reported within 7 s 99.9% of the time over 29 days. The rest were
# dead zones, up to 317 s, and nothing in them marks the values unknown.
MOVING_SILENCE_SECONDS = 120


def number(value: Any) -> float | None:
    """A float from a state, or ``None`` when it isn't one."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gear(value: Any) -> str | None:
    gear = str(value).upper() if value is not None else None
    return gear if gear == "P" or gear in MOVING_GEARS else None


def _switch(value: Any) -> bool | None:
    return {"on": True, "off": False}.get(value)


def _charging(value: Any) -> bool | None:
    return None if value is None else str(value).lower() in CHARGING_STATES


def stream_silent(
    speed: Any, speed_at: float | None, gear: Any, gear_at: float | None, now: float
) -> bool:
    """Whether the car's last words about moving have outlived their meaning.

    A dropped stream leaves its last values in place, so a frozen 60 mph would
    otherwise look like a drive for ever. A car stopped in gear repeats nothing
    either, which a red light explains for a while but not for half an hour.
    """
    heard = [at for at in (speed_at, gear_at) if at is not None]
    if not heard:
        return False
    age = now - max(heard)
    if (number(speed) or 0) >= CREEP_SPEED_MPH:
        return age > MOVING_SILENCE_SECONDS
    return _gear(gear) in MOVING_GEARS and age > SILENT_TRIP_MAX_SECONDS


def minutes_until(value: Any, now: float) -> float | None:
    """Minutes to arrival, or ``None`` once it has passed.

    The car gives a timestamp, and a role pointed at a travel time sensor gives
    plain minutes.
    """
    minutes = number(value)
    if minutes is None:
        try:
            arrival = datetime.fromisoformat(str(value)).timestamp()
        except ValueError:
            return None
        minutes = (arrival - now) / 60
    return minutes if minutes > 0 else None


def build_reading(
    values: Mapping[str, Any], now: float, *, at_home: bool | None = None
) -> Reading:
    """The car right now, from the value picked for each role."""
    return Reading(
        timestamp=now,
        speed=number(values.get(ROLE_SPEED)),
        gear=_gear(values.get(ROLE_GEAR)),
        occupied=_switch(values.get(ROLE_OCCUPANCY)),
        charging=_charging(values.get(ROLE_CHARGING)),
        destination=values.get(ROLE_DESTINATION),
        minutes_to_arrival=minutes_until(values.get(ROLE_ARRIVAL), now),
        odometer=number(values.get(ROLE_ODOMETER)),
        battery=number(values.get(ROLE_BATTERY)),
        at_home=at_home,
        online=values.get(ROLE_ONLINE) != "off",
    )

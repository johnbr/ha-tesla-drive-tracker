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

from .engine import MOVING_GEARS, Reading
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


def _number(value: Any) -> float | None:
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


def minutes_until(value: Any, now: float) -> float | None:
    """Minutes to an arrival timestamp, or ``None`` once it has passed."""
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
        speed=_number(values.get(ROLE_SPEED)),
        gear=_gear(values.get(ROLE_GEAR)),
        occupied=_switch(values.get(ROLE_OCCUPANCY)),
        charging=_charging(values.get(ROLE_CHARGING)),
        destination=values.get(ROLE_DESTINATION),
        minutes_to_arrival=minutes_until(values.get(ROLE_ARRIVAL), now),
        odometer=_number(values.get(ROLE_ODOMETER)),
        battery=_number(values.get(ROLE_BATTERY)),
        at_home=at_home,
        online=values.get(ROLE_ONLINE) != "off",
    )

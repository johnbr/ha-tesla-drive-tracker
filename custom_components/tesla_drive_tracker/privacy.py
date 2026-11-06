"""Keep a hidden destination out of everything the integration publishes.

Redaction happens here rather than in a card, so one rule covers entities, events
and the websocket. A new car starts with the destination shown. Once a state has
been saved it fails hidden: anything but a clean ``off`` counts as hidden, because
a destination shown by mistake can't be taken back.

Arrival time stays visible while hidden. When isn't where, and an automation can
still say someone is five minutes away. Distance and the route line stay hidden,
because each can place the destination.

This is display privacy, not access control: any logged-in user can still read
the source entities.

This module imports nothing from Home Assistant.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from .engine import DriveEvent

HIDDEN_KEYS = frozenset({"destination", "distance", "route", "home"})

# Coarse enough that a moving car doesn't write a recorder row per fix.
DISTANCE_STEP_NEAR = 0.5
DISTANCE_STEP_FAR = 5.0
DISTANCE_FAR_FROM = 20.0


def is_hidden(state: str | None) -> bool:
    """Whether a hide switch's state means hidden."""
    return state != "off"


def redact(data: dict[str, Any], hidden: bool) -> dict[str, Any]:
    """A payload with everything that places the destination removed."""
    if not hidden:
        return data
    return {key: value for key, value in data.items() if key not in HIDDEN_KEYS}


def redact_event(event: DriveEvent, hidden: bool) -> DriveEvent:
    """An event that still fires, without the destination."""
    return replace(event, data=redact(event.data, hidden))


def coarse_distance(miles: float | None) -> float | None:
    """A distance in steps, finer as the car gets close."""
    if miles is None:
        return None
    step = DISTANCE_STEP_FAR if miles >= DISTANCE_FAR_FROM else DISTANCE_STEP_NEAR
    return round(miles / step) * step


def coarse_minutes(minutes: float | None) -> int | None:
    """Minutes remaining, rounded so an entity changes once a minute at most."""
    return None if minutes is None else round(minutes)

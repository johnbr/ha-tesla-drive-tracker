"""Hidden means hidden everywhere, and it fails towards hidden."""
from __future__ import annotations

import pytest
from tesla_drive_tracker_isolated.engine import DriveEvent
from tesla_drive_tracker_isolated.privacy import (
    coarse_distance,
    coarse_minutes,
    is_hidden,
    redact,
    redact_event,
)


@pytest.mark.parametrize("state", ["on", "unknown", "unavailable", "", None])
def test_anything_but_a_clean_off_hides(state) -> None:
    assert is_hidden(state)


def test_a_clean_off_shows() -> None:
    assert not is_hidden("off")


def test_hidden_keeps_when_but_not_where() -> None:
    data = {
        "destination": "Cafe",
        "distance": 4.0,
        "route": [(10.1, 20.1)],
        "home": False,
        "minutes": 5,
    }
    assert redact(data, True) == {"minutes": 5}
    assert redact(data, False) == data


def test_an_event_still_fires_while_hidden() -> None:
    event = DriveEvent("arriving", {"threshold": 5, "minutes": 5.0, "home": True})
    assert redact_event(event, True) == DriveEvent(
        "arriving", {"threshold": 5, "minutes": 5.0}
    )


def test_destination_events_carry_nothing_placing_it() -> None:
    event = DriveEvent("destination_set", {"destination": "Cafe", "home": False})
    assert redact_event(event, True).data == {}


def test_distance_steps() -> None:
    assert coarse_distance(None) is None
    assert coarse_distance(3.2) == 3.0
    assert coarse_distance(3.3) == 3.5
    assert coarse_distance(47.0) == 45.0


def test_minutes_round() -> None:
    assert coarse_minutes(None) is None
    assert coarse_minutes(4.6) == 5

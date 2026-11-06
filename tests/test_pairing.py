"""Replay destination updates through the name/coordinates pairing.

The first scenario follows a real drive whose last leg brought a name and never
its coordinates. Names and positions here are invented: fixtures in this repo
must never hold a real home or a real destination.
"""
from __future__ import annotations

import datetime as dt

import pytest
from tesla_drive_tracker_isolated.pairing import DestinationPairing

HOME = (10.1, 20.1)
CAFE = (10.2, 20.2)
BAKERY = (10.3, 20.3)
OTHER = (10.4, 20.4)


def at(hms: str) -> float:
    return dt.datetime.fromisoformat(f"2026-01-15T{hms}").timestamp()


# Each step: (time, tracker state, position, hidden, status, expected pin)
SCENARIOS = {
    "recorded drive": [
        ("20:56:09", "home", HOME, False, "none", None),
        # name first, coordinates 1 s later
        ("21:14:03", "Cafe", HOME, False, "unpaired", None),
        ("21:14:04", "Cafe", CAFE, False, "paired", CAFE),
        # the next stop's name arrives carrying the last stop's coordinates
        ("21:19:10", "Bakery", CAFE, False, "unpaired", None),
        ("21:19:10.5", "Bakery", BAKERY, False, "paired", BAKERY),
        # name cleared, then Cafe again with no new coordinates
        ("21:29:03", "not_home", BAKERY, False, "none", None),
        ("21:29:06", "Cafe", BAKERY, False, "paired", CAFE),
    ],
    "coordinates before name": [
        ("10:00:00", "home", HOME, False, "none", None),
        ("10:00:01", "home", HOME, False, "none", None),
        ("10:05:00", "Cafe", CAFE, False, "paired", CAFE),
        # new coordinates arrive while the old name is still current...
        ("10:20:00", "Cafe", BAKERY, False, "paired", BAKERY),
        # ...and the name follows 2 s later: the pair moves to Bakery
        ("10:20:02", "Bakery", BAKERY, False, "paired", BAKERY),
        # Cafe's mispairing was dropped, so no pin rather than Bakery's
        ("10:40:00", "Cafe", BAKERY, False, "unpaired", None),
    ],
    "unknown name with stale coordinates": [
        ("10:00:00", "Cafe", CAFE, False, "unpaired", None),  # first run
        ("10:00:05", "Cafe", CAFE, False, "unpaired", None),
        ("10:10:00", "Market", CAFE, False, "unpaired", None),
        ("10:10:01", "Market", OTHER, False, "paired", OTHER),
    ],
    "pairs expire": [
        ("08:00:00", "home", HOME, False, "none", None),
        ("08:00:01", "Cafe", CAFE, False, "paired", CAFE),
        ("08:30:00", "Market", OTHER, False, "paired", OTHER),
        ("21:00:01", "Cafe", OTHER, False, "unpaired", None),  # 13 h later
    ],
    "hiding empties the memory": [
        ("10:00:00", "home", HOME, False, "none", None),
        ("10:00:01", "Cafe", CAFE, False, "paired", CAFE),
        ("10:01:00", "Cafe", CAFE, True, "hidden", None),
        # nothing is remembered, and the coordinates are untrusted until they
        # change
        ("10:02:00", "Cafe", CAFE, False, "unpaired", None),
        ("10:03:00", "Market", OTHER, False, "paired", OTHER),
    ],
}


@pytest.mark.parametrize("title", SCENARIOS)
def test_scenario(title: str) -> None:
    pairing = DestinationPairing()
    for hms, state, position, hidden, status, pin in SCENARIOS[title]:
        fix = pairing.update(state, *position, at(hms), hidden=hidden)
        got = (fix.latitude, fix.longitude) if fix.latitude is not None else None
        assert (fix.status, got) == (status, pin), f"{title} at {hms}"


def test_memory_survives_a_restart() -> None:
    pairing = DestinationPairing()
    pairing.update("home", *HOME, at("10:00:00"))
    pairing.update("Cafe", *CAFE, at("10:00:01"))
    restored = DestinationPairing.from_dict(pairing.as_dict())
    fix = restored.update("Cafe", *CAFE, at("10:05:00"))
    assert (fix.status, fix.latitude) == ("paired", CAFE[0])


def test_no_position_is_not_a_position() -> None:
    pairing = DestinationPairing()
    pairing.update("home", *HOME, at("10:00:00"))
    fix = pairing.update("Cafe", None, None, at("10:00:01"))
    assert fix.status == "unpaired"
    assert fix.latitude is None

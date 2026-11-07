"""The path driven on the current trip."""
from __future__ import annotations

from tesla_drive_tracker_isolated.trail import MAX_POINTS, Trail


def test_a_stationary_car_adds_nothing() -> None:
    trail = Trail()
    assert trail.add(10.0, 20.0, 1)
    assert not trail.add(10.00001, 20.00001, 2)
    assert trail.points == [(10.0, 20.0, 1)]


def test_a_moving_car_adds_points() -> None:
    trail = Trail()
    trail.add(10.0, 20.0, 1)
    assert trail.add(10.001, 20.0, 2)
    assert len(trail.points) == 2


def test_a_full_trail_thins_its_oldest_half() -> None:
    trail = Trail()
    for index in range(MAX_POINTS + 1):
        trail.add(10 + index / 1000, 20.0, index)
    assert len(trail.points) < MAX_POINTS
    assert trail.points[0] == (10.0, 20.0, 0)
    assert trail.points[-1] == (10 + MAX_POINTS / 1000, 20.0, MAX_POINTS)


def test_length_needs_two_points() -> None:
    trail = Trail()
    assert trail.length_km is None
    trail.add(10.0, 20.0, 1)
    assert trail.length_km is None


def test_length_adds_up_and_clears() -> None:
    trail = Trail()
    trail.add(10.0, 20.0, 1)
    trail.add(10.01, 20.0, 2)
    trail.add(10.02, 20.0, 3)
    assert round(trail.length_km, 2) == 2.22
    trail.clear()
    assert trail.length_km is None


def test_length_survives_a_restart() -> None:
    trail = Trail()
    trail.add(10.0, 20.0, 1)
    trail.add(10.01, 20.0, 2)
    assert Trail(list(trail.points)).length_km == trail.length_km


def test_thinning_keeps_the_length() -> None:
    trail = Trail()
    for index in range(MAX_POINTS + 1):
        trail.add(10 + index / 1000, 20.0, index)
    assert round(trail.length_km) == round(MAX_POINTS * 0.1112)

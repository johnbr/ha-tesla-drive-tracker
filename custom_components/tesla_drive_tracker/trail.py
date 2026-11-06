"""The path the car has driven on the current trip.

Every fix would be thousands of points on a long drive, so a point is kept only
once the car has moved, and the oldest half is thinned when the trail fills. The
trail is shown, not measured, so losing detail in old points costs nothing.

This module imports nothing from Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .route_line import distance_km

MIN_STEP_KM = 0.025
MAX_POINTS = 3000


@dataclass(slots=True)
class Trail:
    """Points as ``(latitude, longitude, timestamp)``, oldest first."""

    points: list[tuple[float, float, float]] = field(default_factory=list)

    def add(self, latitude: float, longitude: float, now: float) -> bool:
        """Keep a point if the car has moved, returning whether it was kept."""
        point = (latitude, longitude)
        if self.points and distance_km(self.points[-1][:2], point) < MIN_STEP_KM:
            return False
        self.points.append((latitude, longitude, now))
        if len(self.points) > MAX_POINTS:
            half = len(self.points) // 2
            self.points = self.points[:half:2] + self.points[half:]
        return True

    def clear(self) -> None:
        """Start again for a new trip."""
        self.points = []

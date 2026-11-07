"""The path the car has driven on the current trip.

Every fix would be thousands of points on a long drive, so a point is kept only
once the car has moved, and the oldest half is thinned when the trail fills. The
length is added up as points arrive, so thinning doesn't shorten it until a restart
measures what is left, and a road thinned to every other point is nearly as long.

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
    _km: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._km = sum(
            distance_km(start[:2], end[:2])
            for start, end in zip(self.points, self.points[1:], strict=False)
        )

    @property
    def length_km(self) -> float | None:
        """How far the trail runs, or ``None`` before it has a point."""
        return self._km if self.points else None

    def add(self, latitude: float, longitude: float, now: float) -> bool:
        """Keep a point if the car has moved, returning whether it was kept."""
        point = (latitude, longitude)
        step = distance_km(self.points[-1][:2], point) if self.points else 0.0
        if self.points and step < MIN_STEP_KM:
            return False
        self._km += step
        self.points.append((latitude, longitude, now))
        if len(self.points) > MAX_POINTS:
            half = len(self.points) // 2
            self.points = self.points[:half:2] + self.points[half:]
        return True

    def clear(self) -> None:
        """Start again for a new trip."""
        self.points = []
        self._km = 0.0

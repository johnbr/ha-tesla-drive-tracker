"""Pair a navigation destination's name with the coordinates that belong to it.

Fleet Telemetry sends DestinationName and DestinationLocation as two signals,
each only when it changes, and the location one can simply never come. A route
set after a stream drop can arrive as a bare name while the tracker still holds
the previous stop's position, which would draw the destination where the car
already is.

So coordinates belong to the name that was current when they arrived, or to one
that arrives within ``FRESH_SECONDS`` after them, since the order inside one
update isn't guaranteed. A name that turns up without new coordinates gets the
coordinates last paired with that same name, and if there are none it gets no
position at all: no pin beats a wrong pin.

This module imports nothing from Home Assistant, so a recorded drive can be
replayed through it directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

FRESH_SECONDS = 5
MAX_AGE_SECONDS = 12 * 3600
MAX_PAIRS = 8

STATUS_NONE = "none"
STATUS_PAIRED = "paired"
STATUS_UNPAIRED = "unpaired"
STATUS_HIDDEN = "hidden"

# A tracker with no destination name falls back to a zone verdict. Those are
# lowercase; a destination really named "Home" keeps its capital and is a name.
NOT_A_NAME = frozenset({"unknown", "unavailable", "none", "", "not_home", "home"})


@dataclass(frozen=True, slots=True)
class Pair:
    """One name with the coordinates that arrived for it."""

    name: str
    latitude: float
    longitude: float
    timestamp: float


@dataclass(frozen=True, slots=True)
class DestinationFix:
    """What may be shown for the current destination."""

    status: str
    name: str = ""
    latitude: float | None = None
    longitude: float | None = None


@dataclass(slots=True)
class DestinationPairing:
    """Remembers which coordinates arrived with which name.

    ``update`` is called with the tracker's current reading each time it
    changes, and ``as_dict``/``from_dict`` carry the memory across a restart.
    """

    status: str = STATUS_HIDDEN
    raw_latitude: float = 0
    raw_longitude: float = 0
    raw_timestamp: float = 0
    raw_name: str = ""
    pairs: list[Pair] = field(default_factory=list)

    def update(
        self,
        state: str | None,
        latitude: float | None,
        longitude: float | None,
        now: float,
        *,
        hidden: bool = False,
    ) -> DestinationFix:
        """Take one tracker reading and return the fix for it.

        While ``hidden`` everything is forgotten, and the first reading after
        un-hiding is untrusted because it may be stale.
        """
        if hidden:
            self._forget()
            return DestinationFix(STATUS_HIDDEN)

        name = "" if state is None or state in NOT_A_NAME else state
        has_position = latitude is not None and longitude is not None
        first_reading = self.status == STATUS_HIDDEN
        changed = (
            not first_reading
            and has_position
            and (latitude != self.raw_latitude or longitude != self.raw_longitude)
        )

        if first_reading:
            # Adopt the coordinates as a baseline and trust them for nothing:
            # a raw timestamp of 0 is never fresh.
            self.raw_latitude = latitude if has_position else 0
            self.raw_longitude = longitude if has_position else 0
            self.raw_timestamp = 0
            self.raw_name = ""
        elif changed:
            self.raw_latitude = latitude
            self.raw_longitude = longitude
            self.raw_timestamp = now
            self.raw_name = name

        add = ""
        drop = ""
        if changed and name:
            add = name
        elif (
            name
            and name != self.raw_name
            and self.raw_timestamp > 0
            and now - self.raw_timestamp <= FRESH_SECONDS
        ):
            # The coordinates came a moment before this name, so they are its
            # and the pairing just made with the previous name was wrong.
            add = name
            drop = self.raw_name
            self.raw_name = name

        kept: list[Pair] = []
        if add:
            kept.append(
                Pair(add, self.raw_latitude, self.raw_longitude, self.raw_timestamp)
            )
        for pair in self.pairs:
            if len(kept) >= MAX_PAIRS:
                break
            expired = now - pair.timestamp >= MAX_AGE_SECONDS
            mispaired = bool(drop) and (
                pair.name == drop and pair.timestamp == self.raw_timestamp
            )
            if not expired and pair.name != add and not mispaired:
                kept.append(pair)
        self.pairs = kept

        if not name:
            self.status = STATUS_NONE
            return DestinationFix(STATUS_NONE)
        for pair in kept:
            if pair.name == name:
                self.status = STATUS_PAIRED
                return DestinationFix(
                    STATUS_PAIRED, name, pair.latitude, pair.longitude
                )
        self.status = STATUS_UNPAIRED
        return DestinationFix(STATUS_UNPAIRED, name)

    def _forget(self) -> None:
        self.status = STATUS_HIDDEN
        self.raw_latitude = 0
        self.raw_longitude = 0
        self.raw_timestamp = 0
        self.raw_name = ""
        self.pairs = []

    def as_dict(self) -> dict[str, Any]:
        """The memory as plain data for ``Store``."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DestinationPairing:
        """Rebuild the memory saved by ``as_dict``."""
        return cls(
            status=data.get("status", STATUS_HIDDEN),
            raw_latitude=data.get("raw_latitude", 0),
            raw_longitude=data.get("raw_longitude", 0),
            raw_timestamp=data.get("raw_timestamp", 0),
            raw_name=data.get("raw_name", ""),
            pairs=[Pair(**pair) for pair in data.get("pairs", [])],
        )

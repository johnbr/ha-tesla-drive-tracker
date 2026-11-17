"""Record what the card is sent, so a real drive can be replayed against a change.

Off until the owner turns it on. Each car gets a folder under
``tesla_drive_tracker/recordings`` in the configuration directory, holding a file a
day of JSON lines: a ``snapshot`` of the view when recording starts or a day
begins, then a ``delta`` of whatever changed, each stamped ``t`` in epoch seconds.
That is the card's own feed, already redacted, so a hidden destination never
reaches the disk.

A car reports up to three times a second, so lines are gathered and appended in
the executor every few seconds, gzipped. Files older than the days kept are
deleted once a day, whether or not recording is still on, and removing the car
deletes its folder.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import shutil
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER
from .view import DriveView, changed

SUFFIX = ".jsonl.gz"


def recordings_folder(hass: HomeAssistant, entry_id: str) -> Path:
    """Where one car's recordings go."""
    return Path(hass.config.path(DOMAIN, "recordings", entry_id))


async def async_remove_recordings(hass: HomeAssistant, entry_id: str) -> None:
    """Delete a removed car's recordings."""
    await hass.async_add_executor_job(
        shutil.rmtree, recordings_folder(hass, entry_id), True
    )


def expired(names: Iterable[str], today: date, days: int) -> list[str]:
    """The recordings among ``names`` dated ``days`` or more before today."""
    cutoff = today - timedelta(days=days)
    old = []
    for name in names:
        if not name.endswith(SUFFIX):
            continue
        try:
            day = date.fromisoformat(name.removesuffix(SUFFIX))
        except ValueError:
            continue
        if day <= cutoff:
            old.append(name)
    return old


class DriveRecording:
    """One car's feed, appended to a file a day."""

    def __init__(
        self, hass: HomeAssistant, folder: Path, *, on: bool, days: int
    ) -> None:
        self._hass = hass
        self._folder = folder
        self._on = on
        self._days = days
        self._sent: dict[str, Any] | None = None
        self._day: date | None = None
        self._lines: list[tuple[date, str]] = []
        self._pruned: date | None = None
        self._lock = asyncio.Lock()
        self._warned = False

    @callback
    def add(self, view: DriveView, now: float) -> None:
        """Gather a line for this view, if recording and anything changed."""
        if not self._on:
            return
        current = view.as_wire()
        day = dt_util.as_local(dt_util.utc_from_timestamp(now)).date()
        if self._sent is None or day != self._day:
            message = {"type": "snapshot", **current}
        else:
            message = {"type": "delta", **changed(self._sent, current)}
            if len(message) == 1:
                return
        self._sent = current
        self._day = day
        line = json.dumps({"t": round(now, 3), **message}, separators=(",", ":"))
        self._lines.append((day, line))

    async def async_flush(self, _now: datetime | None = None) -> None:
        """Append what has gathered, and once a day drop what is past keeping."""
        async with self._lock:
            lines, self._lines = self._lines, []
            today = dt_util.now().date()
            prune = today != self._pruned
            if not lines and not prune:
                return
            self._pruned = today
            try:
                await self._hass.async_add_executor_job(
                    self._write, lines, today if prune else None
                )
            except OSError as err:
                if not self._warned:
                    self._warned = True
                    LOGGER.warning("Couldn't record to %s: %s", self._folder, err)

    def _write(self, lines: list[tuple[date, str]], prune: date | None) -> None:
        by_day: dict[date, list[str]] = {}
        for day, line in lines:
            by_day.setdefault(day, []).append(f"{line}\n")
        if by_day:
            self._folder.mkdir(parents=True, exist_ok=True)
        for day, chunk in by_day.items():
            path = self._folder / f"{day.isoformat()}{SUFFIX}"
            with gzip.open(path, "at", encoding="utf-8") as file:
                file.writelines(chunk)
        if prune is not None and self._folder.is_dir():
            names = [path.name for path in self._folder.iterdir()]
            for name in expired(names, prune, self._days):
                (self._folder / name).unlink(missing_ok=True)

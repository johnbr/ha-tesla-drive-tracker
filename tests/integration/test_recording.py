"""Recording what the card is sent."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.tesla_drive_tracker.const import (
    CONF_RECORD_DAYS,
    CONF_RECORD_DRIVES,
    DOMAIN,
)

from .conftest import Car

PLACE = {"latitude": 10.0, "longitude": 20.0}


def folder(hass: HomeAssistant, car: Car) -> Path:
    return Path(hass.config.path(DOMAIN, "recordings", car.entry.entry_id))


def recorded(hass: HomeAssistant, car: Car) -> list[dict[str, Any]]:
    lines = []
    for path in sorted(folder(hass, car).glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as file:
            lines += [json.loads(line) for line in file]
    return lines


async def start_recording(
    hass: HomeAssistant, car: Car, tmp_path: Path, days: int = 7
) -> None:
    hass.config.config_dir = str(tmp_path)
    hass.config_entries.async_update_entry(
        car.entry, options={CONF_RECORD_DRIVES: True, CONF_RECORD_DAYS: days}
    )
    await car.start()


async def test_nothing_is_recorded_by_default(
    car: Car, hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.config_dir = str(tmp_path)
    await car.start()
    await car.report("speed", "40")
    await car.report("position", "not_home", PLACE)
    await car.stop()
    assert not (tmp_path / DOMAIN).exists()


async def test_a_snapshot_then_only_what_changed(
    car: Car, hass: HomeAssistant, tmp_path: Path
) -> None:
    await start_recording(hass, car, tmp_path)
    await car.report("speed", "40")
    await car.report("position", "not_home", PLACE)
    await car.stop()

    lines = recorded(hass, car)
    assert [line["type"] for line in lines] == ["snapshot", "delta", "delta"]
    assert lines[0]["state"] == "parked"
    assert lines[1]["speed"] == 40.0
    assert "battery" not in lines[1]
    assert lines[2]["latitude"] == 10.0
    assert lines[2]["t"] == dt_util.utcnow().timestamp()


async def test_a_hidden_destination_is_never_recorded(
    car: Car, hass: HomeAssistant, tmp_path: Path
) -> None:
    await start_recording(hass, car, tmp_path)
    await car.coordinator.async_set_hidden(True)
    await car.report("speed", "40")
    await car.report("destination", "Cafe", PLACE)
    await car.stop()

    assert recorded(hass, car)
    assert not any(line.get("destination") for line in recorded(hass, car))


async def test_old_recordings_are_deleted(
    car: Car, hass: HomeAssistant, tmp_path: Path
) -> None:
    today = dt_util.now().date()
    hass.config.config_dir = str(tmp_path)
    old = folder(hass, car)
    old.mkdir(parents=True)
    names = ("2025-12-01.jsonl.gz", f"{today.isoformat()}.jsonl.gz", "notes.txt")
    for name in names:
        (old / name).write_bytes(b"")

    await start_recording(hass, car, tmp_path, days=3)
    await car.stop()

    assert sorted(path.name for path in old.iterdir()) == [
        f"{today.isoformat()}.jsonl.gz",
        "notes.txt",
    ]


async def test_turning_recording_off_still_deletes_old_ones(
    car: Car, hass: HomeAssistant, tmp_path: Path
) -> None:
    hass.config.config_dir = str(tmp_path)
    old = folder(hass, car)
    old.mkdir(parents=True)
    (old / "2025-12-01.jsonl.gz").write_bytes(b"")
    await car.start()
    await car.stop()
    assert list(old.iterdir()) == []


async def test_removing_the_car_deletes_its_recordings(
    car: Car, hass: HomeAssistant, tmp_path: Path
) -> None:
    await start_recording(hass, car, tmp_path)
    await car.report("speed", "40")
    await car.stop()
    assert folder(hass, car).exists()
    await hass.config_entries.async_remove(car.entry.entry_id)
    await hass.async_block_till_done()
    assert not folder(hass, car).exists()

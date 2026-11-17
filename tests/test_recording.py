"""Which recordings are past keeping."""
from __future__ import annotations

from datetime import date

from custom_components.tesla_drive_tracker.recording import expired

TODAY = date(2026, 3, 10)


def test_days_kept_include_today() -> None:
    names = [f"2026-03-{day:02d}.jsonl.gz" for day in range(1, 11)]
    assert expired(names, TODAY, 7) == [
        "2026-03-01.jsonl.gz",
        "2026-03-02.jsonl.gz",
        "2026-03-03.jsonl.gz",
    ]


def test_only_recordings_are_touched() -> None:
    names = [
        "notes.txt",
        "2026-01-01.jsonl",
        "backup.jsonl.gz",
        "2026-01-01.jsonl.gz",
    ]
    assert expired(names, TODAY, 7) == ["2026-01-01.jsonl.gz"]

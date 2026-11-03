"""M7: which slot to run (mine.due_slot). Slots 08:30, 15:00, 21:00 Asia/Jerusalem."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from mine import due_slot

IL = ZoneInfo("Asia/Jerusalem")


def at(s):
    return datetime.fromisoformat(s).replace(tzinfo=IL)


@pytest.mark.parametrize("now,expected", [
    ("2026-11-01T08:30", "2026-11-01T08:30"),
    ("2026-11-01T08:31", "2026-11-01T08:30"),
    ("2026-11-01T14:00", "2026-11-01T08:30"),
    ("2026-11-01T15:00", "2026-11-01T15:00"),
    ("2026-11-01T22:10", "2026-11-01T21:00"),
    ("2026-11-02T01:00", "2026-11-01T21:00"),   # after midnight: yesterday's 21:00
])
def test_latest_slot(now, expected):
    assert due_slot(at(now), []) == expected


def test_done_slot_is_not_run_again():
    assert due_slot(at("2026-11-01T15:02"), ["2026-11-01T15:00"]) is None
    assert due_slot(at("2026-11-01T15:02"), ["2026-11-01T08:30"]) == "2026-11-01T15:00"


def test_too_late():
    assert due_slot(at("2026-11-02T07:00"), []) is None            # 10h after 21:00
    assert due_slot(at("2026-11-02T07:00"), [], max_late=timedelta(hours=12)) == "2026-11-01T21:00"


def test_utc_input():
    # 06:30 UTC on 1 Nov 2026 is 08:30 in Israel (winter time, UTC+2)
    assert due_slot(datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc), []) == "2026-11-01T08:30"


def test_summer_time():
    # 05:30 UTC on 1 Jul 2026 is 08:30 in Israel (summer time, UTC+3)
    assert due_slot(datetime(2026, 7, 1, 5, 30, tzinfo=timezone.utc), []) == "2026-07-01T08:30"
    assert due_slot(datetime(2026, 7, 1, 5, 29, tzinfo=timezone.utc), [], max_late=timedelta(hours=12)) == "2026-06-30T21:00"

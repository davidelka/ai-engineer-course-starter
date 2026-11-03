"""When to run: 08:30, 15:00 and 21:00, Asia/Jerusalem, every day.

The schedule lives in ONE place (SLOTS) and is rendered for each runner:

    python -m jobagent schedule --show       prints all of these
    APScheduler (local, long-running)        CronTrigger(hour, minute, timezone="Asia/Jerusalem")
    systemd timer (Linux laptop/server)      OnCalendar=*-*-* 08:30:00 Asia/Jerusalem
    EventBridge Scheduler (AWS)              cron(30 8 * * ? *) with schedule_expression_timezone

All three understand the time zone themselves, so daylight saving time (Israel moves the clock
twice a year) needs no code. A plain UTC cron would drift by an hour twice a year.

Idempotency: every run belongs to a SLOT KEY, the scheduled time it stands for
(e.g. "2026-11-01T15:00"), not the time it happened to start. A retry, a duplicate trigger or
a manual re-run of the same slot finds the slot already done and exits. A run that starts
late (a laptop that was asleep) works for the latest slot that is due.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

TZ_NAME = "Asia/Jerusalem"
TZ = ZoneInfo(TZ_NAME)
SLOTS: tuple[time, ...] = (time(8, 30), time(15, 0), time(21, 0))
MORNING = time(8, 30)


def slot_key(dt: datetime) -> str:
    """'2026-11-01T08:30' (local time, minutes precision)."""
    return dt.astimezone(TZ).strftime("%Y-%m-%dT%H:%M")


def slot_datetimes(day: datetime) -> list[datetime]:
    d = day.astimezone(TZ).date()
    return [datetime.combine(d, t, tzinfo=TZ) for t in SLOTS]


def latest_slot(now: datetime) -> datetime:
    """The most recent scheduled time <= now (yesterday 21:00 before 08:30)."""
    now = now.astimezone(TZ)
    for s in reversed(slot_datetimes(now)):
        if s <= now:
            return s
    return slot_datetimes(now - timedelta(days=1))[-1]


def previous_slot(slot: datetime) -> datetime:
    return latest_slot(slot.astimezone(TZ) - timedelta(minutes=1))


def due_slot(now: datetime, done: Iterable[str], *, max_late: timedelta = timedelta(hours=6)) -> Optional[str]:
    """Reference version of milestone 7. The slot key to run now, or None.

    - the candidate is latest_slot(now)
    - None if that slot is already in `done`
    - None if it is more than `max_late` in the past (the next slot will pick up the posts;
      catching up a 12-hour-old digest helps nobody)
    Missed older slots are never run separately: posts are filtered by "since the last done
    run", so the next run covers them.
    """
    s = latest_slot(now)
    key = slot_key(s)
    if key in set(done):
        return None
    if now.astimezone(TZ) - s > max_late:
        return None
    return key


def is_morning(key: str) -> bool:
    return datetime.fromisoformat(key).time() == MORNING


# ---------------------------------------------------------------- renderings
def eventbridge_expressions() -> list[dict]:
    """One EventBridge Scheduler schedule per slot (different minutes cannot share one cron)."""
    return [{"name": f"slot-{t.hour:02d}{t.minute:02d}", "expression": f"cron({t.minute} {t.hour} * * ? *)",
             "timezone": TZ_NAME} for t in SLOTS]


def systemd_oncalendar() -> list[str]:
    return [f"OnCalendar=*-*-* {t.hour:02d}:{t.minute:02d}:00 {TZ_NAME}" for t in SLOTS]


def apscheduler_jobs(func, *, misfire_grace_s: int = 3600):
    """Build a BlockingScheduler with one CronTrigger per slot. coalesce: several missed
    firings collapse into one; misfire_grace_time: a firing up to an hour late still runs."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    sched = BlockingScheduler(timezone=TZ_NAME)
    for t in SLOTS:
        sched.add_job(func, CronTrigger(hour=t.hour, minute=t.minute, timezone=TZ_NAME),
                      id=f"slot-{t.hour:02d}{t.minute:02d}", coalesce=True, max_instances=1,
                      misfire_grace_time=misfire_grace_s)
    return sched

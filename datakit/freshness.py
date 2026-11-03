"""Data freshness (lesson 8): is the data old enough to mislead?

Two places tell you when data was extracted:
- the provenance table: one row per table, written when the export job finished
- the _extracted_at column on every row

They can disagree. A nightly job that crashed half way leaves a fresh provenance
timestamp (if it is written first) next to rows from last week. So the age of a table
is the age of its OLDEST row, and the provenance row is a cross-check.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union


@dataclass
class Freshness:
    table: str
    extracted_at: str  # the oldest row's _extracted_at (ISO, UTC)
    age_hours: float
    max_age_hours: float
    stale: bool
    source_system: str = ""
    note: str = ""  # e.g. provenance disagrees with the rows

    def message(self) -> str:
        days = self.age_hours / 24
        state = "STALE" if self.stale else "fresh"
        return (f"{self.table}: {state}, extracted {self.extracted_at} ({days:.1f} days ago; "
                f"limit {self.max_age_hours / 24:.1f} days){' - ' + self.note if self.note else ''}")


def parse_ts(value: Union[str, datetime]) -> datetime:
    """ISO timestamp -> aware UTC datetime. 'Z' and naive values are treated as UTC."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def freshness_report(con: sqlite3.Connection, tables: list[str], now: Union[str, datetime],
                     max_age_hours: Union[float, dict[str, float]] = 24.0) -> list[Freshness]:
    """Reference implementation. Exercise 7 asks you to write your own in mine.py."""
    now_dt = parse_ts(now)
    out = []
    for t in tables:
        limit = max_age_hours.get(t, 24.0) if isinstance(max_age_hours, dict) else float(max_age_hours)
        oldest, newest = con.execute(f'SELECT MIN(_extracted_at), MAX(_extracted_at) FROM "{t}"').fetchone()
        prov = con.execute("SELECT source_system, extracted_at FROM provenance WHERE table_name = ?", (t,)).fetchone()
        source = prov[0] if prov else ""
        note = ""
        if oldest is None:
            out.append(Freshness(t, "", float("inf"), limit, True, source, "table is empty"))
            continue
        if oldest != newest:
            note = f"rows were extracted at different times ({oldest} .. {newest}): partial load?"
        elif prov and prov[1] != oldest:
            note = f"provenance says {prov[1]}, rows say {oldest}"
        age = (now_dt - parse_ts(oldest)).total_seconds() / 3600
        out.append(Freshness(t, oldest, round(age, 2), limit, age > limit, source, note))
    return out


def stale_warnings(report: list[Freshness]) -> list[str]:
    return [f.message() for f in report if f.stale or f.note]


def max_age_from_layer(layer) -> dict[str, float]:
    return {t: float(tab.freshness_hours) for t, tab in layer.tables.items()}


def default_now(layer=None) -> Optional[str]:
    """Acme's world has a fixed 'today' (2026-10-31); the extract ran 23:00Z that day.
    Labs default to the next morning so results are reproducible. Pass --now to change it."""
    return "2026-11-01T09:00:00Z"

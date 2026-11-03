"""Exercise 7: freshness_report in mine.py.

Small in-memory databases shaped like acme.db: data tables with an _extracted_at column,
and a provenance(table_name, source_system, extracted_at, ...) table. The real acme.db was
extracted at 2026-10-31T23:00:00Z.
"""

import math
import sqlite3

import pytest

from mine import freshness_report


def make_db(rows_by_table: dict, provenance: dict):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE provenance (table_name TEXT, source_system TEXT, source_object TEXT, "
                "extracted_at TEXT, extracted_by TEXT, row_count INTEGER, notes TEXT)")
    for t, stamps in rows_by_table.items():
        con.execute(f"CREATE TABLE {t} (id INTEGER, _source_system TEXT, _extracted_at TEXT)")
        con.executemany(f"INSERT INTO {t} VALUES (?, 'X', ?)", list(enumerate(stamps)))
    for t, (system, at) in provenance.items():
        con.execute("INSERT INTO provenance VALUES (?, ?, 'obj', ?, 'test', 0, '')", (t, system, at))
    return con


NOW = "2026-11-01T09:00:00Z"


def test_fresh_table():
    con = make_db({"tickets": ["2026-10-31T23:00:00Z"] * 3}, {"tickets": ("Zendesk API", "2026-10-31T23:00:00Z")})
    [f] = freshness_report(con, ["tickets"], NOW, 24)
    assert f.table == "tickets" and f.extracted_at == "2026-10-31T23:00:00Z"
    assert f.age_hours == 10.0 and f.max_age_hours == 24 and not f.stale
    assert f.source_system == "Zendesk API" and f.note == ""


def test_stale_table():
    con = make_db({"tickets": ["2026-10-29T09:00:00Z"]}, {"tickets": ("Zendesk API", "2026-10-29T09:00:00Z")})
    [f] = freshness_report(con, ["tickets"], NOW, 24)
    assert f.age_hours == 72.0 and f.stale


def test_partial_load_uses_oldest_row():
    con = make_db({"tickets": ["2026-10-31T23:00:00Z", "2026-10-27T23:00:00Z"]},
                  {"tickets": ("Zendesk API", "2026-10-31T23:00:00Z")})
    [f] = freshness_report(con, ["tickets"], NOW, 24)
    assert f.extracted_at == "2026-10-27T23:00:00Z"
    assert f.stale and "partial" in f.note.lower()


def test_provenance_disagrees():
    con = make_db({"teams": ["2026-10-30T23:00:00Z"]}, {"teams": ("HiBob", "2026-10-31T23:00:00Z")})
    [f] = freshness_report(con, ["teams"], NOW, 48)
    assert "provenance" in f.note.lower() and not f.stale


def test_per_table_limits_and_order():
    con = make_db({"systems": ["2026-10-28T09:00:00Z"], "tickets": ["2026-10-28T09:00:00Z"]}, {})
    out = freshness_report(con, ["tickets", "systems"], NOW, {"systems": 168, "tickets": 24})
    assert [f.table for f in out] == ["tickets", "systems"]
    assert out[0].stale and not out[1].stale
    assert out[0].source_system == ""


def test_empty_table():
    con = make_db({"customers": []}, {})
    [f] = freshness_report(con, ["customers"], NOW, 24)
    assert f.stale and math.isinf(f.age_hours) and f.note == "table is empty"


def test_now_can_be_naive_or_datetime():
    from datetime import datetime, timezone
    con = make_db({"tickets": ["2026-10-31T23:00:00Z"]}, {})
    a = freshness_report(con, ["tickets"], "2026-11-01T09:00:00", 24)[0]
    b = freshness_report(con, ["tickets"], datetime(2026, 11, 1, 9, tzinfo=timezone.utc), 24)[0]
    assert a.age_hours == b.age_hours == 10.0


def test_real_acme_db(con):
    out = freshness_report(con, ["tickets", "systems"], "2026-11-03T09:00:00Z", {"tickets": 24, "systems": 168})
    assert [f.stale for f in out] == [True, False]
    assert out[0].source_system == "Zendesk API"

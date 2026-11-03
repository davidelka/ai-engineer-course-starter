"""Provenance for data answers (lesson 8): which tables, which rows, extracted when.

Rule: provenance is computed by CODE from what actually ran, never written by the model.
The model may say "15 tickets"; the chips under the answer come from here:

    tickets  Zendesk API · extracted 2026-10-31T23:00Z · 15 rows: T-10094, T-10095, ...

supporting_rows() derives a "lineage query" from the executed SQL: same FROM, JOINs and
WHERE, but selecting the primary key of the main table. For an aggregate like COUNT(*)
those are exactly the rows that were counted. (HAVING is dropped, so for grouped
queries with HAVING it is a superset, and we say so.)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Optional

import sqlglot
from sqlglot import exp

from .freshness import Freshness, freshness_report

DIALECT = "sqlite"


@dataclass
class Source:
    table: str
    source_system: str
    source_object: str
    extracted_at: str
    row_count: int
    notes: str = ""


@dataclass
class RowLineage:
    table: str
    key: str
    ids: list[str] = field(default_factory=list)
    total: int = 0
    note: str = ""


def sources_for(con: sqlite3.Connection, tables: list[str]) -> list[Source]:
    out = []
    for t in tables:
        r = con.execute("SELECT source_system, source_object, extracted_at, row_count, notes "
                        "FROM provenance WHERE table_name = ?", (t,)).fetchone()
        if r:
            out.append(Source(t, *r))
        else:
            out.append(Source(t, "unknown", "", "", 0, "no provenance row"))
    return out


def _base_table(source: exp.Expression) -> Optional[str]:
    if isinstance(source, exp.Table):
        return source.name.lower()
    if isinstance(source, exp.Subquery) and isinstance(source.this, exp.Select):
        inner = source.this.args.get("from") or source.this.args.get("from_")
        if inner is not None and isinstance(inner.this, exp.Table):
            return inner.this.name.lower()
    return None


def supporting_rows(con: sqlite3.Connection, sql: str, primary_keys: dict[str, str],
                    max_ids: int = 50) -> Optional[RowLineage]:
    """Primary keys of the rows of the main (first FROM) table that the query used.
    Returns None when the query shape has no simple lineage (UNION, CTE, no FROM)."""
    try:
        tree = sqlglot.parse_one(sql, read=DIALECT)
    except sqlglot.errors.ParseError:
        return None
    if not isinstance(tree, exp.Select) or tree.args.get("with") or tree.args.get("with_"):
        return None
    frm = tree.args.get("from") or tree.args.get("from_")
    if frm is None:
        return None
    source = frm.this
    table = _base_table(source)
    if table is None or table not in primary_keys:
        return None
    alias = source.alias_or_name
    key = primary_keys[table]
    aggregated = bool(tree.args.get("group")) or any(True for _ in tree.find_all(exp.AggFunc))
    q = exp.select(exp.column(key, table=alias)).distinct()
    q.set("from", frm.copy()) if "from" in q.arg_types else q.set("from_", frm.copy())
    if tree.args.get("joins"):
        q.set("joins", [j.copy() for j in tree.args["joins"]])
    if tree.args.get("where"):
        q.set("where", tree.args["where"].copy())
    note = ""
    if not aggregated:  # a plain listing: the rows shown are the rows used
        if tree.args.get("order"):
            q.set("order", tree.args["order"].copy())
        if tree.args.get("limit"):
            q.set("limit", tree.args["limit"].copy())
    elif tree.args.get("having"):
        note = "HAVING ignored: these rows are a superset of what the final groups used"
    lineage_sql = q.sql(dialect=DIALECT)
    try:
        ids = [str(r[0]) for r in con.execute(lineage_sql).fetchall()]
    except sqlite3.Error as e:
        return RowLineage(table, key, [], 0, f"lineage query failed: {e}")
    return RowLineage(table, key, ids[:max_ids], len(ids), note)


@dataclass
class Provenance:
    sources: list[Source]
    freshness: list[Freshness]
    rows: Optional[RowLineage]

    def chips(self) -> list[str]:
        """One short line per source, for the UI under an answer."""
        out = []
        fresh = {f.table: f for f in self.freshness}
        for s in self.sources:
            f = fresh.get(s.table)
            state = "" if f is None else (" · STALE" if f.stale else "")
            at = f.extracted_at if f is not None and f.extracted_at else s.extracted_at  # oldest row wins
            line = f"{s.table} · {s.source_system} · extracted {at}{state}"
            if self.rows and self.rows.table == s.table:
                shown = ", ".join(self.rows.ids[:8]) + (" ..." if self.rows.total > 8 else "")
                line += f" · {self.rows.total} rows: {shown}" if self.rows.total else " · 0 rows"
            out.append(line)
        return out


def build_provenance(con: sqlite3.Connection, sql: str, tables: list[str], primary_keys: dict[str, str],
                     now: str, max_age_hours) -> Provenance:
    return Provenance(sources=sources_for(con, tables),
                      freshness=freshness_report(con, tables, now, max_age_hours),
                      rows=supporting_rows(con, sql, primary_keys))

"""Read-only execution (lesson 8). The database is the last line of defense, so it gets its
own guards, independent of the SQL guard:

- the file is opened with mode=ro (SQLite refuses every write) and PRAGMA query_only=ON
- a progress handler aborts any query that runs longer than timeout_ms
- fetchmany(max_rows + 1): never pull more rows than we will use, and know if we cut
- an optional authorizer denies sensitive columns at the database level (SQLITE_DENY),
  so even SQL that slipped past the guard cannot read them

In Postgres the same ideas are: a read-only role (GRANT SELECT only), statement_timeout,
column privileges, and row-level security policies.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Union

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "acme" / "corpus" / "structured" / "acme.db"


class QueryTimeout(Exception):
    pass


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool = False  # more rows existed than max_rows
    elapsed_ms: float = 0.0
    sql: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dicts(self) -> list[dict]:
        return [dict(zip(self.columns, r)) for r in self.rows]


def connect_ro(path: Union[str, Path, None] = None, deny_columns: Iterable[str] = ()) -> sqlite3.Connection:
    """Open the database read-only. deny_columns: {"table.column"} the connection must refuse."""
    p = Path(path) if path else DEFAULT_DB
    if not p.exists():
        raise FileNotFoundError(f"database not found: {p}")
    con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    con.execute("PRAGMA query_only = ON")
    denied = {c.lower() for c in deny_columns}
    if denied:
        def authorizer(action, arg1, arg2, dbname, source):
            if action == sqlite3.SQLITE_READ and arg1 and arg2 and f"{arg1.lower()}.{arg2.lower()}" in denied:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        con.set_authorizer(authorizer)
    return con


def _set_progress(con: sqlite3.Connection, handler, n: int) -> None:
    # The handler runs every n SQLite VM instructions; returning non-zero aborts the query.
    con.set_progress_handler(handler, n)


def run_query(con: sqlite3.Connection, sql: str, max_rows: int = 200, timeout_ms: int = 2000,
              params: Optional[dict[str, Any]] = None) -> QueryResult:
    """Execute one query with a time limit and a row cap."""
    deadline = time.perf_counter() + timeout_ms / 1000
    timed_out = {"v": False}

    def progress():
        if time.perf_counter() > deadline:
            timed_out["v"] = True
            return 1  # non-zero aborts the statement
        return 0

    _set_progress(con, progress, 10_000)
    t0 = time.perf_counter()
    try:
        cur = con.execute(sql, params or {})
        rows = cur.fetchmany(max_rows + 1)
        cols = [d[0] for d in (cur.description or [])]
    except sqlite3.OperationalError as e:
        if timed_out["v"] or "interrupted" in str(e):
            raise QueryTimeout(f"query exceeded {timeout_ms} ms and was aborted") from None
        raise
    finally:
        _set_progress(con, None, 10_000)
    truncated = len(rows) > max_rows
    return QueryResult(columns=cols, rows=[tuple(r) for r in rows[:max_rows]], truncated=truncated,
                       elapsed_ms=(time.perf_counter() - t0) * 1000, sql=sql)

"""The workflow's own durable records, next to toolkit's access_requests table (lesson 16).

The requests DB (default labs/16-workflows/results/requests.db) holds:
  access_requests   written by toolkit's create_access_request (the filing side effect)
  flow_audit        one row per status change: request_id, actor, from_status, to_status (SPEC-006 REQ-11)
  flow_outbox       notifications the workflow "sent" (a real system would email / Slack them)

Every write here is idempotent, because a node can run twice for the same step (retry,
crash and resume, approval gate re-run). Audit and outbox rows have deterministic ids and
are inserted with INSERT OR IGNORE; decisions are conditional updates
(UPDATE ... WHERE status = <expected>), the database version of SPEC-006 REQ-10.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from toolkit.acme import requests_connect

FLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS flow_audit (
  id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, request_id TEXT, actor TEXT NOT NULL,
  from_status TEXT, to_status TEXT NOT NULL, note TEXT, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS flow_outbox (
  id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, to_addr TEXT NOT NULL, subject TEXT NOT NULL,
  body TEXT NOT NULL, at TEXT NOT NULL);
"""


def connect(path: Path) -> sqlite3.Connection:
    con = requests_connect(Path(path))  # creates access_requests (toolkit's schema) if needed
    con.executescript(FLOW_SCHEMA)
    return con


def write_audit(path: Path, event: dict) -> bool:
    """Insert one audit event; False if an event with this id already exists."""
    con = connect(path)
    try:
        cur = con.execute("INSERT OR IGNORE INTO flow_audit VALUES (?,?,?,?,?,?,?,?)",
                          (event["id"], event["thread_id"], event.get("request_id"), event["actor"],
                           event.get("from_status"), event["to_status"], event.get("note"), event["at"]))
        con.commit()
        return cur.rowcount == 1
    finally:
        con.close()


def send(path: Path, msg: dict) -> bool:
    """Put one notification in the outbox; False if it was already sent (same id)."""
    con = connect(path)
    try:
        cur = con.execute("INSERT OR IGNORE INTO flow_outbox VALUES (?,?,?,?,?,?)",
                          (msg["id"], msg["thread_id"], msg["to"], msg["subject"], msg["body"], msg["at"]))
        con.commit()
        return cur.rowcount == 1
    finally:
        con.close()


def get_request(path: Path, request_id: str) -> Optional[dict]:
    con = connect(path)
    try:
        row = con.execute("SELECT * FROM access_requests WHERE id=?", (request_id,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def set_status(path: Path, request_id: str, *, expected: str, to: str, approver: Optional[str] = None,
               route: Optional[str] = None) -> str:
    """Move a request from `expected` to `to`. Returns:
       "updated"  the row was in `expected` and is now `to`
       "noop"     the row is already in `to` (this step ran before: a retry or a resume)
       "conflict" the row is in some other status (someone else decided it: REQ-10)
    """
    con = connect(path)
    try:
        sets, args = ["status=?"], [to]
        if approver is not None:
            sets.append("approver=?")
            args.append(approver)
        if route is not None:
            sets.append("route=?")
            args.append(route)
        cur = con.execute(f"UPDATE access_requests SET {', '.join(sets)} WHERE id=? AND status=?",
                          (*args, request_id, expected))
        con.commit()
        if cur.rowcount == 1:
            return "updated"
        row = con.execute("SELECT status FROM access_requests WHERE id=?", (request_id,)).fetchone()
        return "noop" if row and row["status"] == to else "conflict"
    finally:
        con.close()


def dump(path: Path, thread_id: Optional[str] = None) -> dict:
    """Everything the workflow wrote, for inspection scripts and tests."""
    con = connect(path)
    try:
        q = lambda sql, *a: [dict(r) for r in con.execute(sql, a)]  # noqa: E731
        if thread_id:
            audit = q("SELECT * FROM flow_audit WHERE thread_id=? ORDER BY rowid", thread_id)
            ids = sorted({a["request_id"] for a in audit if a["request_id"]})
            reqs = [r for i in ids for r in q("SELECT * FROM access_requests WHERE id=?", i)]
            outbox = q("SELECT * FROM flow_outbox WHERE thread_id=? ORDER BY rowid", thread_id)
        else:
            audit = q("SELECT * FROM flow_audit ORDER BY rowid")
            reqs = q("SELECT * FROM access_requests ORDER BY id")
            outbox = q("SELECT * FROM flow_outbox ORDER BY rowid")
        return {"access_requests": reqs, "audit": audit, "outbox": outbox}
    finally:
        con.close()


def pretty(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)

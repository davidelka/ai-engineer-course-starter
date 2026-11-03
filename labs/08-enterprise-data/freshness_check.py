"""Exercise 7: is the data fresh enough to answer from?

    python labs/08-enterprise-data/freshness_check.py                           # now = 2026-11-01T09:00Z
    python labs/08-enterprise-data/freshness_check.py --now 2026-11-03T09:00:00Z
    python labs/08-enterprise-data/freshness_check.py --simulate-partial        # a half-finished nightly load
    python labs/08-enterprise-data/freshness_check.py --reference

Freshness limits per table come from the semantic layer (freshness_hours):
  tickets 24h, customers 24h, access_grants 24h, employees 48h, teams 48h, systems 168h.
The extract in acme.db ran at 2026-10-31T23:00:00Z (see the provenance table).

--simulate-partial copies acme.db to results/acme_partial.db and makes the ticket load look
half-finished: the provenance row and half of the ticket rows get the new timestamp, the
other half keep a timestamp from 4 days earlier. Then it asks a question through the full
pipeline (offline replay) so you can see the warning attached to the answer.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3

import _lab
from _lab import RESULTS, make_llm, pick
from datakit import connect_ro, load_layer
from datakit.db import DEFAULT_DB
from datakit.freshness import max_age_from_layer
from datakit.text2sql import Settings, answer_question, format_answer


def make_partial_copy() -> str:
    RESULTS.mkdir(exist_ok=True)
    dst = RESULTS / "acme_partial.db"
    shutil.copyfile(DEFAULT_DB, dst)
    con = sqlite3.connect(dst)
    con.execute("UPDATE tickets SET _extracted_at = '2026-10-27T23:00:00Z' WHERE CAST(substr(id, 3) AS INTEGER) % 2 = 1")
    con.execute("UPDATE provenance SET extracted_at = '2026-10-31T23:00:00Z' WHERE table_name = 'tickets'")
    con.commit()
    con.close()
    return str(dst)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", default="2026-11-01T09:00:00Z")
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--simulate-partial", action="store_true")
    a = ap.parse_args()
    fresh, src = pick("freshness_report", a.reference)
    layer = load_layer()
    limits = max_age_from_layer(layer)
    db = make_partial_copy() if a.simulate_partial else None
    con = connect_ro(db)
    print(f"freshness_report: {src}   now: {a.now}   db: {db or DEFAULT_DB.name}\n")
    for f in fresh(con, list(layer.tables), a.now, limits):
        flag = "STALE" if f.stale else "ok   "
        print(f"{flag} {f.table:14} oldest row {f.extracted_at or '-':22} age {f.age_hours:7.1f}h  limit {f.max_age_hours:5.0f}h"
              f"  {f.source_system}")
        if f.note:
            print(f"      note: {f.note}")
    if a.simulate_partial:
        print("\nThe same question, answered from the partial copy:\n")
        llm, _ = make_llm(False, "")
        ans = answer_question(llm, "How many tickets are still open?", Settings(db_path=db, now=a.now, layer=layer))
        print(format_answer(ans))


if __name__ == "__main__":
    main()

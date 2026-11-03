"""Exercise 1: two kinds of sources, one company.

Prints what is in acme.db (tables, rows, where each table comes from and when it was
extracted), then puts four facts side by side: what the DATABASE says and what a DOCUMENT
says. Some agree, some disagree, and the reasons differ.

    python labs/08-enterprise-data/explore_data.py
    python labs/08-enterprise-data/explore_data.py --sql "SELECT plan, COUNT(*) FROM customers GROUP BY plan"
"""

from __future__ import annotations

import argparse
import re

import _lab  # noqa: F401  (paths)
from _lab import ROOT
from datakit import connect_ro, run_query

import sys
sys.path.insert(0, str(ROOT / "data" / "acme" / "corpus"))
import load  # noqa: E402  (the corpus loader)

FACTS = [
    {
        "title": "Who leads the Identity team?",
        "sql": "SELECT e.name AS lead, t.headcount FROM teams t JOIN employees e ON e.id = t.lead_id WHERE t.id = 'identity'",
        "doc": "co-org-chart", "pattern": r"Identity team:.*",
        "lesson": "Agree. The org chart and HiBob are maintained from the same source.",
    },
    {
        "title": "How many support tickets did the August 19 outage cause?",
        "sql": "SELECT COUNT(*) AS linked_tickets, SUM(priority = 'P1') AS p1 FROM tickets WHERE incident_id = 'INC-2026-08-19'",
        "doc": "eng-pm-2026-08-api", "pattern": r".*support tickets.*",
        "lesson": "Disagree, and both are 'right': the postmortem counts every ticket in Zendesk; "
                  "acme.db holds a 200-ticket extract (see the table description). Different scope, "
                  "not a contradiction. An answer must say which scope it uses.",
    },
    {
        "title": "First-response target for an Enterprise P1 ticket?",
        "sql": "SELECT DISTINCT sla_target_minutes FROM tickets WHERE priority = 'P1' AND customer_plan = 'enterprise'",
        "doc": "sup-escalation", "pattern": r"\| P1 \|.*",
        "lesson": "Agree: the column was computed from the policy. The policy is the source of truth; "
                  "the column is a copy that can drift if the policy changes and nobody recomputes it.",
    },
    {
        "title": "Which team owns flow-scheduler?",
        "sql": "SELECT s.name, s.owner_team FROM systems s WHERE s.name = 'flow-scheduler'",
        "doc": "eng-leads-sync-2026-05", "pattern": r".*Decision:.*flow-scheduler.*",
        "lesson": "Disagree: the May meeting notes record a 'decision' that was later postponed "
                  "(co-allhands-2026-07, eng-service-catalog). The register reflects the current state. "
                  "For 'who owns X now', the system of record beats old meeting notes.",
    },
]


def doc_line(doc_id: str, pattern: str) -> tuple[str, str]:
    d = load.get_doc(doc_id)
    m = re.search(pattern, d.text or "")
    return (m.group(0).strip() if m else "(no matching line)"), str(d.meta.get("effective_date"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", help="run your own read-only query and exit")
    a = ap.parse_args()
    con = connect_ro()
    if a.sql:
        r = run_query(con, a.sql)
        print(" | ".join(r.columns))
        for row in r.rows:
            print(" | ".join(str(v) for v in row))
        return

    print("== acme.db: tables, rows, provenance (data/acme/corpus/structured/acme.db)\n")
    for t, system, obj, at, n, notes in con.execute(
            "SELECT table_name, source_system, source_object, extracted_at, row_count, notes FROM provenance"):
        cols = [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')]
        print(f"- {t:14} {n:4} rows  from {system} ({obj}), extracted {at}")
        print(f"    columns: {', '.join(c for c in cols if not c.startswith('_'))}")
        print(f"    note: {notes}")

    print("\n== Two sources, one fact\n")
    for i, f in enumerate(FACTS, 1):
        r = run_query(con, f["sql"])
        line, eff = doc_line(f["doc"], f["pattern"])
        print(f"{i}. {f['title']}")
        print(f"   database : {dict(zip(r.columns, r.rows[0])) if r.rows else 'no rows'}")
        print(f"              SQL: {f['sql']}")
        print(f"   document : \"{line}\"")
        print(f"              ({f['doc']}, effective {eff})")
        print(f"   why      : {f['lesson']}\n")
    print("Your turn: write 3-5 lines on when you would answer from the database, when from a document,")
    print("and what an answer must say when the two disagree. Save it in results/ex1.md.")


if __name__ == "__main__":
    main()

"""Build data/data_questions.jsonl: questions the router should send to the DATABASE, with gold SQL.

Each row is both an eval example and an offline fixture for datakit's replay_llm:
    question, lang, roles (which document-roles may ask it; others should be refused by the
    data layer), gold_sql, columns, rows (computed here by running gold_sql on acme.db),
    plans  (the recorded "model reply" for the SQL plan: here the gold plan itself, so the
            offline path exercises guard, row policy, execution and provenance, not a model),
    answer (the recorded narration, written from the rows).

Offline, the text-to-SQL step is therefore exact by construction: it measures the plumbing.
The live run (MODE=live) asks Haiku for the plan and measures real execution accuracy.

    python data/make_data_questions.py        # rewrites data/data_questions.jsonl
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parents[2] / "data" / "acme" / "corpus" / "structured" / "acme.db"

ALL = ["employee", "engineering", "support", "hr", "finance", "security"]

QUESTIONS = [
    ("d01", "en", "How many open P1 tickets do we have right now?",
     "SELECT COUNT(*) AS open_p1 FROM tickets WHERE priority = 'P1' AND status IN ('open', 'pending')",
     ["tickets"], "'open' includes the pending status", "There are {0} open P1 tickets (status open or pending)."),
    ("d02", "en", "How many tickets are still open?",
     "SELECT COUNT(*) AS open_tickets FROM tickets WHERE status IN ('open', 'pending')",
     ["tickets"], "'open' includes the pending status", "{0} tickets are still open or pending."),
    ("d03", "en", "How many tickets are there for each priority?",
     "SELECT priority, COUNT(*) AS tickets FROM tickets GROUP BY priority ORDER BY priority",
     ["tickets"], None, "Tickets by priority: {rows}."),
    ("d04", "en", "What is our overall SLA breach rate?",
     "SELECT ROUND(1.0 * SUM(sla_breached) / COUNT(*), 4) AS sla_breach_rate FROM tickets WHERE sla_target_minutes IS NOT NULL",
     ["tickets"], "only tickets that have an SLA target", "The overall SLA breach rate is {0} (tickets with an SLA target)."),
    ("d05", "en", "How many customers are on each plan?",
     "SELECT plan, COUNT(*) AS customers FROM customers GROUP BY plan ORDER BY plan",
     ["customers"], None, "Customers by plan: {rows}."),
    ("d06", "en", "How many Red Folder customers are there?",
     "SELECT COUNT(*) AS red_folder_customers FROM customers WHERE red_folder = 1",
     ["customers"], None, "There are {0} Red Folder customers."),
    ("d07", "en", "How many employees work in each office?",
     "SELECT location, COUNT(*) AS employees FROM employees GROUP BY location ORDER BY location",
     ["employees"], None, "Employees by office: {rows}."),
    ("d08", "en", "How many access grants went through security review?",
     "SELECT COUNT(*) AS grants FROM access_grants WHERE route = 'needs_security'",
     ["access_grants"], "security review = route needs_security", "{0} access grants went through the needs_security route."),
    ("d09", "en", "How many tickets are linked to the August outage, and how many of them breached the SLA?",
     "SELECT COUNT(*) AS tickets, SUM(sla_breached) AS breached FROM tickets WHERE incident_id = 'INC-2026-08-19'",
     ["tickets"], "the August outage is incident INC-2026-08-19", "{0} tickets are linked to the August outage, and {1} of them breached the SLA."),
    ("d10", "en", "How many tickets were created in August 2026?",
     "SELECT COUNT(*) AS tickets FROM tickets WHERE created_at >= '2026-08-01' AND created_at < '2026-09-01'",
     ["tickets"], None, "{0} tickets were created in August 2026."),
    ("d11", "he", "כמה קריאות P1 פתוחות יש כרגע?",
     "SELECT COUNT(*) AS open_p1 FROM tickets WHERE priority = 'P1' AND status IN ('open', 'pending')",
     ["tickets"], "'open' includes the pending status", "יש כרגע {0} קריאות P1 פתוחות (בסטטוס open או pending)."),
    ("d12", "he", "כמה לקוחות יש בכל תוכנית?",
     "SELECT plan, COUNT(*) AS customers FROM customers GROUP BY plan ORDER BY plan",
     ["customers"], None, "מספר הלקוחות לפי תוכנית: {rows}."),
    ("d13", "he", "כמה עובדים יש בכל משרד?",
     "SELECT location, COUNT(*) AS employees FROM employees GROUP BY location ORDER BY location",
     ["employees"], None, "מספר העובדים לפי משרד: {rows}."),
    ("d14", "en", "List the tier 1 systems.",
     "SELECT name FROM systems WHERE tier = 1 ORDER BY name",
     ["systems"], None, "The tier 1 systems are: {rows}."),
    ("d15", "en", "How many access grants expire in November 2026?",
     "SELECT COUNT(*) AS grants FROM access_grants WHERE expires_at >= '2026-11-01' AND expires_at <= '2026-11-30'",
     ["access_grants"], None, "{0} access grants expire in November 2026."),
    ("d16", "en", "What is the total ARR of the Red Folder customers?",
     "SELECT SUM(arr_usd) AS red_folder_arr FROM customers WHERE red_folder = 1",
     ["customers"], "ARR in USD (arr_usd)", "The total ARR of the Red Folder customers is ${0:,} (USD)."),
]

# Which document-roles may get an answer (the datakit role behind each one decides; see
# acmeqa/router.py DATA_ROLE). arr_usd is a financial column: only finance and support leads see it.
# support_lead may read tickets, customers, teams, systems; finance only customers, tickets, teams.
ROLES = {
    "d07": ["employee", "engineering", "hr", "security"],
    "d08": ["employee", "engineering", "hr", "security"],
    "d13": ["employee", "engineering", "hr", "security"],
    "d14": ["employee", "engineering", "support", "hr", "security"],
    "d15": ["employee", "engineering", "hr", "security"],
    "d16": ["support", "finance"],
}


def fmt_rows(rows: list[tuple]) -> str:
    return ", ".join(" ".join(str(v) for v in r) if len(r) > 1 else str(r[0]) for r in rows)


def main() -> None:
    con = sqlite3.connect(DB)
    out = []
    for qid, lang, q, sql, tables, assumption, template in QUESTIONS:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [list(r) for r in cur.fetchall()]
        plan = {"assumptions": [assumption] if assumption else [], "tables_used": tables, "answerable": True,
                "sql": sql, "clarification": None}
        answer = template.format(*rows[0], rows=fmt_rows([tuple(r) for r in rows])) if rows else "No rows."
        out.append({"id": qid, "lang": lang, "question": q, "roles": ROLES.get(qid, ALL), "gold_sql": sql,
                    "columns": cols, "rows": rows, "plans": [json.dumps(plan, ensure_ascii=False)],
                    "answer": answer, "note": "synthetic recorded reply (the gold plan)"})
    path = HERE / "data_questions.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"wrote {len(out)} questions to {path}")


if __name__ == "__main__":
    main()

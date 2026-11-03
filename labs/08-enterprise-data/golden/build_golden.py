"""Build golden/business_questions.jsonl: business questions with a golden SQL query and the
golden RESULT, computed by running that SQL on acme.db (read-only).

    python labs/08-enterprise-data/golden/build_golden.py          # rebuild
    python labs/08-enterprise-data/golden/build_golden.py --check  # verify the file is in sync

Each line:
  id, question, category, role, user (row-policy parameters), expect ("rows" | "refuse"),
  gold_sql, ordered (does row order matter), columns, rows, note

expect = "refuse": the right behavior is NOT to answer from the database (the answer lives in
documents, the data does not exist, or the role may not see it). The eval counts it correct
when the pipeline ends as not_answerable, or rejected by the guard after its repair turn.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from datakit import apply_row_policy, connect_ro, load_layer, run_query  # noqa: E402

OUT = HERE / "business_questions.jsonl"

Q = [
    # ---- lookup: one table or one join, one answer
    ("q01", "Which team owns auth-service, and who leads that team?", "lookup", "analyst", {},
     "SELECT t.name AS team, e.name AS lead FROM systems s JOIN teams t ON t.id = s.owner_team "
     "JOIN employees e ON e.id = t.lead_id WHERE s.name = 'auth-service'", False, ""),
    ("q02", "In which office is the Engine team based?", "lookup", "analyst", {},
     "SELECT main_location FROM teams WHERE id = 'engine'", False, ""),
    ("q03", "List the tier 1 systems.", "lookup", "analyst", {},
     "SELECT name FROM systems WHERE tier = 1", False, ""),
    ("q04", "Which approved SaaS tools does the IT team own?", "lookup", "analyst", {},
     "SELECT name FROM systems WHERE approved_tool = 1 AND owner_team = 'it'", False, ""),
    # ---- aggregates
    ("q05", "How many employees work in each office?", "aggregate", "analyst", {},
     "SELECT location, COUNT(*) AS employees FROM employees GROUP BY location", False, ""),
    ("q06", "How many tickets are there for each priority?", "aggregate", "analyst", {},
     "SELECT priority, COUNT(*) AS tickets FROM tickets GROUP BY priority", False, ""),
    ("q07", "How many access grants went through security review?", "aggregate", "analyst", {},
     "SELECT COUNT(*) AS grants FROM access_grants WHERE route = 'needs_security'", False,
     "business term: security review = route needs_security"),
    ("q08", "How many customers are on each plan?", "aggregate", "analyst", {},
     "SELECT plan, COUNT(*) AS customers FROM customers GROUP BY plan", False, ""),
    # ---- metrics and business terms from the semantic layer
    ("q09", "What is our overall SLA breach rate?", "metric", "analyst", {},
     "SELECT ROUND(1.0 * SUM(sla_breached) / COUNT(*), 4) AS sla_breach_rate FROM tickets "
     "WHERE sla_target_minutes IS NOT NULL", False,
     "metric definition: starter tickets have no target and are excluded (27/174, not 27/200)"),
    ("q10", "What is the SLA breach rate for each customer plan?", "metric", "analyst", {},
     "SELECT customer_plan, ROUND(1.0 * SUM(sla_breached) / COUNT(*), 4) AS sla_breach_rate FROM tickets "
     "WHERE sla_target_minutes IS NOT NULL GROUP BY customer_plan", False, "starter has no target: no row"),
    ("q11", "How many tickets are still open?", "metric", "analyst", {},
     "SELECT COUNT(*) AS open_tickets FROM tickets WHERE status IN ('open', 'pending')", False,
     "business term: open = open or pending"),
    ("q12", "How many open P1 tickets do we have right now?", "metric", "analyst", {},
     "SELECT COUNT(*) AS open_p1 FROM tickets WHERE priority = 'P1' AND status IN ('open', 'pending')", False,
     "business term: open = open or pending (status = 'open' alone gives 1)"),
    ("q13", "How many Red Folder customers are there?", "metric", "analyst", {},
     "SELECT COUNT(*) AS red_folder_customers FROM customers WHERE red_folder = 1", False, ""),
    # ---- joins along the declared join paths
    ("q14", "How many tickets came from customers who are in the Red Folder?", "join", "analyst", {},
     "SELECT COUNT(*) AS tickets FROM tickets t JOIN customers c ON c.id = t.customer_id WHERE c.red_folder = 1",
     False, ""),
    ("q15", "How many tier 1 systems does each team own? Use team names.", "join", "analyst", {},
     "SELECT t.name AS team, COUNT(*) AS tier1_systems FROM systems s JOIN teams t ON t.id = s.owner_team "
     "WHERE s.tier = 1 GROUP BY t.name", False, "asks for names, not team ids"),
    ("q16", "List the people on the Identity team with their job titles.", "join", "analyst", {},
     "SELECT e.name, e.title FROM employees e WHERE e.team = 'identity'", False, ""),
    ("q17", "Who approved the most access grants, not counting automatic approvals? Give the name and the count.",
     "join", "analyst", {},
     "SELECT e.name, COUNT(*) AS approvals FROM access_grants g JOIN employees e ON e.id = g.approved_by "
     "WHERE g.approved_by <> 'system:auto' GROUP BY e.name ORDER BY approvals DESC LIMIT 1", True, ""),
    # ---- time
    ("q18", "How many tickets were created in August 2026?", "time", "analyst", {},
     "SELECT COUNT(*) AS tickets FROM tickets WHERE created_at >= '2026-08-01' AND created_at < '2026-09-01'",
     False, "created_at has a time part: BETWEEN '2026-08-01' AND '2026-08-31' would miss Aug 31 after midnight"),
    ("q19", "How many tickets were created in each month of 2026? Show the month as YYYY-MM.", "time", "analyst", {},
     "SELECT substr(created_at, 1, 7) AS month, COUNT(*) AS tickets FROM tickets "
     "WHERE created_at LIKE '2026-%' GROUP BY month ORDER BY month", True, ""),
    ("q20", "How many access grants expire in November 2026?", "time", "analyst", {},
     "SELECT COUNT(*) AS grants FROM access_grants WHERE expires_at >= '2026-11-01' AND expires_at <= '2026-11-30'",
     False, ""),
    # ---- incidents (the structured side of multi-source questions)
    ("q21", "How many tickets are linked to the August outage, and how many of them breached the SLA?",
     "incident", "analyst", {},
     "SELECT COUNT(*) AS tickets, SUM(sla_breached) AS breached FROM tickets WHERE incident_id = 'INC-2026-08-19'",
     False, "the postmortem says 203 tickets: this table is a 200-ticket extract, a different scope"),
    ("q22", "Which customers opened tickets linked to the June billing incident?", "incident", "analyst", {},
     "SELECT DISTINCT c.name FROM tickets t JOIN customers c ON c.id = t.customer_id "
     "WHERE t.incident_id = 'INC-2026-06-03'", False, ""),
    # ---- roles
    ("q23", "What is the total ARR of the Red Folder accounts?", "role", "finance", {},
     "SELECT SUM(arr_usd) AS red_folder_arr FROM customers WHERE red_folder = 1", False,
     "financial column: finance may see it"),
    ("q24", "List the people on my team with their email addresses.", "role", "manager", {"team": "core-api"},
     "SELECT name, email FROM employees", False,
     "row policy: the manager of core-api sees only core-api rows; the SQL needs no team filter"),
    # ---- should NOT be answered from the database
    ("q25", "What are the email addresses of the Identity team?", "refuse", "analyst", {},
     "", False, "PII: analyst may not see employees.email"),
    ("q26", "Why did the August outage happen?", "refuse", "analyst", {},
     "", False, "the reason is in the postmortem document, not in any table"),
    ("q27", "What was our customer churn rate in 2026?", "refuse", "analyst", {},
     "", False, "no churn data exists in these tables"),
]


def build() -> list[dict]:
    layer = load_layer()
    con = connect_ro()
    out = []
    for qid, question, cat, role, user, sql, ordered, note in Q:
        row = {"id": qid, "question": question, "category": cat, "role": role, "user": user,
               "expect": "refuse" if not sql else "rows", "gold_sql": sql, "ordered": ordered,
               "columns": [], "rows": [], "note": note}
        if sql:
            rp = layer.role(role).row_policy
            run_sql = apply_row_policy(sql, rp, user) if rp else sql
            res = run_query(con, run_sql, max_rows=1000)
            row["columns"], row["rows"] = res.columns, [list(r) for r in res.rows]
        out.append(row)
    con.close()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the file differs from a fresh build")
    a = ap.parse_args()
    rows = build()
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    if a.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("in sync" if same else "OUT OF SYNC: run without --check to rebuild")
        raise SystemExit(0 if same else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {len(rows)} questions to {OUT.relative_to(ROOT)}")
    for r in rows:
        shown = r["rows"][:3]
        print(f"  {r['id']} [{r['category']}/{r['role']}] {r['question'][:60]:60} -> {shown if r['expect'] == 'rows' else 'REFUSE'}")


if __name__ == "__main__":
    main()

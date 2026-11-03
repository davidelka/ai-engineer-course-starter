"""Exercise 6: row-level security. The same SQL, run as different users.

    python labs/08-enterprise-data/rls_demo.py                 # YOUR apply_row_policy (falls back to the reference)
    python labs/08-enterprise-data/rls_demo.py --reference
    python labs/08-enterprise-data/rls_demo.py --sql "SELECT COUNT(*) FROM access_grants" --team identity

Users (roles from datakit/data/acme_semantic.yaml):
  analyst           all tables, no PII
  manager core-api  PII allowed, row policy: employees.team = 'core-api' and their access_grants
  manager identity  same, for the Identity team
  people_ops        PII allowed, no row policy

The guard runs first (on what the model would write), then the row policy rewrites the SQL.
"""

from __future__ import annotations

import argparse

import _lab
from _lab import pick
from datakit import connect_ro, load_layer, policy_from_layer, run_query

USERS = [("analyst", {}), ("manager", {"team": "core-api"}), ("manager", {"team": "identity"}), ("people_ops", {})]
QUERIES = [
    "SELECT name, email FROM employees",
    "SELECT COUNT(*) AS grants FROM access_grants WHERE route = 'needs_security'",
    "SELECT e.name, g.system, g.level FROM access_grants g JOIN employees e ON e.id = g.employee_id WHERE g.level = 'admin'",
    "SELECT name, email FROM employees WHERE team = 'identity'",
    "SELECT COUNT(*) AS people FROM (SELECT id FROM employees)",
    "SELECT COUNT(*) AS tickets FROM tickets",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--sql")
    ap.add_argument("--team", default="core-api", help="team for --sql as a manager")
    a = ap.parse_args()
    rls, src = pick("apply_row_policy", a.reference)
    guard, _ = pick("guard_sql", True)
    layer = load_layer()
    policy = policy_from_layer(layer)
    con = connect_ro()
    print(f"row policy: {src}\n")
    queries = [a.sql] if a.sql else QUERIES
    users = [("manager", {"team": a.team}), ("analyst", {})] if a.sql else USERS
    for sql in queries:
        print("=" * 100 + f"\n{sql}")
        for role, user in users:
            who = role + (f" ({user['team']})" if user else "")
            g = guard(sql, policy, role)
            if not g.ok:
                print(f"  {who:22} guard REJECT: {g.reason}")
                continue
            rp = layer.role(role).row_policy
            final = rls(g.sql, rp, user) if rp else g.sql
            r = run_query(con, final)
            preview = r.rows[0] if len(r.rows) == 1 else f"{len(r.rows)} rows, first: {r.rows[:2]}"
            print(f"  {who:22} {preview}")
            if final != g.sql:
                print(f"  {'':22} ran: {final}")


if __name__ == "__main__":
    main()

"""Exercise 3 companion: throw queries at the SQL guard and see what it does.

    python labs/08-enterprise-data/guard_cli.py                      # the attack list, with YOUR guard
    python labs/08-enterprise-data/guard_cli.py --reference          # the reference guard
    python labs/08-enterprise-data/guard_cli.py --sql "SELECT email FROM employees" --role people_ops
    python labs/08-enterprise-data/guard_cli.py --run --sql "SELECT priority, COUNT(*) FROM tickets GROUP BY 1"

The policy comes from the semantic layer (datakit/data/acme_semantic.yaml):
  roles: analyst (no pii, no financial), support_lead, finance (financial), manager (pii, own team),
  people_ops (pii). pii: employees.email, employees.start_date. financial: customers.arr_usd.
  row_limit 200.
"""

from __future__ import annotations

import argparse

import _lab
from _lab import pick
from datakit import connect_ro, load_layer, policy_from_layer, run_query

# (query, role, should it pass?, what it tests)
ATTACKS = [
    ("SELECT priority, COUNT(*) AS n FROM tickets GROUP BY priority", "analyst", True, "a normal query: LIMIT gets added"),
    ("SELECT id FROM tickets LIMIT 100000", "analyst", True, "LIMIT above the cap is lowered"),
    ("SELECT 1; DROP TABLE tickets", "analyst", False, "stacked statements"),
    ("DELETE FROM tickets WHERE 1 = 1", "analyst", False, "a write"),
    ("PRAGMA table_info(employees)", "analyst", False, "PRAGMA"),
    ("ATTACH DATABASE '/tmp/evil.db' AS evil", "analyst", False, "ATTACH another file"),
    ("SELECT * FROM sqlite_master", "analyst", False, "system catalog"),
    ("SELECT id FROM main.customers", "analyst", False, "schema-qualified name"),
    ("SELECT * FROM pragma_table_info('employees')", "analyst", False, "table-valued function"),
    ("SELECT load_extension('/tmp/x.so')", "analyst", False, "loading native code"),
    ("SELECT email FROM employees", "analyst", False, "PII column"),
    ("SELECT email FROM employees", "people_ops", True, "PII allowed for this role"),
    ("SELECT * FROM employees WHERE team = 'identity'", "analyst", False, "SELECT * expands to PII"),
    ("SELECT e.* FROM employees e", "analyst", False, "alias.* expands too"),
    ("SELECT \"EMAIL\" FROM Employees", "analyst", False, "case and quoting tricks"),
    ("SELECT [email] FROM employees", "analyst", False, "SQLite bracket quoting"),
    ("SELECT lower(email) AS team FROM employees", "analyst", False, "PII hidden in a function and an alias"),
    ("SELECT x FROM (SELECT email AS x FROM employees)", "analyst", False, "PII in a subquery"),
    ("WITH t AS (SELECT email FROM employees) SELECT * FROM t", "analyst", False, "PII in a CTE"),
    ("SELECT id FROM tickets UNION SELECT email FROM employees", "analyst", False, "PII in a UNION branch"),
    ("SELECT COUNT(*) FROM employees WHERE email LIKE 'gil%'", "analyst", False, "PII in WHERE leaks too"),
    ("SELECT name FROM employees -- ; DELETE FROM employees", "analyst", True, "a comment is not a statement"),
    ("SELECT SUM(arr_usd) FROM customers", "analyst", False, "financial column"),
    ("SELECT SUM(arr_usd) FROM customers", "finance", True, "financial allowed for finance"),
    ("SELECT name FROM employees", "finance", False, "table not allowed for the role"),
    ("SELECT id FROM tickets LIMIT (SELECT 1000000)", "analyst", False, "LIMIT that is not a number"),
    ("SELECT nosuch FROM tickets", "analyst", False, "a column that does not exist"),
    ("SELECT id FROM employees e JOIN teams t ON t.id = e.team", "analyst", False, "ambiguous column"),
    ("WITH employees AS (SELECT 1 AS id) SELECT id FROM employees", "analyst", True, "a CTE may reuse a table name"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--sql")
    ap.add_argument("--role", default="analyst")
    ap.add_argument("--run", action="store_true", help="execute accepted SQL (read-only)")
    a = ap.parse_args()
    guard, src = pick("guard_sql", a.reference)
    policy = policy_from_layer(load_layer())
    print(f"guard: {src}\n")
    cases = [(a.sql, a.role, None, "your query")] if a.sql else ATTACKS
    con = connect_ro() if a.run else None
    good = 0
    for sql, role, expect, what in cases:
        res = guard(sql, policy, role)
        mark = "" if expect is None else ("ok  " if res.ok == expect else "BAD ")
        good += expect is not None and res.ok == expect
        print(f"{mark}[{role}] {sql}")
        print(f"      {'ACCEPT -> ' + str(res.sql) if res.ok else 'REJECT: ' + str(res.reason)}   ({what})")
        if res.ok and res.changes:
            print(f"      changes: {', '.join(res.changes)}")
        if res.ok and con is not None:
            r = run_query(con, res.sql)
            print(f"      {' | '.join(r.columns)}")
            for row in r.rows[:10]:
                print("      " + " | ".join(str(v) for v in row))
    if not a.sql:
        print(f"\n{good}/{len(cases)} behave as expected")


if __name__ == "__main__":
    main()

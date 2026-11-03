"""Exercise 3: guard_sql in mine.py.

Policy (from datakit/data/acme_semantic.yaml): six tables; pii = employees.email,
employees.start_date; financial = customers.arr_usd; roles analyst (sees nothing extra),
finance (customers, tickets, teams; financial), people_ops (pii), manager (pii); row_limit 200.
"""

import pytest

from mine import guard_sql

ACCEPT = [
    ("SELECT priority, COUNT(*) AS n FROM tickets GROUP BY priority", "analyst"),
    ("SELECT name, title FROM employees WHERE team = 'identity'", "analyst"),
    ("SELECT t.name, e.name FROM teams t JOIN employees e ON e.id = t.lead_id", "analyst"),
    ("SELECT email FROM employees", "people_ops"),
    ("SELECT SUM(arr_usd) FROM customers", "finance"),
    ("WITH employees AS (SELECT 1 AS id) SELECT id FROM employees", "analyst"),
    ("SELECT name FROM employees -- ; DELETE FROM employees", "analyst"),
    ("SELECT id FROM tickets;", "analyst"),
    ("SELECT id FROM tickets UNION SELECT id FROM customers", "analyst"),
    ("SELECT * FROM tickets WHERE priority = 'P1'", "analyst"),
]

REJECT = [
    # (sql, role, a word the reason must contain)
    ("SELECT 1; DROP TABLE tickets", "analyst", "one statement"),
    ("SELECT id FROM tickets; SELECT id FROM customers", "analyst", "one statement"),
    ("DELETE FROM tickets WHERE 1 = 1", "analyst", "only SELECT"),
    ("UPDATE tickets SET status = 'closed'", "analyst", "only SELECT"),
    ("DROP TABLE tickets", "analyst", "only SELECT"),
    ("PRAGMA table_info(employees)", "analyst", "only SELECT"),
    ("ATTACH DATABASE '/tmp/evil.db' AS evil", "analyst", "only SELECT"),
    ("SELECT FROM WHERE", "analyst", "parse"),
    ("SELECT * FROM sqlite_master", "analyst", "not allowed"),
    ("SELECT id FROM main.customers", "analyst", "schema-qualified"),
    ("SELECT * FROM pragma_table_info('employees')", "analyst", "not allowed"),
    ("SELECT load_extension('/tmp/x.so')", "analyst", "not allowed"),
    ("SELECT hex(randomblob(1000000000))", "analyst", "not allowed"),
    ("SELECT email FROM employees", "analyst", "pii"),
    ("SELECT * FROM employees", "analyst", "pii"),
    ("SELECT e.* FROM employees e", "analyst", "pii"),
    ("SELECT \"EMAIL\" FROM Employees", "analyst", "pii"),
    ("SELECT [email] FROM employees", "analyst", "pii"),
    ("SELECT lower(email) AS team FROM employees", "analyst", "pii"),
    ("SELECT x FROM (SELECT email AS x FROM employees)", "analyst", "pii"),
    ("WITH t AS (SELECT email FROM employees) SELECT * FROM t", "analyst", "pii"),
    ("SELECT id FROM tickets UNION SELECT email FROM employees", "analyst", "pii"),
    ("SELECT COUNT(*) FROM employees WHERE email LIKE 'gil%'", "analyst", "pii"),
    ("SELECT name FROM employees ORDER BY start_date", "analyst", "pii"),
    ("SELECT SUM(arr_usd) FROM customers", "analyst", "financial"),
    ("SELECT SUM(arr_usd) FROM customers", "people_ops", "financial"),
    ("SELECT name FROM employees", "finance", "not allowed for role"),
    ("WITH t AS (SELECT * FROM sqlite_master) SELECT * FROM t", "analyst", "not allowed"),
    ("SELECT nosuch FROM tickets", "analyst", "resolve"),
    ("SELECT id FROM employees e JOIN teams t ON t.id = e.team", "analyst", "resolve"),
    ("SELECT id FROM tickets LIMIT (SELECT 1000000)", "analyst", "LIMIT"),
    ("SELECT id FROM tickets LIMIT 10 + 1000", "analyst", "LIMIT"),
    ("SELECT id FROM tickets", "intern", "unknown role"),
]


@pytest.mark.parametrize("sql,role", ACCEPT)
def test_accepts(sql, role, policy):
    res = guard_sql(sql, policy, role)
    assert res.ok, res.reason
    assert res.sql and "LIMIT" in res.sql.upper()


@pytest.mark.parametrize("sql,role,word", REJECT)
def test_rejects(sql, role, word, policy):
    res = guard_sql(sql, policy, role)
    assert not res.ok, f"should be rejected: {sql}"
    assert word.lower() in (res.reason or "").lower(), res.reason


def test_pii_reason_is_exact(policy):
    res = guard_sql("SELECT email FROM employees", policy, "analyst")
    assert res.reason == "column employees.email is pii; role analyst may not see it"


def test_adds_limit(policy):
    res = guard_sql("SELECT id FROM tickets", policy, "analyst")
    assert res.sql == "SELECT id FROM tickets LIMIT 200"
    assert res.changes == ["added LIMIT 200"]


def test_lowers_limit_and_keeps_small_one(policy):
    res = guard_sql("SELECT id FROM tickets LIMIT 5000", policy, "analyst")
    assert res.sql == "SELECT id FROM tickets LIMIT 200"
    assert res.changes == ["lowered LIMIT 5000 to 200"]
    res = guard_sql("SELECT id FROM tickets LIMIT 3", policy, "analyst")
    assert res.sql == "SELECT id FROM tickets LIMIT 3" and res.changes == []


def test_limit_on_union_is_outermost(policy):
    res = guard_sql("SELECT id FROM tickets UNION SELECT id FROM customers", policy, "analyst")
    assert res.sql.endswith("LIMIT 200")
    assert res.sql.upper().count("LIMIT") == 1


def test_reports_tables_and_columns(policy):
    res = guard_sql("SELECT t.name, e.name FROM teams t JOIN employees e ON e.id = t.lead_id", policy, "analyst")
    assert res.tables == ["teams", "employees"]
    assert set(res.columns) == {"teams.name", "employees.name", "employees.id", "teams.lead_id"}


def test_star_expands_to_real_columns(policy):
    res = guard_sql("SELECT * FROM teams", policy, "analyst")
    assert res.ok
    assert "teams.headcount" in res.columns and "teams.lead_id" in res.columns


def test_policy_driven_not_hardcoded(policy):
    """Your guard must read the policy, not a list of names you typed in."""
    from datakit.guard import Policy
    p = Policy(columns={"pets": ["id", "owner_phone"]}, sensitive={"pets.owner_phone": "pii"},
               roles={"vet": {"tables": ["pets"], "sees": []}}, row_limit=7)
    assert guard_sql("SELECT id FROM pets", p, "vet").sql == "SELECT id FROM pets LIMIT 7"
    assert not guard_sql("SELECT owner_phone FROM pets", p, "vet").ok
    assert not guard_sql("SELECT id FROM tickets", p, "vet").ok

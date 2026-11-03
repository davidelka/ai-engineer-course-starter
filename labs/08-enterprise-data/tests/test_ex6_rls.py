"""Exercise 6: apply_row_policy in mine.py.

Row policy of the manager role (datakit/data/acme_semantic.yaml):
  employees:     team = :team
  access_grants: employee_id IN (SELECT id FROM employees WHERE team = :team)
Facts in acme.db: core-api has 7 employees, identity 5, 120 in total; 300 access grants,
14 of them belong to core-api people; 200 tickets (not policed).
"""

import pytest

from mine import apply_row_policy

POLICY = {"employees": "team = :team",
          "access_grants": "employee_id IN (SELECT id FROM employees WHERE team = :team)"}
CORE = {"team": "core-api"}


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_simple_count(con):
    assert one(con, apply_row_policy("SELECT COUNT(*) FROM employees", POLICY, CORE)) == 7
    assert one(con, apply_row_policy("SELECT COUNT(*) FROM employees", POLICY, {"team": "identity"})) == 5


def test_alias_is_kept(con):
    sql = apply_row_policy("SELECT e.name FROM employees e WHERE e.location = 'Haifa'", POLICY, CORE)
    assert " AS e" in sql
    names = [r[0] for r in con.execute(sql)]
    assert len(names) == len(set(names)) and len(names) <= 7


def test_filter_in_join_cannot_escape(con):
    sql = apply_row_policy("SELECT e.name FROM employees e JOIN teams t ON t.id = e.team WHERE t.id = 'engine'",
                           POLICY, CORE)
    assert con.execute(sql).fetchall() == []


def test_subquery_cte_and_union_are_filtered(con):
    assert one(con, apply_row_policy("SELECT COUNT(*) FROM (SELECT id FROM employees)", POLICY, CORE)) == 7
    assert one(con, apply_row_policy("WITH x AS (SELECT id FROM employees) SELECT COUNT(*) FROM x", POLICY, CORE)) == 7
    rows = con.execute(apply_row_policy("SELECT id FROM employees UNION ALL SELECT id FROM employees",
                                        POLICY, CORE)).fetchall()
    assert len(rows) == 14


def test_second_policed_table(con):
    assert one(con, apply_row_policy("SELECT COUNT(*) FROM access_grants", POLICY, CORE)) == 14


def test_unpoliced_table_untouched(con):
    sql = apply_row_policy("SELECT COUNT(*) FROM tickets", POLICY, CORE)
    assert one(con, sql) == 200
    assert "WHERE" not in sql.upper()


def test_cte_with_policed_name_is_not_rewritten():
    sql = apply_row_policy("WITH employees AS (SELECT 1 AS id) SELECT id FROM employees", POLICY, CORE)
    assert "core-api" not in sql


def test_value_cannot_inject(con):
    evil = {"team": "x' OR '1'='1"}
    assert one(con, apply_row_policy("SELECT COUNT(*) FROM employees", POLICY, evil)) == 0


def test_missing_parameter_raises():
    with pytest.raises(KeyError):
        apply_row_policy("SELECT COUNT(*) FROM employees", POLICY, {})


def test_empty_policy_returns_sql_unchanged():
    assert apply_row_policy("SELECT id FROM tickets", {}, {}) == "SELECT id FROM tickets"

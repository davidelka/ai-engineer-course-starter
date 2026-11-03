"""datakit (lesson 8): semantic layer, SQL guard, row policy, read-only execution, freshness,
provenance, execution accuracy, and the text-to-SQL loop over recorded replies. No network."""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "08-enterprise-data"

pytest.importorskip("sqlglot")  # labs/08-enterprise-data/requirements.txt

from datakit import (apply_row_policy, connect_ro, freshness_report, guard_sql, load_layer,  # noqa: E402
                     policy_from_layer, render_context, results_match, run_query)
from datakit.db import QueryTimeout  # noqa: E402
from datakit.provenance import build_provenance, supporting_rows  # noqa: E402
from datakit.semantic import Layer, render_ddl  # noqa: E402
from datakit.text2sql import (SQLPlan, Settings, answer_question, load_fixtures, redact_for_llm,  # noqa: E402
                              replay_llm)


@pytest.fixture(scope="module")
def layer():
    return load_layer()


@pytest.fixture(scope="module")
def policy(layer):
    return policy_from_layer(layer)


@pytest.fixture
def con():
    c = connect_ro()
    yield c
    c.close()


# ------------------------------------------------------------------ semantic layer
def test_layer_loads_and_is_consistent(layer):
    assert set(layer.tables) == {"employees", "teams", "systems", "access_grants", "customers", "tickets"}
    assert {m.name for m in layer.metrics} >= {"sla_breach_rate", "open_tickets", "red_folder_arr"}
    assert layer.role("manager").row_policy["employees"] == "team = :team"


def test_layer_columns_match_the_database(layer, con):
    for t, tab in layer.tables.items():
        cols = {r[1] for r in con.execute(f'PRAGMA table_info("{t}")')} - {"_source_system", "_extracted_at"}
        assert cols == set(tab.columns), t


def test_layer_rejects_bad_references(layer):
    data = layer.model_dump(by_alias=True)
    data["relationships"].append({"from": "tickets.nosuch", "to": "customers.id"})
    with pytest.raises(ValidationError, match="unknown column tickets.nosuch"):
        Layer.model_validate(data)


def test_render_hides_by_role(layer):
    analyst = render_context(layer, role="analyst")
    assert "- email " not in analyst and "- arr_usd " not in analyst
    assert "sla_breach_rate" in analyst and "tickets.customer_id = customers.id" in analyst
    finance = render_context(layer, role="finance")
    assert "- arr_usd " in finance and "### employees" not in finance
    assert len(render_context(layer, tables=["tickets"])) < len(analyst)


def test_ddl_is_smaller_but_poorer(layer):
    ddl = render_ddl(ROOT / "data" / "acme" / "corpus" / "structured" / "acme.db")
    assert "CREATE TABLE tickets" in ddl and "pending" not in ddl


# ------------------------------------------------------------------ guard
@pytest.mark.parametrize("sql,role,ok", [
    ("SELECT priority, COUNT(*) FROM tickets GROUP BY priority", "analyst", True),
    ("SELECT 1; DROP TABLE tickets", "analyst", False),
    ("PRAGMA table_info(employees)", "analyst", False),
    ("SELECT * FROM sqlite_master", "analyst", False),
    ("SELECT id FROM main.customers", "analyst", False),
    ("SELECT * FROM employees", "analyst", False),
    ("SELECT [email] FROM employees", "analyst", False),
    ("WITH t AS (SELECT email FROM employees) SELECT * FROM t", "analyst", False),
    ("SELECT email FROM employees", "people_ops", True),
    ("SELECT SUM(arr_usd) FROM customers", "finance", True),
    ("SELECT name FROM employees", "finance", False),
    ("SELECT load_extension('x')", "analyst", False),
])
def test_guard_cases(policy, sql, role, ok):
    assert guard_sql(sql, policy, role).ok is ok


def test_guard_limit_rewrite(policy):
    assert guard_sql("SELECT id FROM tickets LIMIT 999", policy, "analyst").sql == "SELECT id FROM tickets LIMIT 200"
    assert not guard_sql("SELECT id FROM tickets LIMIT (SELECT 9)", policy, "analyst").ok


def test_guard_accepts_every_golden_query(policy):
    for line in (LAB / "golden" / "business_questions.jsonl").read_text().splitlines():
        g = json.loads(line)
        if g["gold_sql"]:
            assert guard_sql(g["gold_sql"], policy, g["role"]).ok, g["id"]


# ------------------------------------------------------------------ database layer
def test_connection_is_read_only(con):
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM tickets")


def test_timeout_aborts_runaway_query(con):
    with pytest.raises(QueryTimeout):
        run_query(con, "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c",
                  timeout_ms=200)
    assert run_query(con, "SELECT COUNT(*) FROM tickets").rows == [(200,)]  # handler removed afterwards


def test_row_cap_and_truncation(con):
    r = run_query(con, "SELECT id FROM tickets", max_rows=10)
    assert len(r.rows) == 10 and r.truncated


def test_authorizer_denies_column():
    c = connect_ro(deny_columns=["employees.email"])
    with pytest.raises(sqlite3.DatabaseError):
        c.execute("SELECT email FROM employees").fetchall()
    assert c.execute("SELECT COUNT(*) FROM employees").fetchone() == (120,)
    c.close()


# ------------------------------------------------------------------ row policy
def test_row_policy(layer, con):
    rp = layer.role("manager").row_policy
    q = lambda s, team="core-api": con.execute(apply_row_policy(s, rp, {"team": team})).fetchone()[0]  # noqa: E731
    assert q("SELECT COUNT(*) FROM employees") == 7
    assert q("SELECT COUNT(*) FROM access_grants") == 14
    assert q("SELECT COUNT(*) FROM (SELECT id FROM employees)") == 7
    assert q("SELECT COUNT(*) FROM tickets") == 200
    assert q("SELECT COUNT(*) FROM employees", team="x' OR '1'='1") == 0
    with pytest.raises(KeyError):
        apply_row_policy("SELECT 1 FROM employees", rp, {})


# ------------------------------------------------------------------ freshness and provenance
def test_freshness(con):
    out = freshness_report(con, ["tickets", "systems"], "2026-11-03T09:00:00Z", {"tickets": 24, "systems": 168})
    assert [f.stale for f in out] == [True, False] and out[0].age_hours == 58.0


def test_supporting_rows_for_aggregate_and_listing(layer, con):
    pks = {t: tab.primary_key for t, tab in layer.tables.items()}
    lin = supporting_rows(con, "SELECT COUNT(*) FROM tickets WHERE incident_id = 'INC-2026-08-19'", pks)
    assert lin.table == "tickets" and lin.total == 15
    lin = supporting_rows(con, "SELECT id FROM tickets ORDER BY first_response_minutes DESC LIMIT 3", pks)
    assert lin.total == 3
    assert supporting_rows(con, "SELECT id FROM tickets UNION SELECT id FROM customers", pks) is None


def test_provenance_chips(layer, con):
    pks = {t: tab.primary_key for t, tab in layer.tables.items()}
    p = build_provenance(con, "SELECT COUNT(*) FROM tickets WHERE priority = 'P1'", ["tickets"], pks,
                         "2026-11-01T09:00:00Z", 24)
    [chip] = p.chips()
    assert "Zendesk API" in chip and "26 rows" in chip and "STALE" not in chip


# ------------------------------------------------------------------ evaluation
def test_results_match():
    assert results_match([(79, "Tel Aviv")], [("Tel Aviv", 79)])
    assert results_match([(3.0,)], [(3,)])
    assert not results_match([(1,), (1,)], [(1,), (2,)])
    assert not results_match([("a", 1), ("b", 2)], [("b", 2), ("a", 1)], ordered=True)
    assert results_match([("x", "X", 1)], [("X", 1)], allow_extra_columns=True)
    assert not results_match([("x", "X", 1)], [("X", 1)])


def test_golden_file_in_sync():
    spec = importlib.util.spec_from_file_location("build_golden", LAB / "golden" / "build_golden.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    built = mod.build()
    stored = [json.loads(l) for l in (LAB / "golden" / "business_questions.jsonl").read_text().splitlines()]
    assert built == stored
    assert 20 <= len(stored) <= 30


# ------------------------------------------------------------------ the loop, offline
@pytest.fixture(scope="module")
def replay():
    return replay_llm(load_fixtures(LAB / "fixtures" / "replay.jsonl"))


def test_fixtures_are_valid_plans():
    for q, fx in load_fixtures(LAB / "fixtures" / "replay.jsonl").items():
        for p in fx["plans"]:
            SQLPlan.model_validate_json(p)


def test_loop_answers_with_provenance(replay, layer):
    ans = answer_question(replay, "How many tickets are linked to the August outage, and how many of them breached the SLA?",
                          Settings(layer=layer))
    assert ans.status == "ok" and ans.rows == [(15, 6)]
    assert ans.sql_executed.endswith("LIMIT 200")
    assert ans.provenance.rows.total == 15 and "Zendesk API" in ans.provenance.chips()[0]
    assert ans.answer and ans.cost_usd > 0


def test_loop_repairs_after_guard_rejection(replay, layer):
    ans = answer_question(replay, "List the people on the Identity team with their job titles.", Settings(layer=layer))
    assert ans.attempts == 2 and ans.errors[0].startswith("guard:") and len(ans.rows) == 5


def test_loop_refuses_pii_and_document_questions(replay, layer):
    a = answer_question(replay, "What are the email addresses of the Identity team?", Settings(layer=layer))
    assert a.status == "not_answerable" and not a.rows
    b = answer_question(replay, "Why did the August outage happen?", Settings(layer=layer))
    assert b.status == "not_answerable"


def test_loop_applies_row_policy(replay, layer):
    ans = answer_question(replay, "List the people on my team with their email addresses.",
                          Settings(role="manager", user={"team": "core-api"}, layer=layer))
    assert len(ans.rows) == 7 and "(SELECT * FROM employees WHERE team = 'core-api')" in ans.sql_executed


def test_redaction_before_the_model():
    assert redact_for_llm(["name", "email"], [("Gil", "gil.avraham@acme.example")]) == [("Gil", "<email>")]


def test_offline_execution_accuracy(replay, layer):
    """The synthetic replies contain three deliberate mistakes (q09, q12, q15): EX = 24/27."""
    golden = [json.loads(l) for l in (LAB / "golden" / "business_questions.jsonl").read_text().splitlines()]
    correct = 0
    for g in golden:
        ans = answer_question(replay, g["question"], Settings(role=g["role"], user=g["user"], layer=layer,
                                                              narrate=False))
        if g["expect"] == "refuse":
            correct += ans.status in ("not_answerable", "rejected")
        else:
            correct += ans.status == "ok" and results_match(ans.rows, g["rows"], ordered=g["ordered"])
    assert correct == 24

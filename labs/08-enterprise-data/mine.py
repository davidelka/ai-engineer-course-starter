"""Your code for lesson 8. Each part is checked by tests in ./tests.

datakit/ has reference versions (guard.py, evaluate.py, rls.py, freshness.py).
Try not to peek before your tests pass.

    python -m pytest -q labs/08-enterprise-data/tests

The data: data/acme/corpus/structured/acme.db (SQLite, read-only). Six tables:
  employees(id, name, email*, title, team, manager_id, location, start_date*)
  teams(id, name, department, lead_id, parent_lead_id, main_location, headcount)
  systems(name, owner_team, tier, data_classification, approved_tool, kind, sensitive)
  access_grants(id, employee_id, system, level, granted_at, approved_by, route, expires_at, policy_version)
  customers(id, name, plan, region, seats, arr_usd**, currency, red_folder)
  tickets(id, customer_id, customer_plan, subject, priority, status, created_at,
          first_response_minutes, sla_target_minutes, sla_breached, assigned_team, red_folder, incident_id)
  provenance(table_name, source_system, source_object, extracted_at, extracted_by, row_count, notes)
  * = pii, ** = financial. Every data table also has _source_system and _extracted_at.
Roles and sensitivities come from datakit/data/acme_semantic.yaml (exercise 2 is your copy).
"""

from __future__ import annotations

import sqlite3  # noqa: F401
from collections import Counter  # noqa: F401
from datetime import datetime, timezone  # noqa: F401
from itertools import permutations  # noqa: F401
from typing import Any, Sequence, Union

import sqlglot  # noqa: F401
from sqlglot import exp  # noqa: F401
from sqlglot.errors import OptimizeError, ParseError  # noqa: F401
from sqlglot.optimizer.qualify import qualify  # noqa: F401
from sqlglot.optimizer.scope import traverse_scope  # noqa: F401

from datakit.freshness import Freshness, parse_ts  # noqa: F401
from datakit.guard import FORBIDDEN_FUNCTIONS, FORBIDDEN_NODES, GuardResult, Policy  # noqa: F401


# ------------------------------------------------------------------ exercise 3
def guard_sql(sql: str, policy: Policy, role: str) -> GuardResult:
    """Decide whether SQL written by a model may run, and return the SQL to run.

    policy.columns   {table: [column, ...]}         the allow-list of tables and columns
    policy.sensitive {"table.column": "pii"|"financial"}
    policy.roles     {role: {"tables": [...], "sees": ["pii", "financial"]}}
    policy.row_limit the maximum LIMIT

    Return GuardResult(ok=False, reason=...) on the FIRST problem, checked in this order:
      1. unknown role                                   reason contains "unknown role"
      2. does not parse (sqlglot.parse, read="sqlite") reason contains "parse"
         or the number of statements is not exactly 1  reason contains "one statement"
         (sqlglot.parse returns None for an empty trailing statement after ';': ignore those)
      3. the statement is not a query (exp.Select or exp.SetOperation for UNION/INTERSECT/EXCEPT)
                                                        reason contains "only SELECT"
         or any node in FORBIDDEN_NODES appears anywhere in the tree (tree.find_all)
                                                        reason contains "forbidden"
         or a function in FORBIDDEN_FUNCTIONS is called (exp.Func nodes; for exp.Anonymous
         use .name, otherwise .sql_name(); compare lowercase) reason contains "not allowed"
      4. tables (exp.Table nodes; CTE names from exp.CTE are local and skipped):
         - empty table name (a table-valued function like pragma_table_info(...))  "not allowed"
         - schema-qualified (t.args.get("db") or t.args.get("catalog"))            "schema-qualified"
         - not in policy.columns                                                    "not allowed"
         - not in the role's tables                                                 "not allowed for role"
      5. columns: run qualify(tree.copy(), schema=policy.schema_for(tables), dialect="sqlite",
         validate_qualify_columns=True, quote_identifiers=False). It expands SELECT * and
         resolves every column to its source. OptimizeError -> reason contains "resolve".
         Then for every scope in traverse_scope(qualified), for every col in scope.columns,
         source = scope.sources.get(col.table); if it is an exp.Table, the column read is
         "<table>.<column>" (lowercase). Collect them in order, without duplicates.
      6. any column read whose policy.sensitive level is not in the role's "sees":
         reason exactly: "column <table>.<column> is <level>; role <role> may not see it"
      7. LIMIT on the OUTERMOST query (tree.args.get("limit")):
         - missing: add LIMIT policy.row_limit, changes ["added LIMIT <n>"]
         - a plain integer above row_limit: lower it, changes ["lowered LIMIT <old> to <n>"]
         - anything else (a subquery, an expression, a string): reject, reason contains "LIMIT"
    On success: GuardResult(ok=True, sql=tree.sql(dialect="sqlite"), tables=[...in order of
    first appearance], columns=[...], changes=[...]).
    Write reasons for the MODEL: they are sent back to it in a repair turn.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement guard_sql")


# ------------------------------------------------------------------ exercise 5
def results_match(pred_rows: Sequence[Sequence[Any]], gold_rows: Sequence[Sequence[Any]],
                  ordered: bool = False, allow_extra_columns: bool = False) -> bool:
    """Execution accuracy: do two query results contain the same answer?

    Normalize every value first:
      - bool -> int
      - float -> round(v, 4); and if the rounded value is a whole number, int (so 3.0 == 3)
      - str -> stripped
      - everything else (int, None) unchanged
    Then:
      - different number of rows -> False; both empty -> True
      - ordered=False: compare as multisets (duplicates count: [1, 1] != [1])
        ordered=True: compare as lists
      - column order does not matter: try every permutation of the predicted columns
        (itertools.permutations(range(pred_width), gold_width))
      - the predicted result may have MORE columns than the gold only when
        allow_extra_columns=True (then some choice of gold_width predicted columns must match);
        fewer columns is always False
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement results_match")


# ------------------------------------------------------------------ exercise 6
def apply_row_policy(sql: str, row_policy: dict[str, str], params: dict[str, str]) -> str:
    """Row-level security by rewriting: every reference to a policed table becomes a filtered
    subquery with the same alias.

    row_policy: {table: condition}, e.g. {"employees": "team = :team"}
    params:     {"team": "core-api"}

        SELECT e.name FROM employees e
     -> SELECT e.name FROM (SELECT * FROM employees WHERE team = 'core-api') AS e
        SELECT COUNT(*) FROM employees
     -> SELECT COUNT(*) FROM (SELECT * FROM employees WHERE team = 'core-api') AS employees

    Rules:
      - every exp.Table whose name (lowercase) is in row_policy, anywhere in the tree (FROM,
        JOIN, subqueries, CTE bodies, UNION branches), EXCEPT names defined by a CTE
      - collect the targets first, then replace them (so the new inner tables are not rewritten)
      - alias = the table's alias if it has one, else its name
      - parse the condition with sqlglot and replace each exp.Placeholder (":team") with
        exp.Literal.string(value). Never build SQL by string concatenation: a value like
        "x' OR '1'='1" must stay one harmless string.
      - a placeholder with no value in params: raise KeyError
      - empty row_policy: return sql unchanged
    Return the rewritten SQL as a string (dialect="sqlite").
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement apply_row_policy")


# ------------------------------------------------------------------ exercise 7
def freshness_report(con: sqlite3.Connection, tables: list[str], now: Union[str, datetime],
                     max_age_hours: Union[float, dict[str, float]] = 24.0) -> list[Freshness]:
    """How old is the data in each table, and is it too old?

    For each table, in the given order, return a Freshness(table, extracted_at, age_hours,
    max_age_hours, stale, source_system, note):
      - extracted_at: the OLDEST row's _extracted_at (SELECT MIN(_extracted_at), MAX(_extracted_at))
      - age_hours: hours between that and `now`, rounded to 2 decimals (use parse_ts for both)
      - max_age_hours: the number, or max_age_hours[table] (default 24) when a dict is given
      - stale: age_hours > max_age_hours
      - source_system: from the provenance table (WHERE table_name = ?), "" if no row
      - note:
          * MIN != MAX: the rows were extracted at different times. Note must contain
            "partial" (a half-finished load is the usual cause).
          * else, if the provenance row's extracted_at differs from the rows: note contains
            "provenance".
          * else "".
      - empty table: extracted_at "", age_hours float("inf"), stale True, note "table is empty"
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement freshness_report")

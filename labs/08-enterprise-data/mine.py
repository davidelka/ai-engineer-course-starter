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

    Receives the SQL text, a Policy and a role name. The Policy carries:
        policy.columns   {table: [column, ...]}   allow-list of tables and columns
        policy.sensitive {"table.column": "pii"|"financial"}
        policy.roles     {role: {"tables": [...], "sees": ["pii", "financial"]}}
        policy.row_limit the maximum LIMIT;  policy.schema_for(tables) a schema for sqlglot
    Returns a GuardResult. On the FIRST problem (in this priority order) ok=False, and reason
    contains the quoted words:
      1. role not in policy.roles                                        "unknown role"
      2. SQL does not parse (SQLite dialect)                             "parse"
         not exactly one statement (a trailing ';' alone is fine)        "one statement"
      3. not a query (SELECT or UNION/INTERSECT/EXCEPT)                  "only SELECT"
         a FORBIDDEN_NODES node anywhere                                 "forbidden"
         a FORBIDDEN_FUNCTIONS function is called                        "not allowed"
      4. a table-valued function, or a table outside policy.columns      "not allowed"
         a schema-qualified table (main.customers)                       "schema-qualified"
         a table outside the role's tables                               "not allowed for role"
         (names defined by a CTE are local, not tables)
      5. a column that cannot be resolved to a source table              "resolve"
      6. a column READ anywhere (SELECT *, WHERE, ORDER BY, subqueries, CTEs) whose sensitive
         level the role does not see -> reason EXACTLY:
             "column <table>.<column> is <level>; role <role> may not see it"
      7. the outermost LIMIT is not a plain integer                      "LIMIT"
    On success: ok=True, sql=the query in SQLite dialect with the OUTERMOST LIMIT capped at
    row_limit, changes=["added LIMIT <n>"] or ["lowered LIMIT <old> to <n>"] or [],
    tables=[in order of first appearance], columns=["table.column" lowercase, in order, no
    duplicates]. Reasons are sent back to the MODEL in a repair turn: write them for it.
    Stuck? HINTS.md -> guard_sql
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement guard_sql")


# ------------------------------------------------------------------ exercise 5
def results_match(pred_rows: Sequence[Sequence[Any]], gold_rows: Sequence[Sequence[Any]],
                  ordered: bool = False, allow_extra_columns: bool = False) -> bool:
    """Execution accuracy: do two query results contain the same answer?

    Receives two results (sequences of rows, each row a sequence of values). Returns bool.
      - Values are compared after normalization: bool counts as int, floats are equal when
        they agree to 4 decimals and a whole float equals the int (3.0 == 3), strings are
        compared stripped. int and None compare as they are.
      - Different number of rows -> False; both empty -> True.
      - ordered=False: rows compared as multisets (duplicates count: [1, 1] != [1]).
        ordered=True: compared as lists.
      - Column order does not matter.
      - The prediction may have MORE columns than the gold only when allow_extra_columns=True
        (then some choice of gold-width columns must match). Fewer columns: always False.
    Stuck? HINTS.md -> results_match
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

    Rules the result must satisfy:
      - every reference to a policed table (name compared lowercase) is filtered, wherever it
        is: FROM, JOIN, subqueries, CTE bodies, UNION branches. A name defined by a CTE is not
        a table and is not rewritten.
      - the alias is the table's alias if it has one, else its name.
      - parameter values become SQL string literals, never string concatenation: a value like
        "x' OR '1'='1" must stay one harmless string.
      - a placeholder with no value in params: raise KeyError.
      - empty row_policy: return sql unchanged.
    Returns the rewritten SQL as a string (SQLite dialect).
    Stuck? HINTS.md -> apply_row_policy
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement apply_row_policy")


# ------------------------------------------------------------------ exercise 7
def freshness_report(con: sqlite3.Connection, tables: list[str], now: Union[str, datetime],
                     max_age_hours: Union[float, dict[str, float]] = 24.0) -> list[Freshness]:
    """How old is the data in each table, and is it too old?

    Receives an open connection, table names, `now` (ISO string or datetime, naive or aware)
    and max_age_hours (one number, or {table: hours} with 24 for a missing table).
    Returns one Freshness(table, extracted_at, age_hours, max_age_hours, stale, source_system,
    note) per table, in the given order:
      - extracted_at: the OLDEST row's _extracted_at
      - age_hours: hours from extracted_at to now, rounded to 2 decimals
      - stale: age_hours > max_age_hours
      - source_system: from the provenance table row for this table, "" if there is none
      - note: contains "partial" if the rows were extracted at different times; otherwise
        contains "provenance" if the provenance row's extracted_at differs from the rows';
        otherwise "".
      - empty table: extracted_at "", age_hours float("inf"), stale True, note "table is empty"
    Stuck? HINTS.md -> freshness_report
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement freshness_report")

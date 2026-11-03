"""Row-level security by query rewriting (lesson 8).

A manager may see PII, but only of their own team. The semantic layer says so:

    roles.manager.row_policy:
      employees: "team = :team"
      access_grants: "employee_id IN (SELECT id FROM employees WHERE team = :team)"

apply_row_policy replaces every reference to a policed table, wherever it appears
(FROM, JOIN, subquery, CTE body, UNION branch), with a filtered subquery under the
same alias:

    SELECT e.name FROM employees e
 -> SELECT e.name FROM (SELECT * FROM employees WHERE team = 'core-api') AS e

Parameter values become SQL string literals built by sqlglot (quotes escaped), never
string concatenation. Run it AFTER the guard: the guard checks what the model wrote,
this rewrite only narrows it.

Real databases do this natively: Postgres CREATE POLICY ... USING (team = current_setting('app.team')),
Snowflake row access policies, BigQuery row-level access policies. In SQLite you can
get close with TEMP VIEWs that shadow the table name for one connection.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

DIALECT = "sqlite"


def bind_condition(condition: str, params: dict[str, str]) -> exp.Expression:
    """Parse a row-policy condition and replace :name placeholders with literals."""
    cond = sqlglot.parse_one(condition, read=DIALECT)
    for ph in list(cond.find_all(exp.Placeholder)):
        name = ph.name
        if name not in params or params[name] is None:
            raise KeyError(f"row policy needs parameter :{name}, the user has none")
        value = params[name]
        lit = exp.Literal.number(value) if isinstance(value, (int, float)) else exp.Literal.string(str(value))
        ph.replace(lit)
    return cond


def apply_row_policy(sql: str, row_policy: dict[str, str], params: dict[str, str]) -> str:
    """Reference implementation. Exercise 6 asks you to write your own in mine.py."""
    if not row_policy:
        return sql
    tree = sqlglot.parse_one(sql, read=DIALECT)
    policed = {k.lower(): v for k, v in row_policy.items()}
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    targets = [t for t in tree.find_all(exp.Table)
               if t.name.lower() in policed and t.name.lower() not in ctes]
    for t in targets:
        name = t.name.lower()
        alias = t.alias or t.name
        inner = exp.select("*").from_(exp.to_table(name)).where(bind_condition(policed[name], params))
        t.replace(exp.Subquery(this=inner, alias=exp.TableAlias(this=exp.to_identifier(alias))))
    return tree.sql(dialect=DIALECT)

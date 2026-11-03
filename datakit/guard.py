"""SQL guard (lesson 8): decide whether SQL written by a model may run, and make it safe.

The guard never trusts the model, the prompt, or a regex. It parses the SQL into a
syntax tree with sqlglot and checks the TREE:

1. exactly one statement, and it is a query (SELECT / UNION / WITH ... SELECT)
2. no write, DDL, PRAGMA, ATTACH or other command anywhere in the tree
3. every table is allow-listed for the role (no schema-qualified names like main.x,
   no sqlite_master), CTE names are local and fine
4. every column resolves to a known column of an allowed table (sqlglot's qualify
   expands SELECT * and resolves aliases, subqueries and CTEs)
5. columns marked pii/financial only if the role "sees" that sensitivity, wherever
   they appear (SELECT, WHERE, JOIN, ORDER BY: a WHERE on email leaks email too)
6. no dangerous functions (load_extension, readfile, randomblob ...)
7. LIMIT: added when missing, lowered when above the row limit, rejected when not a number

Defense in depth: the guard is ONE layer. The connection is also read-only
(datakit.db), and the database authorizer can deny sensitive columns again.

    from datakit.guard import guard_sql
    res = guard_sql("SELECT email FROM employees", policy, role="analyst")
    res.ok, res.reason  # False, "column employees.email is pii; role analyst may not see it"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

DIALECT = "sqlite"
# Statement/expression types that must never appear anywhere in the tree.
FORBIDDEN_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
                   exp.Command, exp.Pragma, exp.Attach, exp.Detach, exp.Transaction, exp.Commit,
                   exp.Rollback, exp.Set, exp.Use, exp.Into)
# SQLite functions that read files, load code, or burn CPU/memory.
FORBIDDEN_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer",
                       "randomblob", "zeroblob", "sqlite_compileoption_get", "sqlite_offset"}


@dataclass
class Policy:
    """What may be queried. Build it from the semantic layer: policy_from_layer(layer).

    columns:   {table: [column, ...]}  every known column (the allow-list)
    sensitive: {"table.column": "pii" | "financial"}
    roles:     {role: {"tables": [table, ...], "sees": ["pii", "financial"]}}
    row_limit: the most rows a query may return
    """

    columns: dict[str, list[str]]
    sensitive: dict[str, str] = field(default_factory=dict)
    roles: dict[str, dict] = field(default_factory=dict)
    row_limit: int = 200

    def schema_for(self, tables: list[str]) -> dict:
        return {t: {c: "text" for c in self.columns[t]} for t in tables}


@dataclass
class GuardResult:
    ok: bool
    sql: Optional[str] = None  # the SQL to execute (LIMIT enforced), only when ok
    reason: Optional[str] = None  # why it was rejected, written for the model to fix it
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)  # "table.column" actually read
    changes: list[str] = field(default_factory=list)  # e.g. "added LIMIT 200"


def _reject(reason: str) -> GuardResult:
    return GuardResult(ok=False, reason=reason)


def guard_sql(sql: str, policy: Policy, role: str) -> GuardResult:
    """Reference implementation. Exercise 3 asks you to write your own in mine.py."""
    if role not in policy.roles:
        return _reject(f"unknown role {role!r}")
    allowed_tables = set(policy.roles[role]["tables"])
    sees = set(policy.roles[role].get("sees", []))

    # 1. parse: exactly one statement
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except ParseError as e:
        first = str(e).splitlines()[0][:160]
        return _reject(f"SQL does not parse: {first}")
    if len(statements) != 1:
        return _reject(f"exactly one statement is allowed, got {len(statements)}")
    tree = statements[0]

    # 2. only queries, nothing dangerous anywhere inside
    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        return _reject(f"only SELECT queries are allowed, got {tree.key.upper()}")
    bad = next(tree.find_all(*FORBIDDEN_NODES), None)
    if bad is not None:
        return _reject(f"forbidden operation inside the query: {bad.key.upper()}")
    for fn in tree.find_all(exp.Func):
        name = (fn.name if isinstance(fn, exp.Anonymous) else fn.sql_name()).lower()
        if name in FORBIDDEN_FUNCTIONS:
            return _reject(f"function {name}() is not allowed")

    # 3. tables: allow-listed, not schema-qualified; CTE names are local
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    used_tables: list[str] = []
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if not name:  # table-valued function, e.g. pragma_table_info('x')
            return _reject("table-valued functions are not allowed")
        if t.args.get("db") or t.args.get("catalog"):
            return _reject(f"schema-qualified table {t.sql(dialect=DIALECT)} is not allowed; use the bare table name")
        if name in cte_names:
            continue
        if name not in policy.columns:
            return _reject(f"table {name} does not exist or is not allowed")
        if name not in allowed_tables:
            return _reject(f"table {name} is not allowed for role {role}")
        if name not in used_tables:
            used_tables.append(name)

    # 4. columns: resolve every reference (expands *, follows aliases/subqueries/CTEs)
    try:
        qualified = qualify(tree.copy(), schema=policy.schema_for(used_tables), dialect=DIALECT,
                            validate_qualify_columns=True, quote_identifiers=False)
    except OptimizeError as e:
        return _reject(f"cannot resolve columns: {str(e).splitlines()[0][:160]}")
    read: list[str] = []
    for scope in traverse_scope(qualified):
        for col in scope.columns:
            source = scope.sources.get(col.table)
            if isinstance(source, exp.Table):
                ref = f"{source.name.lower()}.{col.name.lower()}"
                if col.name.lower() not in policy.columns.get(source.name.lower(), []):
                    return _reject(f"unknown column {ref}")
                if ref not in read:
                    read.append(ref)

    # 5. sensitive columns
    for ref in read:
        level = policy.sensitive.get(ref)
        if level and level not in sees:
            return _reject(f"column {ref} is {level}; role {role} may not see it")

    # 7. LIMIT on the outermost query
    changes = []
    limit = tree.args.get("limit")
    if limit is None:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(policy.row_limit)))
        changes.append(f"added LIMIT {policy.row_limit}")
    else:
        value = limit.expression
        if not (isinstance(value, exp.Literal) and not value.is_string and value.this.isdigit()):
            return _reject("LIMIT must be a plain integer")
        if int(value.this) > policy.row_limit:
            limit.set("expression", exp.Literal.number(policy.row_limit))
            changes.append(f"lowered LIMIT {value.this} to {policy.row_limit}")
    return GuardResult(ok=True, sql=tree.sql(dialect=DIALECT), tables=used_tables, columns=read,
                       changes=changes)

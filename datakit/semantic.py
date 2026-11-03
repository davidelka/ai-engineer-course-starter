"""The semantic layer (lesson 8): load it, validate it, render it for an LLM, and turn it
into the SQL guard's policy.

    from datakit.semantic import load_layer, render_context, policy_from_layer
    layer = load_layer()                         # datakit/data/acme_semantic.yaml
    text = render_context(layer, role="analyst") # compact context for the prompt
    policy = policy_from_layer(layer)            # allow-lists, sensitivities, roles

One file, three readers: the model (context), the guard (policy) and people (docs).
When they disagree, the file wins, so there is exactly one place to fix a definition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_LAYER = Path(__file__).resolve().parent / "data" / "acme_semantic.yaml"
Sensitivity = Literal["none", "pii", "financial"]


class Column(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = "text"
    description: str = ""
    values: Optional[list[Union[str, int]]] = None
    sensitivity: Sensitivity = "none"


class Table(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    grain: str = ""
    primary_key: str
    source: str = ""
    freshness_hours: int = 24
    columns: dict[str, Column]

    @model_validator(mode="after")
    def _pk_exists(self):
        if self.primary_key not in self.columns:
            raise ValueError(f"primary_key {self.primary_key!r} is not one of the columns")
        return self


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    from_: str = Field(alias="from")
    to: str
    kind: Literal["many_to_one", "one_to_one", "one_to_many", "many_to_many"] = "many_to_one"
    note: str = ""


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term: str
    synonyms: list[str] = []
    means: str


class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    synonyms: list[str] = []
    table: str
    expr: str
    filter: str = ""
    description: str = ""
    format: str = ""


class RoleDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = ""
    tables: Union[Literal["all"], list[str]] = "all"
    sees: list[Literal["pii", "financial"]] = []
    row_policy: dict[str, str] = {}


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    row_limit: int = 200
    timeout_ms: int = 2000


class VerifiedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    sql: str


class Layer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    name: str
    description: str = ""
    dialect: str = "sqlite"
    today: str = ""
    conventions: list[str] = []
    tables: dict[str, Table]
    relationships: list[Relationship] = []
    terms: list[Term] = []
    metrics: list[Metric] = []
    roles: dict[str, RoleDef] = {}
    limits: Limits = Limits()
    verified_queries: list[VerifiedQuery] = []

    @field_validator("tables")
    @classmethod
    def _lower_names(cls, v):
        return {k.lower(): t for k, t in v.items()}

    @model_validator(mode="after")
    def _references_exist(self):
        """Every join, metric and role must point at tables/columns that exist."""
        problems = []

        def col_ok(ref: str) -> bool:
            t, _, c = ref.partition(".")
            return t in self.tables and c in self.tables[t].columns

        for r in self.relationships:
            for ref in (r.from_, r.to):
                if not col_ok(ref):
                    problems.append(f"relationship {r.from_} -> {r.to}: unknown column {ref}")
        for m in self.metrics:
            if m.table not in self.tables:
                problems.append(f"metric {m.name}: unknown table {m.table}")
        for name, role in self.roles.items():
            tabs = [] if role.tables == "all" else role.tables
            for t in list(tabs) + list(role.row_policy):
                if t not in self.tables:
                    problems.append(f"role {name}: unknown table {t}")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    # convenience
    def role(self, name: str) -> RoleDef:
        if name not in self.roles:
            raise KeyError(f"unknown role {name!r}; roles: {', '.join(self.roles)}")
        return self.roles[name]

    def tables_for(self, role: Optional[str]) -> list[str]:
        if role is None:
            return list(self.tables)
        r = self.role(role)
        return list(self.tables) if r.tables == "all" else [t for t in self.tables if t in r.tables]


def load_layer(path: Union[str, Path, None] = None) -> Layer:
    """Read and validate a semantic-layer YAML. Raises pydantic.ValidationError with
    precise locations when the file is malformed."""
    p = Path(path) if path else DEFAULT_LAYER
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Layer.model_validate(data)


# ------------------------------------------------------------------ rendering
def render_context(layer: Layer, role: Optional[str] = None, tables: Optional[list[str]] = None,
                   include_values: bool = True, include_examples: bool = True) -> str:
    """Render the layer as compact text for a prompt.

    - Only the tables the role may query (and, if given, only `tables`): the model
      should not even see what it is not allowed to use.
    - Columns the role may not see are omitted, so the model is not tempted.
    - One line per column, `values` inline for enums: enums prevent 'Enterprise' vs 'enterprise'.
    - Join paths, business terms and metrics follow, then verified examples.
    """
    allowed = layer.tables_for(role)
    if tables:
        wanted = {t.lower() for t in tables}
        allowed = [t for t in allowed if t in wanted]
    sees = set(layer.role(role).sees) if role else {"pii", "financial"}
    out = [f"# Database: {layer.name} ({layer.dialect}). {layer.description}".strip()]
    if layer.today:
        out.append(f"Today is {layer.today}.")
    for c in layer.conventions:
        out.append(f"- {c}")
    out.append("")
    out.append("## Tables")
    for tname in allowed:
        t = layer.tables[tname]
        out.append(f"### {tname}  ({t.grain or 'rows'}; pk {t.primary_key}) - {t.description}")
        for cname, c in t.columns.items():
            if c.sensitivity != "none" and c.sensitivity not in sees:
                continue
            bits = [f"- {cname} {c.type}"]
            if c.description:
                bits.append(f": {c.description}")
            if include_values and c.values:
                bits.append(f" [values: {', '.join(str(v) for v in c.values)}]")
            out.append("".join(bits))
    rels = [r for r in layer.relationships
            if r.from_.split(".")[0] in allowed and r.to.split(".")[0] in allowed]
    if rels:
        out.append("")
        out.append("## Join paths (use only these)")
        for r in rels:
            out.append(f"- {r.from_} = {r.to}" + (f"  ({r.note})" if r.note else ""))
    terms = layer.terms
    if terms:
        out.append("")
        out.append("## Business terms")
        for term in terms:
            syn = f" (also: {', '.join(term.synonyms)})" if term.synonyms else ""
            out.append(f"- {term.term}{syn}: {term.means}")
    mets = [m for m in layer.metrics if m.table in allowed]
    if mets:
        out.append("")
        out.append("## Metrics (use these exact definitions)")
        for m in mets:
            where = f" WHERE {m.filter}" if m.filter else ""
            syn = f" (also: {', '.join(m.synonyms)})" if m.synonyms else ""
            out.append(f"- {m.name}{syn} = {m.expr} FROM {m.table}{where}. {m.description}".rstrip())
    if include_examples and layer.verified_queries:
        out.append("")
        out.append("## Verified examples")
        for v in layer.verified_queries:
            out.append(f"Q: {v.question}\nSQL: {v.sql}")
    return "\n".join(out).strip() + "\n"


def render_ddl(db_path: Union[str, Path]) -> str:
    """The naive alternative, for comparison: raw CREATE TABLE statements from the database."""
    import sqlite3

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL").fetchall()
    finally:
        con.close()
    return "\n".join(r[0] + ";" for r in rows) + "\n"


# ------------------------------------------------------------------ policy
def policy_from_layer(layer: Layer):
    """Build the guard's Policy (datakit.guard.Policy) from the layer."""
    from .guard import Policy

    columns = {t: list(tab.columns) + ["_source_system", "_extracted_at"] for t, tab in layer.tables.items()}
    sensitive = {}
    for t, tab in layer.tables.items():
        for c, col in tab.columns.items():
            if col.sensitivity != "none":
                sensitive[f"{t}.{c}"] = col.sensitivity
    roles = {}
    for name, r in layer.roles.items():
        roles[name] = {"tables": layer.tables_for(name), "sees": list(r.sees)}
    return Policy(columns=columns, sensitive=sensitive, roles=roles, row_limit=layer.limits.row_limit)

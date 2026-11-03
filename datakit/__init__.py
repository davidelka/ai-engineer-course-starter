"""datakit: structured enterprise data for LLM systems (lesson 8).

- semantic   the semantic layer: YAML -> validated model -> LLM context + guard policy
- guard      SQL guard on the syntax tree (sqlglot): SELECT only, allow-lists, sensitive
             columns by role, LIMIT
- rls        row-level security by rewriting table references into filtered subqueries
- db         read-only SQLite connection, timeout, row cap, column authorizer
- provenance sources, extraction times and the row ids behind an answer
- freshness  stale-data detection from _extracted_at and the provenance table
- evaluate   execution accuracy: compare result sets, not SQL text
- text2sql   the whole loop: question -> SQLPlan -> guard -> execute -> answer with provenance

Works on data/acme/corpus/structured/acme.db. Lesson 9 (ragkit) handles documents.
"""

from .db import DEFAULT_DB, QueryResult, QueryTimeout, connect_ro, run_query
from .evaluate import results_match
from .freshness import Freshness, freshness_report
from .guard import GuardResult, Policy, guard_sql
from .rls import apply_row_policy
from .semantic import DEFAULT_LAYER, Layer, load_layer, policy_from_layer, render_context

__all__ = [
    "DEFAULT_DB", "QueryResult", "QueryTimeout", "connect_ro", "run_query", "results_match",
    "Freshness", "freshness_report", "GuardResult", "Policy", "guard_sql", "apply_row_policy",
    "DEFAULT_LAYER", "Layer", "load_layer", "policy_from_layer", "render_context",
]

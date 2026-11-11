"""The retriever stack and the access rules.

    stack = build_retriever(job, settings)          # rerank? ( versions( hybrid(bm25, dense) ) )
    hits = stack.search(question, k=30, where=acl_filter("support"))

Every layer is a ragkit retriever with search(query, k, where), so the same object serves the
assistant, the ablation and the evaluation. The order matters:

1. ACL first, as a `where` that every inner retriever applies BEFORE ranking (lesson 11:
   acl_where(role)). Filtering after the top-k would leak through the ranking and silently
   return fewer results. BM25Index and NumpyVectorStore understand only plain filters, so the
   ACL dict ($or ...) is turned into a callable with filters.as_callable.
2. Hybrid: BM25 and dense, fused with RRF (k=60). Each child is asked for the same depth.
3. Versions: drop a chunk when a newer version of its document is ALSO in the candidates
   ("retrieved" mode, the safe default; "corpus" hides superseded documents altogether).
4. Rerank (optional): re-score the first 30 candidates. "fake" is a lexical stand-in that runs
   anywhere; ce:bge-m3 is a real cross-encoder (a 2.3 GB download, measure it live).
"""

from __future__ import annotations

from typing import Any

from ragkit.types import Chunk
from ragkit.vectors.filters import ROLES, acl_where, as_callable, matches_ext

ROLE_LABELS = {
    "employee": "עובד/ת (ללא מחלקה)",
    "engineering": "הנדסה",
    "support": "תמיכה ומכירות",
    "hr": "משאבי אנוש",
    "finance": "כספים",
    "security": "אבטחת מידע",
    "contractor": "קבלן חיצוני",
}


def acl_filter(role: str) -> Any:
    """The `where` for a role, in a form every ragkit retriever understands."""
    return as_callable(acl_where(role))


def doc_visible(role: str, meta: dict) -> bool:
    """Same rule as the retrieval filter, for a whole document (GET /docs/{id})."""
    return matches_ext(Chunk(id="", doc_id="", text="", start=0, end=0, meta=meta), acl_where(role))


def visible_docs(role: str, docs: dict) -> list[str]:
    return sorted(d for d, sd in docs.items() if doc_visible(role, sd.meta))


def build_retriever(*args, **kwargs):
    """Milestone 3: runs your mine.build_retriever (see acmeqa/hooks.py)."""
    from .hooks import call
    return call("build_retriever", *args, **kwargs)


__all__ = ["ROLES", "ROLE_LABELS", "acl_filter", "doc_visible", "visible_docs", "build_retriever"]

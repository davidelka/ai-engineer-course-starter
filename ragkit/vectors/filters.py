"""Metadata filters for vector databases (lesson 11): one filter language, four dialects.

ragkit's `where` (ragkit.retrieval.base.matches) is the contract every store honours:
    {"language": "he"}                               equality
    {"classification": ["public", "internal"]}       membership
    {"effective_date": {"$gte": "2026-01-01"}}       comparison ($gte $gt $lte $lt $ne)
Lesson 11 adds boolean structure, because real access rules need it (lesson 24's ACL matrix
says "public or internal, OR confidential AND my department"):
    {"$or": [where, where, ...]}                     any branch matches
    {"$and": [where, where, ...]}                    every branch matches
    {"tags": {"$contains": "x"}}                     a list-valued field contains x
    {"k": {"$in": [...]}} / {"k": {"$nin": [...]}}   explicit membership / exclusion
Keys inside one dict are ANDed, exactly like matches().

This module translates that language into:
    matches_ext(chunk, where)      Python (exact baseline; NumpyVectorStore takes it as a callable)
    to_qdrant_filter(where)        qdrant_client.models.Filter (payload filter)
    to_sql_where(where)            (sql, params) for the pgvector table of PgVectorStore
    to_s3vectors_filter(where)     the JSON filter document of Amazon S3 Vectors QueryVectors

and gives the role-based access filter of Company Brain:
    acl_where(role)                same matrix as guardkit.acl (lesson 24), as a `where`

Every translator FAILS CLOSED: an operator it does not know raises ValueError instead of
silently dropping a condition (a dropped ACL condition is a data leak, not a bug report).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ..retrieval.base import OPS as _BASE_OPS
from ..retrieval.base import Where, matches
from ..types import Chunk

# Fields that live on the Chunk itself rather than in chunk.meta.
CHUNK_FIELDS = ("doc_id", "id", "index", "n_tokens", "section")
BOOL_KEYS = ("$or", "$and")
FIELD_OPS = ("$gte", "$gt", "$lte", "$lt", "$ne", "$in", "$nin", "$contains")

# ---------------------------------------------------------------- the ACL matrix (lesson 24)
# Same rules as guardkit/acl.py, restated here so ragkit does not import guardkit:
#   public        every role, including contractor
#   internal      every role except contractor
#   confidential  security, or a role whose department equals the document's department
#   anything else (restricted, missing, unknown role) -> denied
ROLE_DEPARTMENT = {"engineering": "engineering", "support": "sales_support", "hr": "hr",
                   "finance": "finance", "security": None, "employee": None, "contractor": None}
ROLES = tuple(ROLE_DEPARTMENT)


def acl_where(role: str) -> dict:
    """The `where` that lets `role` see exactly the chunks the ACL matrix allows.

        acl_where("contractor") -> {"classification": ["public"]}
        acl_where("security")   -> {"classification": ["public", "internal", "confidential"]}
        acl_where("engineering")-> {"$or": [{"classification": ["public", "internal"]},
                                            {"classification": "confidential",
                                             "department": "engineering"}]}
    An unknown role gets a filter that matches nothing (fail closed).
    """
    if role not in ROLE_DEPARTMENT:
        return {"classification": []}                       # membership in an empty list: nothing
    if role == "contractor":
        return {"classification": ["public"]}
    if role == "security":
        return {"classification": ["public", "internal", "confidential"]}
    dept = ROLE_DEPARTMENT[role]
    if dept is None:
        return {"classification": ["public", "internal"]}
    return {"$or": [{"classification": ["public", "internal"]},
                    {"classification": "confidential", "department": dept}]}


# ---------------------------------------------------------------- Python (exact baseline)
def _value(chunk: Chunk, key: str):
    if key in ("doc_id", "id", "index", "n_tokens"):
        return getattr(chunk, key)
    if key == "section":
        return chunk.section
    return chunk.meta.get(key)


def _check_ops(cond: dict) -> None:
    bad = [op for op in cond if op not in FIELD_OPS]
    if bad:
        raise ValueError(f"unknown filter operator(s) {bad}; known: {FIELD_OPS}")


def matches_ext(chunk: Chunk, where: Where) -> bool:
    """matches() plus $or / $and / $in / $nin / $contains. Unknown operators raise."""
    if where is None:
        return True
    if callable(where):
        return bool(where(chunk))
    for key, cond in where.items():
        if key == "$or":
            if not any(matches_ext(chunk, w) for w in cond):
                return False
            continue
        if key == "$and":
            if not all(matches_ext(chunk, w) for w in cond):
                return False
            continue
        if key.startswith("$"):
            raise ValueError(f"unknown boolean key {key!r}; known: {BOOL_KEYS}")
        v = _value(chunk, key)
        if isinstance(cond, dict):
            _check_ops(cond)
            for op, arg in cond.items():
                if op == "$in":
                    ok = v in arg
                elif op == "$nin":
                    ok = v not in arg
                elif op == "$contains":
                    ok = isinstance(v, (list, tuple, set)) and arg in v
                else:
                    ok = _BASE_OPS[op](v, arg)
                if not ok:
                    return False
        elif isinstance(cond, (list, tuple, set, frozenset)):
            if v not in cond:
                return False
        elif v != cond:
            return False
    return True


def as_callable(where: Where) -> Optional[Callable[[Chunk], bool]]:
    """A callable for stores that only understand matches() (NumpyVectorStore, FaissVectorStore).
    Plain dicts without lesson-11 operators are passed through unchanged."""
    if where is None or callable(where):
        return where
    if _is_basic(where):
        return where  # type: ignore[return-value]
    return lambda c: matches_ext(c, where)


def _is_basic(where: dict) -> bool:
    for key, cond in where.items():
        if key.startswith("$"):
            return False
        if isinstance(cond, dict) and any(op in ("$in", "$nin", "$contains") for op in cond):
            return False
    return True


# ---------------------------------------------------------------- Qdrant
def payload_key(key: str) -> str:
    """Where a `where` key lives in a Qdrant point payload (see QdrantVectorStore)."""
    return key


def to_qdrant_filter(where: Where):
    """Translate a dict `where` into qdrant_client.models.Filter (None -> None).

    equality -> FieldCondition(match=MatchValue); a list -> MatchAny (an empty list matches
    nothing: we emit a condition on an impossible value, never "no condition");
    $gte.. -> Range (numbers) or DatetimeRange-free string comparison is NOT supported by
    Qdrant Range on keyword fields, so string ranges (ISO dates) use DatetimeRange;
    $ne -> must_not MatchValue; $nin -> must_not MatchAny; $contains -> MatchValue on an
    array payload (Qdrant matches an array if ANY element matches);
    $or -> should (with min_should 1 semantics: Qdrant's `should` = at least one);
    $and -> nested must.
    """
    if where is None:
        return None
    if callable(where):
        raise ValueError("a callable `where` cannot be sent to Qdrant; use a dict filter")
    from qdrant_client import models  # lazy: only needed with Qdrant

    must, must_not = [], []
    for key, cond in where.items():
        if key == "$or":
            must.append(models.Filter(should=[to_qdrant_filter(w) for w in cond] or
                                      [_nothing(models)]))
            continue
        if key == "$and":
            must.append(models.Filter(must=[to_qdrant_filter(w) for w in cond]))
            continue
        if key.startswith("$"):
            raise ValueError(f"unknown boolean key {key!r}; known: {BOOL_KEYS}")
        k = payload_key(key)
        if isinstance(cond, dict):
            _check_ops(cond)
            rng: dict[str, Any] = {}
            for op, arg in cond.items():
                if op == "$ne":
                    must_not.append(models.FieldCondition(key=k, match=models.MatchValue(value=arg)))
                elif op == "$nin":
                    must_not.append(models.FieldCondition(key=k, match=models.MatchAny(any=list(arg))))
                elif op == "$in":
                    must.append(_any(models, k, list(arg)))
                elif op == "$contains":
                    must.append(models.FieldCondition(key=k, match=models.MatchValue(value=arg)))
                else:
                    rng[op[1:]] = arg
            if rng:
                if all(isinstance(a, (int, float)) for a in rng.values()):
                    must.append(models.FieldCondition(key=k, range=models.Range(**rng)))
                else:
                    must.append(models.FieldCondition(key=k, range=models.DatetimeRange(**rng)))
        elif isinstance(cond, (list, tuple, set, frozenset)):
            must.append(_any(models, k, list(cond)))
        else:
            must.append(models.FieldCondition(key=k, match=models.MatchValue(value=cond)))
    return models.Filter(must=must or None, must_not=must_not or None)


_IMPOSSIBLE = "\x00ragkit-matches-nothing\x00"


def _nothing(models):
    return models.FieldCondition(key="doc_id", match=models.MatchValue(value=_IMPOSSIBLE))


def _any(models, key: str, values: list):
    if not values:
        return models.FieldCondition(key=key, match=models.MatchValue(value=_IMPOSSIBLE))
    return models.FieldCondition(key=key, match=models.MatchAny(any=values))


# ---------------------------------------------------------------- PostgreSQL / pgvector
SQL_COLUMNS = {"doc_id": "doc_id", "id": "id"}
_SQL_CMP = {"$gte": ">=", "$gt": ">", "$lte": "<=", "$lt": "<", "$ne": "IS DISTINCT FROM"}


def _sql_field(key: str, arg: Any = None) -> str:
    if key in SQL_COLUMNS:
        return SQL_COLUMNS[key]
    if not key.replace("_", "").isalnum():
        raise ValueError(f"unsafe metadata key {key!r}")   # keys are inlined; values never are
    # Numbers are compared as numbers, everything else as text (ISO dates sort correctly).
    if isinstance(arg, bool):
        return f"(meta->>'{key}')::boolean"
    if isinstance(arg, (int, float)):
        return f"(meta->>'{key}')::numeric"
    return f"(meta->>'{key}')"


def to_sql_where(where: Where) -> tuple[str, list]:
    """Translate a dict `where` into ("<sql boolean expression>", [params]) for psycopg.

    Values are ALWAYS bound parameters (%s); only whitelisted-shape keys are inlined.
    None -> ("TRUE", []). Metadata lives in a jsonb column `meta`; doc_id and id are columns.
    """
    if where is None:
        return "TRUE", []
    if callable(where):
        raise ValueError("a callable `where` cannot be sent to PostgreSQL; use a dict filter")
    parts: list[str] = []
    params: list = []
    for key, cond in where.items():
        if key in BOOL_KEYS:
            subs = [to_sql_where(w) for w in cond]
            if not subs:
                parts.append("FALSE" if key == "$or" else "TRUE")
                continue
            joiner = " OR " if key == "$or" else " AND "
            parts.append("(" + joiner.join(f"({s})" if " AND " in s or " OR " in s else s
                                          for s, _ in subs) + ")")
            for _, p in subs:
                params.extend(p)
            continue
        if key.startswith("$"):
            raise ValueError(f"unknown boolean key {key!r}; known: {BOOL_KEYS}")
        if isinstance(cond, dict):
            _check_ops(cond)
            for op, arg in cond.items():
                if op in ("$in", "$nin"):
                    vals = [str(a) for a in arg]
                    f = _sql_field(key)
                    if op == "$in":
                        parts.append(f"({f} = ANY(%s))" if vals else "FALSE")
                    else:   # a missing key is "not in the list" (same as matches_ext)
                        parts.append(f"({f} IS NULL OR NOT ({f} = ANY(%s)))" if vals else "TRUE")
                    if vals:
                        params.append(vals)
                elif op == "$contains":
                    if key in SQL_COLUMNS:
                        raise ValueError(f"$contains needs a list-valued metadata key, not {key!r}")
                    parts.append(f"(meta->'{key}' ? %s)")
                    params.append(str(arg))
                else:
                    parts.append(f"({_sql_field(key, arg)} {_SQL_CMP[op]} %s)")
                    params.append(arg)
        elif isinstance(cond, (list, tuple, set, frozenset)):
            vals = [str(v) for v in cond]
            if not vals:
                parts.append("FALSE")
            else:
                parts.append(f"({_sql_field(key)} = ANY(%s))")
                params.append(vals)
        else:
            parts.append(f"({_sql_field(key, cond)} = %s)")
            params.append(cond)
    return (" AND ".join(parts) if parts else "TRUE"), params


# ---------------------------------------------------------------- Amazon S3 Vectors
def to_s3vectors_filter(where: Where) -> Optional[dict]:
    """Translate into the S3 Vectors QueryVectors `filter` document.

    S3 Vectors uses MongoDB-style operators: $eq $ne $gt $gte $lt $lte $in $nin $exists
    $and $or (and $startsWith). Equality is {"k": v}, membership {"k": {"$in": [...]}}.
    Keys must be FILTERABLE metadata of the index (non-filterable keys -> 400 Bad Request).
    $contains maps to $eq: S3 Vectors list metadata matches if any element equals.
    """
    if where is None:
        return None
    if callable(where):
        raise ValueError("a callable `where` cannot be sent to S3 Vectors; use a dict filter")
    clauses: list[dict] = []
    for key, cond in where.items():
        if key in BOOL_KEYS:
            subs = [to_s3vectors_filter(w) for w in cond]
            if not subs:
                clauses.append({"doc_id": {"$in": [_IMPOSSIBLE]}} if key == "$or" else {})
                continue
            clauses.append({key: subs})
            continue
        if key.startswith("$"):
            raise ValueError(f"unknown boolean key {key!r}; known: {BOOL_KEYS}")
        if isinstance(cond, dict):
            _check_ops(cond)
            ops = {}
            for op, arg in cond.items():
                if op == "$contains":
                    ops["$eq"] = arg
                elif op in ("$in", "$nin"):
                    ops[op] = list(arg) or [_IMPOSSIBLE]
                else:
                    ops[op] = arg
            clauses.append({key: ops})
        elif isinstance(cond, (list, tuple, set, frozenset)):
            clauses.append({key: {"$in": list(cond) or [_IMPOSSIBLE]}})
        else:
            clauses.append({key: {"$eq": cond}})
    clauses = [c for c in clauses if c]
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


__all__ = ["acl_where", "ROLES", "ROLE_DEPARTMENT", "matches_ext", "as_callable", "to_qdrant_filter",
           "to_sql_where", "to_s3vectors_filter", "matches"]

"""Exercise 6: acl_where in mine.py. The data is the real Acme corpus (55 documents)."""

import pytest

import mine
from ragkit.types import Chunk
from ragkit.vectors.filters import matches_ext, to_s3vectors_filter, to_sql_where

ROLES = ["engineering", "support", "hr", "finance", "security", "employee", "contractor"]
DEPT = {"engineering": "engineering", "support": "sales_support", "hr": "hr", "finance": "finance"}


def allowed(role, meta):
    """The matrix, written the long way."""
    cls = str(meta.get("classification") or "")
    if role not in ROLES:
        return False
    if cls == "public":
        return True
    if cls == "internal":
        return role != "contractor"
    if cls == "confidential":
        return role == "security" or (role in DEPT and DEPT[role] == meta.get("department"))
    return False


def fake_chunks():
    out = []
    for cls in ["public", "internal", "confidential", "restricted", "", None, "Confidential "]:
        for dept in ["engineering", "sales_support", "hr", "finance", "company", None]:
            meta = {"classification": cls, "department": dept}
            out.append(Chunk(id=f"{cls}-{dept}#0", doc_id=f"{cls}-{dept}", text="x", start=0, end=1, meta=meta))
    return out


@pytest.mark.parametrize("role", ROLES + ["intern", ""])
def test_matrix_on_synthetic_metadata(role):
    w = mine.acl_where(role)
    for c in fake_chunks():
        assert matches_ext(c, w) == allowed(role, c.meta), (role, c.meta)


@pytest.mark.parametrize("role", ROLES)
def test_matrix_on_the_acme_corpus(role, chunks):
    w = mine.acl_where(role)
    got = {c.doc_id for c in chunks if matches_ext(c, w)}
    want = {c.doc_id for c in chunks if allowed(role, c.meta)}
    assert got == want


def test_who_sees_the_postmortems(chunks):
    pm = {"eng-pm-2026-03-scheduler", "eng-pm-2026-06-billing", "eng-pm-2026-08-api"}
    seen = {r: {c.doc_id for c in chunks if matches_ext(c, mine.acl_where(r))} for r in ROLES}
    assert pm <= seen["engineering"] and pm <= seen["security"]
    for r in ("support", "hr", "finance", "employee", "contractor"):
        assert not (pm & seen[r]), r
    assert "hr-relocation" in seen["hr"] and "hr-relocation" not in seen["engineering"]
    assert len(seen["contractor"]) == 4


@pytest.mark.parametrize("role", ROLES + ["intern"])
def test_filter_translates_to_every_backend(role):
    w = mine.acl_where(role)
    assert isinstance(w, dict) and not callable(w), "a callable cannot be sent to a database"
    sql, params = to_sql_where(w)
    assert "%s" in sql or sql in ("FALSE", "TRUE") or "FALSE" in sql
    assert to_s3vectors_filter(w) is not None


def test_filter_runs_in_qdrant(chunks):
    pytest.importorskip("qdrant_client")
    import numpy as np

    from ragkit.vectors.qdrant_store import QdrantVectorStore
    rng = np.random.default_rng(0)
    vecs = rng.normal(size=(len(chunks), 16)).astype("float32")
    store = QdrantVectorStore(collection="acl_test")
    store.add(chunks, vecs)
    for role in ("engineering", "contractor", "hr"):
        hits = store.search(vecs[0], k=len(chunks), where=mine.acl_where(role))
        assert {h.chunk.doc_id for h in hits} == {c.doc_id for c in chunks if allowed(role, c.meta)}

"""Exercise 6: multi-tenant access control inside the vector database.

    python labs/11-managed-vectors/acl_demo.py                    # reference acl_where, Qdrant in-process
    python labs/11-managed-vectors/acl_demo.py --mine             # YOUR mine.acl_where
    python labs/11-managed-vectors/acl_demo.py --qdrant           # the docker compose Qdrant
    python labs/11-managed-vectors/acl_demo.py --model fake       # offline

The data (printed first): the Acme corpus has 55 documents: 47 internal, 4 public and 4
confidential (three engineering postmortems and the HR relocation policy). Seven roles; the
matrix is lesson 24's (guardkit/acl.py):
  public        every role, including contractor
  internal      every role except contractor
  confidential  security, or the role whose department owns the document
                (engineering -> engineering, support -> sales_support, hr -> hr, finance -> finance)
The script then:
  1. shows, per role, the filter acl_where(role) and how it looks in Qdrant, SQL and S3 Vectors;
  2. runs two questions per role through Qdrant WITH the filter in the query (pre-ranking);
  3. checks all 79 golden questions x 7 roles: zero forbidden chunks returned, and the same
     top-10 as an exact search over the allowed chunks only;
  4. shows the wrong way, post-filtering in application code: fetch top 5, drop forbidden
     ones -> the contractor gets fewer results (and the ranking leaked that confidential
     documents about the topic exist).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from common import DEFAULT_MODEL, QDRANT_URL, acme_vectors, numpy_store  # noqa: E402
from ragkit.vectors.filters import (ROLES, as_callable, matches_ext, to_qdrant_filter,  # noqa: E402
                                    to_s3vectors_filter, to_sql_where)

QUESTIONS = ["What caused the August 2026 flow-api outage, and how long did it last?",
             "How much does Acme pay toward relocation to the Berlin office?"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--qdrant", nargs="?", const=QDRANT_URL)
    ap.add_argument("--mine", action="store_true")
    a = ap.parse_args()
    if a.mine:
        import mine
        try:
            mine.acl_where("hr")
        except NotImplementedError:
            sys.exit("implement mine.acl_where first (exercise 6)")
        acl_where = mine.acl_where
    else:
        from ragkit.vectors.filters import acl_where

    ch, vecs, qa, qv = acme_vectors(a.model)
    docs = {c.doc_id: c.meta for c in ch}
    print("== the data")
    print("  classification of the 55 documents:", dict(Counter(m.get("classification") for m in docs.values())))
    for d, m in sorted(docs.items()):
        if m.get("classification") != "internal":
            print(f"  {m.get('classification'):<13} {m.get('department'):<14} {d:<28} {m.get('title')}")

    print("\n== 1. the filter per role")
    for r in ROLES:
        w = acl_where(r)
        n_docs = sum(1 for m in docs.values() if matches_ext(type(ch[0])(id="x", doc_id="x", text="", start=0, end=0, meta=m), w))
        print(f"  {r:<12} sees {n_docs:>2} documents   where={json.dumps(w)}")
    w = acl_where("engineering")
    sql, params = to_sql_where(w)
    print(f"\n  engineering in SQL:        WHERE {sql}    params={params}")
    print(f"  engineering in S3 Vectors: {json.dumps(to_s3vectors_filter(w))}")
    try:
        print(f"  engineering in Qdrant:     {to_qdrant_filter(w).model_dump(exclude_none=True)}")
    except ImportError:
        pass

    from ragkit.vectors.qdrant_store import QdrantVectorStore
    store = QdrantVectorStore(url=a.qdrant, collection="acme_acl", recreate=True)
    store.add(ch, vecs)
    base = numpy_store(ch, vecs)
    emb_q = __import__("common").embedder(a.model).embed_queries(QUESTIONS)

    print("\n== 2. two questions, top 3 per role (filter inside the query)")
    for qi, question in enumerate(QUESTIONS):
        print(f"\n  Q: {question}")
        for r in ROLES:
            hits = store.search(emb_q[qi], k=3, where=acl_where(r))
            print(f"    {r:<12} " + ", ".join(f"{h.chunk.doc_id}[{h.chunk.classification[:4]}]" for h in hits))

    print("\n== 3. all golden questions x all roles")
    bad = mismatch = 0
    for r in ROLES:
        w = acl_where(r)
        for v in qv:
            got = store.search(v, k=10, where=w)
            bad += sum(1 for h in got if not _truth(r, h.chunk.meta))
            want = [h.chunk.id for h in base.search(v, k=10, where=lambda c, r=r: _truth(r, c.meta))]
            mismatch += {h.chunk.id for h in got} != set(want)     # same set (ties may swap order)
    print(f"  forbidden chunks returned: {bad}   top-10 different from exact-over-allowed: {mismatch} "
          f"(of {len(ROLES) * len(qv)} searches)")

    print("\n== 4. the wrong way: post-filter top 5 in application code (contractor)")
    for qi, question in enumerate(QUESTIONS):
        top = base.search(emb_q[qi], k=5)
        kept = [h for h in top if _truth("contractor", h.chunk.meta)]
        print(f"  Q{qi + 1}: fetched 5, kept {len(kept)}; dropped: "
              + ", ".join(f"{h.chunk.doc_id}[{h.chunk.classification}]" for h in top if h not in kept))
    print("  -> fewer answers, and the gap itself tells the user that hidden documents exist.")
    if store.local:
        print("\nnote: in-process Qdrant. For the real thing: --qdrant (filter on indexed payload).")
    _ = as_callable


def _truth(role: str, meta: dict) -> bool:
    """The matrix, independent of acl_where (used to check it)."""
    dept = {"engineering": "engineering", "support": "sales_support", "hr": "hr", "finance": "finance"}
    cls = meta.get("classification")
    if role not in ROLES:
        return False
    if cls == "public":
        return True
    if cls == "internal":
        return role != "contractor"
    if cls == "confidential":
        return role == "security" or (role in dept and dept[role] == meta.get("department"))
    return False


if __name__ == "__main__":
    main()

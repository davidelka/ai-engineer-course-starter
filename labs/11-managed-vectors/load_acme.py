"""Exercise 4: load the Acme corpus into Qdrant and pgvector, and check them against lesson
10's exact NumpyVectorStore on the 79 golden questions.

    python labs/11-managed-vectors/load_acme.py                         # Qdrant in-process (exact!)
    python labs/11-managed-vectors/load_acme.py --qdrant --pgvector     # the docker compose servers
    python labs/11-managed-vectors/load_acme.py --model fake            # offline, no model download
    python labs/11-managed-vectors/load_acme.py --qdrant --where language=he --show q039

The same embeddings go into every store (lesson 10's cache: nothing is re-embedded). For each
store the script reports:
  agree@10   share of the exact top-10 chunks (numpy) that the store also returned
             (1.000 = identical; HNSW on 210 points should be 1.000: the graph is tiny)
  R@5 / MRR  document-level retrieval quality on the 69 answerable golden questions
             (lesson 10's metrics). Equal agree@10 => equal R@5. If they differ, a store
             returned different chunks, and the quality numbers tell you whether it matters.
  load / query  seconds to upsert 210 chunks, mean ms per query (embedding excluded)
It then runs the incremental-update cycle every production index needs: remove one document,
re-add it with changed text, and checks the store and the baseline still agree.
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from common import DEFAULT_MODEL, PG_DSN, QDRANT_URL, acme_vectors, numpy_store  # noqa: E402
from ragkit.metrics import dedupe, recall_at_k, reciprocal_rank  # noqa: E402


def parse_where(items):
    if not items:
        return None
    w = {}
    for it in items:
        k, _, v = it.partition("=")
        w[k] = v.split("|") if "|" in v else v
    return w


def evaluate(store, qa, qv, base, where, k=10):
    agree, r5, rr, t = [], [], [], 0.0
    for q, v in zip(qa, qv):
        t0 = time.perf_counter()
        hits = store.search(v, k=30, where=where)
        t += time.perf_counter() - t0
        ids = [h.chunk.id for h in hits[:k]]
        ref = [h.chunk.id for h in base.search(v, k=k, where=where)]
        agree.append(len(set(ids) & set(ref)) / max(1, len(ref)))
        if q.get("source_ids"):
            docs = dedupe(h.chunk.doc_id for h in hits)
            r5.append(recall_at_k(docs, q["source_ids"], 5))
            rr.append(reciprocal_rank(docs, q["source_ids"], 10))
    return {"agree": float(np.mean(agree)), "r5": float(np.mean(r5)), "mrr": float(np.mean(rr)),
            "ms": t / len(qa) * 1000}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL, help="embedder spec (lesson 10), or 'fake'")
    ap.add_argument("--qdrant", nargs="?", const=QDRANT_URL, help="Qdrant server URL (default: in-process)")
    ap.add_argument("--pgvector", nargs="?", const=PG_DSN, help="PostgreSQL DSN with pgvector")
    ap.add_argument("--quantization", choices=["scalar", "binary", "product"], help="Qdrant quantization")
    ap.add_argument("--where", action="append", help="metadata filter key=value (value a|b = one of)")
    ap.add_argument("--show", help="print the top 5 of every store for this golden question id")
    a = ap.parse_args()

    ch, vecs, qa, qv = acme_vectors(a.model)
    where = parse_where(a.where)
    base = numpy_store(ch, vecs)
    stores = {"numpy (exact)": base}

    from ragkit.vectors.qdrant_store import QdrantVectorStore
    t0 = time.perf_counter()
    q = QdrantVectorStore(url=a.qdrant, collection=f"acme_{a.model.replace(':', '_').replace('-', '_')}",
                          recreate=True, quantization=a.quantization, oversampling=2.0 if a.quantization else None)
    q.add(ch, vecs)
    loads = {"qdrant": time.perf_counter() - t0}
    stores["qdrant" + (" (in-process: exact)" if q.local else f" ({a.qdrant})")] = q
    if a.pgvector:
        from ragkit.vectors.pgvector_store import PgVectorStore
        t0 = time.perf_counter()
        p = PgVectorStore(a.pgvector, table="acme_chunks", recreate=True, index="hnsw",
                          iterative_scan="relaxed_order")
        p.add(ch, vecs)
        loads["pgvector"] = time.perf_counter() - t0
        stores["pgvector (hnsw)"] = p

    print(f"\n{'store':<34} {'agree@10':>9} {'R@5':>6} {'MRR':>6} {'load s':>7} {'ms/q':>7}"
          + (f"   where={where}" if where else ""))
    for name, s in stores.items():
        r = evaluate(s, qa, qv, base, where)
        load = next((v for k, v in loads.items() if name.startswith(k)), 0.0)
        print(f"{name:<34} {r['agree']:>9.3f} {r['r5']:>6.3f} {r['mrr']:>6.3f} {load:>7.2f} {r['ms']:>7.2f}")

    if a.show:
        i = next((j for j, x in enumerate(qa) if x["id"] == a.show), None)
        if i is None:
            sys.exit(f"no golden question {a.show}")
        print(f"\n{a.show}: {qa[i]['question']}\n  relevant: {qa[i].get('source_ids')}")
        for name, s in stores.items():
            print(f"  {name}")
            for h in s.search(qv[i], k=5, where=where):
                print(f"    {h.rank}. {h.score:.3f}  {h.chunk.id}")

    print("\nincremental update: remove hr-vacation-2026, re-add it with an edited first chunk")
    doc = "hr-vacation-2026"
    old = [c for c in ch if c.doc_id == doc]
    idx = [k for k, c in enumerate(ch) if c.doc_id == doc]
    for name, s in stores.items():
        n = s.remove(doc)
        print(f"  {name:<34} removed {n} chunks, size now {len(s)}")
    edited = [type(c)(**{**c.__dict__, "text": c.text + " (edited)"}) for c in old]
    for s in stores.values():
        s.add(edited, vecs[idx])
    sizes = {name: len(s) for name, s in stores.items()}
    print(f"  sizes after re-add: {sizes}")
    v = qv[0]
    tops = {name: [h.chunk.id for h in s.search(v, 5)] for name, s in stores.items()}
    same = len({tuple(t) for t in tops.values()}) == 1
    print(f"  top-5 identical across stores after the update: {same}")
    if q.local:
        print("\nnote: in-process Qdrant searches EXACTLY (no HNSW, no quantization). Run with "
              "--qdrant against the docker compose server to test the real index.")


if __name__ == "__main__":
    main()

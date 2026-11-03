"""Exercise 2: sweep HNSW parameters, measure recall@10 vs latency, keep the Pareto frontier.

    python labs/11-managed-vectors/hnsw_sweep.py                          # FAISS, offline, ~1 min
    python labs/11-managed-vectors/hnsw_sweep.py --mine                   # frontier with YOUR mine.py
    python labs/11-managed-vectors/hnsw_sweep.py --backend qdrant         # the docker compose Qdrant
    python labs/11-managed-vectors/hnsw_sweep.py --backend pgvector       # the docker compose Postgres
    python labs/11-managed-vectors/hnsw_sweep.py --m 8,16,32 --ef 10,20,40,80,160,320 --n 50000

What is measured, for every (M, ef_search) pair:
  recall@10  against EXACT search on the same data (brute force; for Qdrant also checked with
             SearchParams(exact=True), for pgvector with the index disabled)
  ms         mean latency per query, one query at a time, after a warm-up
  p95        95th percentile latency: what your slowest users feel
Build time per M is printed too (ef_construction is fixed; change it with --ef-construct).

The data: clustered synthetic unit vectors (384 dims by default), not Acme: Acme has 210
chunks, where every index is exact and instant. With --real e5-small the 79 golden questions
are appended to the queries and the 210 Acme vectors to the data, so you can see your own
vectors are not special. Network round trips dominate Qdrant/pgvector latency on localhost
(~0.3-1 ms): compare configurations within one backend, not FAISS ms against Qdrant ms.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

from common import PG_DSN, QDRANT_URL, RESULTS, qdrant_client_or_exit, synthetic  # noqa: E402
from ragkit.vectors.bench import exact_top_k_matrix, sweep  # noqa: E402


def ints(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x]


def faiss_backend(x, m: int, efc: int, threads: int):
    import faiss  # type: ignore
    faiss.omp_set_num_threads(threads)
    idx = faiss.IndexHNSWFlat(x.shape[1], m, faiss.METRIC_INNER_PRODUCT)
    idx.hnsw.efConstruction = efc
    t0 = time.perf_counter()
    idx.add(x)
    build = time.perf_counter() - t0

    def search(q, k, ef):
        idx.hnsw.efSearch = ef
        return idx.search(q.reshape(1, -1), k)[1][0].tolist()
    return search, build, None


def qdrant_backend(x, m: int, efc: int, url: str):
    from qdrant_client import models
    c = qdrant_client_or_exit(url)
    name = f"l11_sweep_m{m}_efc{efc}_n{len(x)}"
    t0 = time.perf_counter()
    if not c.collection_exists(name):
        c.create_collection(name, vectors_config=models.VectorParams(size=x.shape[1], distance=models.Distance.DOT),
                            hnsw_config=models.HnswConfigDiff(m=m, ef_construct=efc),
                            optimizers_config=models.OptimizersConfigDiff(indexing_threshold=1000))
        for i in range(0, len(x), 1000):
            c.upsert(name, points=models.Batch(ids=list(range(i, min(i + 1000, len(x)))),
                                               vectors=x[i:i + 1000].tolist()), wait=False)
    while True:                                   # wait until the HNSW graph covers every point
        info = c.get_collection(name)
        if str(info.status).lower().endswith("green") and (info.indexed_vectors_count or 0) >= len(x) * 0.99:
            break
        time.sleep(1)
    build = time.perf_counter() - t0

    def search(q, k, ef, exact=False):
        r = c.query_points(name, query=q.tolist(), limit=k,
                           search_params=models.SearchParams(hnsw_ef=ef, exact=exact))
        return [p.id for p in r.points]
    return search, build, lambda q, k: search(q, k, 0, exact=True)


def pgvector_backend(x, m: int, efc: int, dsn: str):
    import psycopg  # type: ignore

    from ragkit.vectors.pgvector_store import vector_literal
    cn = psycopg.connect(dsn, autocommit=True)
    t = f"l11_sweep_m{m}_efc{efc}_n{len(x)}"
    t0 = time.perf_counter()
    exists = cn.execute("SELECT to_regclass(%s)", (t,)).fetchone()[0]
    if not exists:
        cn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cn.execute(f"CREATE TABLE {t} (id int PRIMARY KEY, embedding vector({x.shape[1]}))")
        with cn.cursor().copy(f"COPY {t} (id, embedding) FROM STDIN") as cp:
            for i, v in enumerate(x):
                cp.write_row((i, vector_literal(v)))
        cn.execute("SET maintenance_work_mem = '1GB'")        # build the graph in memory
        cn.execute(f"CREATE INDEX ON {t} USING hnsw (embedding vector_ip_ops) "
                   f"WITH (m = {m}, ef_construction = {efc})")
    build = time.perf_counter() - t0

    def search(q, k, ef):
        with cn.transaction():
            cn.execute(f"SET LOCAL hnsw.ef_search = {int(ef)}")
            rows = cn.execute(f"SELECT id FROM {t} ORDER BY embedding <#> %s::vector LIMIT {int(k)}",
                              (vector_literal(q),)).fetchall()
        return [r[0] for r in rows]
    return search, build, None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["faiss", "qdrant", "pgvector"], default="faiss")
    ap.add_argument("--n", type=int, default=30_000)
    ap.add_argument("--dim", type=int, default=384)
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--noise", type=float, default=1.4)
    ap.add_argument("--m", type=ints, default=[8, 16, 32])
    ap.add_argument("--ef", type=ints, default=[10, 20, 40, 80, 160, 320])
    ap.add_argument("--ef-construct", type=int, default=100)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--qdrant", default=QDRANT_URL)
    ap.add_argument("--pg", default=PG_DSN)
    ap.add_argument("--real", help="also mix in the Acme vectors of this embedder (e.g. e5-small)")
    ap.add_argument("--mine", action="store_true", help="use mine.recall_at_k / mine.pareto_frontier")
    a = ap.parse_args()

    if a.mine:
        import mine
        try:
            mine.pareto_frontier([(1.0, 1.0)])
            mine.recall_at_k([1], [1], 1)
        except NotImplementedError:
            sys.exit("implement mine.recall_at_k and mine.pareto_frontier first (exercise 2)")
        frontier = mine.pareto_frontier
        from ragkit.vectors import bench
        bench.recall_ids = mine.recall_at_k          # sweep() computes recall with this
    else:
        from ragkit.vectors.bench import pareto_frontier as frontier

    x, q = synthetic(a.n, a.dim, a.queries, noise=a.noise)
    if a.real:
        from common import acme_vectors
        _, vecs, _, qv = acme_vectors(a.real)
        if vecs.shape[1] != a.dim:
            sys.exit(f"--real {a.real} has {vecs.shape[1]} dims; pass --dim {vecs.shape[1]}")
        x, q = np.vstack([x, vecs]).astype(np.float32), np.vstack([q, qv]).astype(np.float32)
    truth = exact_top_k_matrix(q, x, 10)
    print(f"[{a.backend}] {len(x):,} vectors x {x.shape[1]} dims, {len(q)} queries, ef_construct {a.ef_construct}")

    rows = []
    for m in a.m:
        if a.backend == "faiss":
            search, build, exact = faiss_backend(x, m, a.ef_construct, a.threads)
        elif a.backend == "qdrant":
            search, build, exact = qdrant_backend(x, m, a.ef_construct, a.qdrant)
        else:
            search, build, exact = pgvector_backend(x, m, a.ef_construct, a.pg)
        if exact is not None:                 # the server's own exact search must agree with ours
            agree = np.mean([len(set(exact(v, 10)) & set(t)) / 10 for v, t in zip(q[:20], truth[:20])])
            print(f"  M={m}: server exact search agrees with numpy on {agree:.0%} of the top-10")
        print(f"  M={m}: index ready in {build:.1f}s")
        for r in sweep(search, q, truth, a.ef, k=10):
            rows.append({"m": m, "ef": r["param"], "recall": r["recall"], "ms": r["ms"], "p95_ms": r["p95_ms"],
                         "build_s": build})

    front = set(frontier([(r["ms"], r["recall"]) for r in rows]))
    print(f"\n{'M':>3} {'ef':>5} {'recall@10':>10} {'ms/q':>8} {'p95':>8}   frontier")
    for i, r in enumerate(rows):
        print(f"{r['m']:>3} {r['ef']:>5} {r['recall']:>10.3f} {r['ms']:>8.3f} {r['p95_ms']:>8.3f}   "
              f"{'*' if i in front else ''}")
    best = [rows[i] for i in sorted(front, key=lambda i: rows[i]["ms"])]
    target = next((r for r in best if r["recall"] >= 0.95), None)
    if target:
        print(f"\ncheapest config with recall@10 >= 0.95: M={target['m']} ef={target['ef']} "
              f"({target['ms']:.3f} ms/query)")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"sweep_{a.backend}.json"
    out.write_text(json.dumps({"args": vars(a) | {"m": a.m, "ef": a.ef}, "rows": rows}, indent=1, default=str))
    print(f"saved {out.relative_to(RESULTS.parent.parent.parent)}")


if __name__ == "__main__":
    main()

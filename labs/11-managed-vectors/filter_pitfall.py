"""Exercise 3: filtered vector search: is the result correct, and what does a restrictive
filter do to each strategy?

    python labs/11-managed-vectors/filter_pitfall.py                       # FAISS strategies, offline
    python labs/11-managed-vectors/filter_pitfall.py --mine                # recall with YOUR mine.py
    python labs/11-managed-vectors/filter_pitfall.py --qdrant              # + Qdrant (ACORN off/on)
    python labs/11-managed-vectors/filter_pitfall.py --pgvector            # + pgvector (iterative scan off/on)

The data: N clustered unit vectors (like embeddings), each with filter fields of different
SELECTIVITY (the share of rows that pass): 50%, 10%, 1% and 0.1%. Each selectivity comes in
two flavours:
  random     the passing rows are spread uniformly over the space (a "language" field)
  clustered  the passing rows are whole topic clusters, usually FAR from the query (a
             "tenant" field: tenant B's documents are about tenant B's topics). This is
             the hard case for graph search: the walk starts in the wrong neighbourhood.

Strategies (k = 10, recall against the exact filtered top 10 = mine.exact_filtered_top_k):
  post-filter   HNSW top (k x oversample) without the filter, then drop non-matching rows.
                What a naive wrapper does. Restrictive filter -> fewer than k results.
  in-graph      HNSW walk that only RETURNS allowed rows but may pass through others
                (FAISS IDSelector; Qdrant filterable HNSW and pgvector iterative scans
                are smarter versions of this).
  pre-filter    score exactly the rows that pass (brute force on the subset). Always
                correct; cost grows with the number of passing rows, so it is the right
                plan for restrictive filters, which is what query planners choose.
  planner       exact on the subset when few rows pass (<= --full-scan), in-graph otherwise:
                the idea behind Qdrant's full_scan_threshold and Postgres' cost-based planner.
  qdrant        filter in the query; Qdrant's planner picks payload-index + exact scoring
                below full_scan_threshold, filterable HNSW above it. ACORN off vs on.
  pgvector      WHERE clause + HNSW. iterative_scan off: the index returns ef_search
                candidates, THEN Postgres filters -> can return fewer than LIMIT rows.
                relaxed_order: keeps scanning until LIMIT rows pass.
Columns: recall (filtered recall@10), got (mean number of results returned; 10 is right
unless fewer rows pass), ms (mean per query).
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from common import PG_DSN, QDRANT_URL, qdrant_client_or_exit  # noqa: E402
from ragkit.vectors.bench import exact_filtered_top_k, filtered_recall, post_filter  # noqa: E402

SELECTIVITIES = (0.5, 0.1, 0.01, 0.001)


def make_data(n: int, dim: int, queries: int, clusters: int, noise: float, seed: int = 0):
    rng = np.random.default_rng(seed)
    centers = rng.standard_normal((clusters, dim)).astype(np.float32)
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)
    lab = rng.integers(0, clusters, n + queries)
    x = centers[lab] + noise / np.sqrt(dim) * rng.standard_normal((n + queries, dim)).astype(np.float32)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    data, qs, data_lab = x[:n], x[n:], lab[:n]
    masks = {"no filter": np.ones(n, dtype=bool)}
    for s in SELECTIVITIES:
        masks[f"random {s:g}"] = rng.random(n) < s
        chosen = rng.permutation(clusters)[:max(1, round(clusters * s))]
        masks[f"clustered {s:g}"] = np.isin(data_lab, chosen)
    return data, qs, masks


def run(name, fn, qs, masks, k, recall_fn, exact_fn, rows):
    for mname, mask in masks.items():
        recs, gots, t = [], [], 0.0
        for q in qs:
            exact = exact_fn(q, mask)
            t0 = time.perf_counter()
            found = fn(q, mask, mname)
            t += time.perf_counter() - t0
            assert all(mask[int(i)] for i in found), f"{name} returned a row that fails the filter"
            recs.append(recall_fn(found, exact, k))
            gots.append(len(found))
        rows.append((name, mname, float(mask.mean()), float(np.mean(recs)), float(np.mean(gots)),
                     t / len(qs) * 1000))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=50_000)
    ap.add_argument("--dim", type=int, default=128)
    ap.add_argument("--queries", type=int, default=100)
    ap.add_argument("--clusters", type=int, default=1000)
    ap.add_argument("--noise", type=float, default=1.0)
    ap.add_argument("--ef", type=int, default=64, help="efSearch / hnsw_ef / hnsw.ef_search")
    ap.add_argument("--full-scan", type=int, default=6000,
                    help="planner: score exactly when at most this many rows pass")
    ap.add_argument("--oversample", type=int, default=10, help="post-filter fetches k x this")
    ap.add_argument("--qdrant", nargs="?", const=QDRANT_URL, help=f"Qdrant URL (default {QDRANT_URL})")
    ap.add_argument("--pgvector", nargs="?", const=PG_DSN, help="PostgreSQL DSN with pgvector")
    ap.add_argument("--mine", action="store_true")
    a = ap.parse_args()
    k = 10
    if a.mine:
        import mine
        try:
            mine.filtered_recall([], [], 10)
            mine.exact_filtered_top_k(np.ones(2), np.ones((1, 2)), [True], 1)
        except NotImplementedError:
            raise SystemExit("implement mine.exact_filtered_top_k and mine.filtered_recall first (exercise 3)")
        exact_top, recall_fn = mine.exact_filtered_top_k, mine.filtered_recall
    else:
        exact_top, recall_fn = exact_filtered_top_k, filtered_recall
    x, qs, masks = make_data(a.n, a.dim, a.queries, a.clusters, a.noise)
    cache: dict = {}

    def exact_fn(q, mask):
        key = (id(mask), q.tobytes())
        if key not in cache:
            cache[key] = [int(i) for i in exact_top(q, x, mask, k)]
        return cache[key]

    print(f"{a.n:,} vectors x {a.dim} dims, {a.queries} queries, k={k}, ef={a.ef}")
    import faiss  # type: ignore
    faiss.omp_set_num_threads(1)
    idx = faiss.IndexHNSWFlat(a.dim, 16, faiss.METRIC_INNER_PRODUCT)
    idx.add(x)
    idx.hnsw.efSearch = max(a.ef, k * a.oversample)
    rows: list = []

    def post(q, mask, _):
        cand = idx.search(q.reshape(1, -1), k * a.oversample)[1][0]
        return post_filter([i for i in cand if i >= 0], mask, k)

    sels = {m: faiss.IDSelectorBatch(np.flatnonzero(mask).astype(np.int64)) for m, mask in masks.items()}

    def ingraph(q, mask, mname):
        p = faiss.SearchParametersHNSW(sel=sels[mname], efSearch=a.ef)
        return [int(i) for i in idx.search(q.reshape(1, -1), k, params=p)[1][0] if i >= 0]

    allowed = {m: np.flatnonzero(mask) for m, mask in masks.items()}

    def pre(q, mask, mname):               # exact on the subset: x is already normalized
        rows_ = allowed[mname]
        s = x[rows_] @ q
        top = np.argpartition(-s, min(k, len(s) - 1))[:k] if len(s) > k else np.arange(len(s))
        return [int(rows_[i]) for i in top[np.argsort(-s[top], kind="stable")]]

    def planner(q, mask, mname):           # what a query planner does: cardinality decides
        return pre(q, mask, mname) if len(allowed[mname]) <= a.full_scan else ingraph(q, mask, mname)

    run(f"post-filter x{a.oversample}", post, qs, masks, k, recall_fn, exact_fn, rows)
    run("in-graph (faiss sel)", ingraph, qs, masks, k, recall_fn, exact_fn, rows)
    run("pre-filter (exact)", pre, qs, masks, k, recall_fn, exact_fn, rows)
    run(f"planner (<= {a.full_scan} rows: exact)", planner, qs, masks, k, recall_fn, exact_fn, rows)
    if a.qdrant:
        rows += qdrant_rows(a, x, qs, masks, k, recall_fn, exact_fn)
    if a.pgvector:
        rows += pg_rows(a, x, qs, masks, k, recall_fn, exact_fn)

    print(f"\n{'strategy':<30} {'filter':<16} {'pass':>7} {'recall':>7} {'got':>5} {'ms':>8}")
    last = None
    for name, mname, share, rec, got, ms in rows:
        if name != last:
            print()
            last = name
        flag = "  <- fewer than k" if got < min(k, share * a.n) - 0.5 else ""
        print(f"{name:<30} {mname:<16} {share:>7.2%} {rec:>7.3f} {got:>5.1f} {ms:>8.3f}{flag}")
    print("\nRead it: which strategy stays at recall ~1.0 AND returns 10 results at 0.1%? "
          "What did that cost in ms at 50%?")


def qdrant_rows(a, x, qs, masks, k, recall_fn, exact_fn):
    from qdrant_client import models
    c = qdrant_client_or_exit(a.qdrant)
    name = f"l11_filters_n{len(x)}_d{x.shape[1]}"
    fields = {m: m.replace(" ", "_").replace(".", "p") for m in masks}
    if not c.collection_exists(name):
        c.create_collection(name, vectors_config=models.VectorParams(size=x.shape[1], distance=models.Distance.DOT),
                            optimizers_config=models.OptimizersConfigDiff(indexing_threshold=1000))
        for f in fields.values():                    # payload indexes BEFORE the data
            c.create_payload_index(name, field_name=f, field_schema="bool")
        for i in range(0, len(x), 1000):
            ids = list(range(i, min(i + 1000, len(x))))
            payloads = [{fields[m]: bool(masks[m][j]) for m in masks} for j in ids]
            c.upsert(name, points=models.Batch(ids=ids, vectors=x[i:i + 1000].tolist(), payloads=payloads), wait=False)
    while not (str(c.get_collection(name).status).lower().endswith("green")
               and (c.get_collection(name).indexed_vectors_count or 0) >= len(x) * 0.99):
        time.sleep(1)
    out = []
    for acorn in (False, True):
        def fn(q, mask, mname, acorn=acorn):
            r = c.query_points(name, query=q.tolist(), limit=k,
                               query_filter=models.Filter(must=[models.FieldCondition(
                                   key=fields[mname], match=models.MatchValue(value=True))]),
                               search_params=models.SearchParams(hnsw_ef=a.ef,
                                                                 acorn=models.AcornSearchParams(enable=acorn)))
            return [p.id for p in r.points]
        run(f"qdrant acorn={'on' if acorn else 'off'}", fn, qs, masks, k, recall_fn, exact_fn, out)
    return out


def pg_rows(a, x, qs, masks, k, recall_fn, exact_fn):
    import psycopg  # type: ignore

    from ragkit.vectors.pgvector_store import vector_literal
    cn = psycopg.connect(a.pgvector, autocommit=True)
    t = f"l11_filters_n{len(x)}_d{x.shape[1]}"
    cols = {m: m.replace(" ", "_").replace(".", "p") for m in masks}
    if not cn.execute("SELECT to_regclass(%s)", (t,)).fetchone()[0]:
        cn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        coldefs = ", ".join(f"{c} boolean" for c in cols.values())
        cn.execute(f"CREATE TABLE {t} (id int PRIMARY KEY, embedding vector({x.shape[1]}), {coldefs})")
        with cn.cursor().copy(f"COPY {t} (id, embedding, {', '.join(cols.values())}) FROM STDIN") as cp:
            for i, v in enumerate(x):
                cp.write_row((i, vector_literal(v), *[bool(masks[m][i]) for m in masks]))
        cn.execute("SET maintenance_work_mem = '1GB'")
        cn.execute(f"CREATE INDEX ON {t} USING hnsw (embedding vector_ip_ops) WITH (m = 16, ef_construction = 100)")
        cn.execute(f"ANALYZE {t}")
    out = []
    for mode in ("off", "relaxed_order"):
        def fn(q, mask, mname, mode=mode):
            with cn.transaction():
                cn.execute("SET LOCAL enable_seqscan = off")     # make the planner use HNSW, as at scale
                cn.execute(f"SET LOCAL hnsw.ef_search = {int(a.ef)}")
                cn.execute(f"SET LOCAL hnsw.iterative_scan = {mode}")
                rows = cn.execute(f"SELECT id FROM {t} WHERE {cols[mname]} ORDER BY embedding <#> %s::vector "
                                  f"LIMIT {k}", (vector_literal(q),)).fetchall()
            return [r[0] for r in rows]
        run(f"pgvector iterative={mode}", fn, qs, masks, k, recall_fn, exact_fn, out)
    return out


if __name__ == "__main__":
    main()

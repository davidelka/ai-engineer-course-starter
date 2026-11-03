"""Exercise 7: exact vs approximate search with FAISS: speed, recall and memory.

    python labs/10-embeddings/faiss_bench.py                       # 100k x 384, ~1-2 minutes
    python labs/10-embeddings/faiss_bench.py --n 20000             # quick
    python labs/10-embeddings/faiss_bench.py --real e5-small       # mix in the cached Acme vectors
    python labs/10-embeddings/faiss_bench.py --threads 1           # per-query latency on one core

The data: we do not have 100k real Acme chunks, so we synthesize vectors that look like
embeddings (clustered, not uniform): `n_clusters` random topic centers, each point a center
plus noise, L2-normalized. Uniform random vectors in 384 dimensions are a bad benchmark:
all distances are almost equal and every ANN index looks terrible (try --clusters 0 to see).
With --real <model>, the real Acme chunk vectors from the embedding cache are added too, and
the queries are the 79 golden questions (embedded by the same model) plus synthetic ones.

The ground truth is exact search (IndexFlatIP). For every index we report:
  build   seconds to train (k-means for IVF/PQ) and add all vectors
  ms/q    average search latency per query (batched search, divided by the number of queries)
  R@10    recall@10 against the exact top 10 (1.0 = found all 10 true neighbors)
  MB      the serialized index size (faiss.serialize_index), i.e. the RAM it needs
Index types (faiss.index_factory strings):
  Flat           exact: every query compares to every vector. 4*d bytes/vector.
  HNSW32         graph with M=32 links/node; efSearch = how wide the search is. 4*d + ~2*M*4 bytes/vector.
  IVF{nlist},Flat   k-means cells; nprobe = cells searched per query. 4*d + 8 bytes/vector.
  IVF{nlist},PQ{m}  cells + product quantization: m bytes/vector (+8 for the id). Lossy.
"""

from __future__ import annotations

import argparse
import math
import sys
import time

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover
    sys.exit("this exercise needs faiss-cpu: uv pip install -r labs/10-embeddings/requirements.txt")

from common import acme_qa, chunks, embedder  # noqa: E402
from ragkit.vectors import l2_normalize  # noqa: E402


def topic_centers(clusters: int, d: int, rng) -> np.ndarray:
    return l2_normalize(rng.standard_normal((clusters, d), dtype=np.float32))


def synth(n: int, centers, d: int, rng, noise: float = 1.4) -> np.ndarray:
    """n points: a random topic center plus Gaussian noise, normalized. centers=None means
    uniform random directions (the bad benchmark)."""
    if centers is None:
        return l2_normalize(rng.standard_normal((n, d), dtype=np.float32))
    pick = rng.integers(0, centers.shape[0], n)
    x = centers[pick] + noise / math.sqrt(d) * rng.standard_normal((n, d), dtype=np.float32)
    return l2_normalize(x)


def recall_at(found: np.ndarray, truth: np.ndarray, k: int) -> float:
    hits = sum(len(set(f[:k]) & set(t[:k])) for f, t in zip(found, truth))
    return hits / (truth.shape[0] * k)


def timed_search(index, q, k, reps: int = 1):
    t0 = time.perf_counter()
    for _ in range(reps):
        _, ids = index.search(q, k)
    return ids, (time.perf_counter() - t0) / reps / q.shape[0] * 1000


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=100_000, help="number of database vectors")
    ap.add_argument("--dim", type=int, default=384)
    ap.add_argument("--queries", type=int, default=500)
    ap.add_argument("--clusters", type=int, default=2000, help="topic centers (0 = uniform random)")
    ap.add_argument("--noise", type=float, default=1.4, help="spread around each topic (bigger = harder)")
    ap.add_argument("-k", type=int, default=10)
    ap.add_argument("--real", help="embedder spec whose cached Acme vectors to mix in (e.g. e5-small)")
    ap.add_argument("--threads", type=int, default=0, help="FAISS threads (0 = library default)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if args.threads:
        faiss.omp_set_num_threads(args.threads)
    rng = np.random.default_rng(args.seed)

    d = args.dim
    real_q = None
    xb_parts = []
    if args.real:
        emb = embedder(args.real)
        rv = emb.embed_documents([c.context_text() for c in chunks()])
        real_q = emb.embed_queries([q["question"] for q in acme_qa()])
        d = rv.shape[1]
        xb_parts.append(rv)
        print(f"real vectors: {rv.shape[0]} Acme chunks from {emb.model_id} (dim {d})")
    centers = topic_centers(args.clusters, d, rng) if args.clusters else None
    xb_parts.append(synth(args.n - sum(p.shape[0] for p in xb_parts), centers, d, rng, args.noise))
    xb = np.ascontiguousarray(np.vstack(xb_parts), dtype=np.float32)
    xq = synth(args.queries, centers, d, rng, args.noise)     # queries: new points around the SAME topics
    if real_q is not None:
        xq = np.vstack([real_q, xq]).astype(np.float32)
    n, k = xb.shape[0], args.k
    print(f"database {n:,} x {d}  ({xb.nbytes / 1e6:.0f} MB float32), {xq.shape[0]} queries, k={k}, "
          f"faiss {faiss.__version__}, threads {faiss.omp_get_max_threads()}\n")

    rows = []

    def report(name, index, build_s, params=None):
        nonlocal truth
        mb = len(faiss.serialize_index(index)) / 1e6
        settings = params or [(None, None)]
        for label, setter in settings:
            if setter:
                setter(index)
            ids, ms = timed_search(index, xq, k)
            r = recall_at(ids, truth, k) if truth is not None else 1.0
            tag = f"{name}" + (f" {label}" if label else "")
            rows.append((tag, build_s, ms, r, mb))
            print(f"  {tag:34s} build {build_s:6.1f}s   {ms:7.3f} ms/q   R@{k} {r:5.3f}   {mb:8.1f} MB")

    # exact baseline (ground truth)
    t0 = time.perf_counter()
    flat = faiss.IndexFlatIP(d)
    flat.add(xb)
    build = time.perf_counter() - t0
    truth, flat_ms = timed_search(flat, xq, k)
    truth = np.array(truth)
    report("Flat (exact)", flat, build)

    # HNSW
    t0 = time.perf_counter()
    hnsw = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
    hnsw.hnsw.efConstruction = 40
    hnsw.add(xb)
    build = time.perf_counter() - t0
    report("HNSW32", hnsw, build, [(f"efSearch={ef}", (lambda ix, ef=ef: setattr(ix.hnsw, "efSearch", ef)))
                                   for ef in (16, 32, 64, 128, 256)])

    # IVF Flat
    nlist = max(16, min(int(4 * math.sqrt(n)), n // 40))   # FAISS wiki: ~C*sqrt(n) cells; k-means wants >= 39 points per cell
    t0 = time.perf_counter()
    quant = faiss.IndexFlatIP(d)
    ivf = faiss.IndexIVFFlat(quant, d, nlist, faiss.METRIC_INNER_PRODUCT)
    ivf.train(xb[rng.choice(n, min(n, 40 * nlist), replace=False)])
    ivf.add(xb)
    build = time.perf_counter() - t0
    report(f"IVF{nlist},Flat", ivf, build, [(f"nprobe={p}", (lambda ix, p=p: setattr(ix, "nprobe", p)))
                                           for p in (1, 4, 16, 64)])

    # IVF + PQ
    m = 48 if d % 48 == 0 else (32 if d % 32 == 0 else 16)
    t0 = time.perf_counter()
    quant2 = faiss.IndexFlatIP(d)
    ivfpq = faiss.IndexIVFPQ(quant2, d, nlist, m, 8, faiss.METRIC_INNER_PRODUCT)
    ivfpq.train(xb[rng.choice(n, min(n, max(40 * nlist, 256 * 40)), replace=False)])
    ivfpq.add(xb)
    build = time.perf_counter() - t0
    report(f"IVF{nlist},PQ{m}x8", ivfpq, build, [(f"nprobe={p}", (lambda ix, p=p: setattr(ix, "nprobe", p)))
                                                for p in (16, 64)])

    # the same PQ index, but re-scoring the top k*4 candidates with the exact vectors
    ivfpq.nprobe = 64
    refine = faiss.IndexRefineFlat(ivfpq, faiss.swig_ptr(xb))
    refine.k_factor = 4
    ids, ms = timed_search(refine, xq, k)
    r = recall_at(ids, truth, k)
    print(f"  {'IVF,PQ + exact re-rank (k_factor=4)':34s} build    0.0s   {ms:7.3f} ms/q   R@{k} {r:5.3f}"
          f"   (+{xb.nbytes / 1e6:.0f} MB: needs the full vectors again)")

    print("\nmemory math (bytes per vector -> total), float32, from the FAISS wiki formulas:")
    for N in (n, 1_000_000, 10_000_000):
        flat_b = 4 * d
        hnsw_b = 4 * d + 2 * 32 * 4                 # vectors + ~2*M neighbor ids of 4 bytes (level 0)
        ivf_b = 4 * d + 8
        pq_b = m + 8
        print(f"  N={N:>11,}  Flat {flat_b * N / 1e9:6.2f} GB | HNSW32 ~{hnsw_b * N / 1e9:6.2f} GB | "
              f"IVF,Flat {ivf_b * N / 1e9:6.2f} GB | IVF,PQ{m} {pq_b * N / 1e9:6.2f} GB")
    print("\nHow to read it: pick the cheapest row whose R@10 is good enough for you (0.95?), and"
          "\nremember that a reranker (lesson 12) can recover some of what a lossy index (PQ) loses.")
    if real_q is not None:
        print("The first 79 queries were the real golden questions; the rest were synthetic.")


if __name__ == "__main__":
    main()

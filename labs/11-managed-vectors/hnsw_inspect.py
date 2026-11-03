"""Exercise 1: look inside a real HNSW graph (FAISS), and check the theory against it.

    python labs/11-managed-vectors/hnsw_inspect.py                     # 20k x 384, M=16
    python labs/11-managed-vectors/hnsw_inspect.py --m 8 --m 32        # compare several M
    python labs/11-managed-vectors/hnsw_inspect.py --ef-construction 40 --ef-construction 200

For each M (and efConstruction) the script builds faiss.IndexHNSWFlat on clustered synthetic
vectors (they behave like embeddings; uniform random vectors do not) and prints:

  levels     how many nodes reached each layer, next to the theory: a node reaches layer >= l
             with probability M^-l (FAISS uses mL = 1/ln(M)). Few nodes up high = express lanes.
  degree     average and max number of neighbors on layer 0 (cap 2*M) and layer 1 (cap M).
  memory     the serialized index size vs our formula 4*d + (2M*4+4) + (M*4+4)/(M-1) bytes/node.
  build      seconds to insert all vectors (efConstruction = candidate list while inserting).
  recall@10  at efSearch 16 / 64 / 256, against exact search, with ms per query.
  delete     FAISS HNSW cannot remove a node (graph surgery is hard): we show the exception,
             and what databases do instead (tombstones + periodic rebuild/vacuum).
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
    sys.exit("needs faiss-cpu (installed in lesson 10): uv pip install faiss-cpu")

from common import fmt_mb, synthetic  # noqa: E402
from ragkit.vectors.bench import exact_top_k_matrix, mean_recall  # noqa: E402
from ragkit.vectors.sizing import graph_bytes_per_node  # noqa: E402


def layer_stats(index) -> tuple[list[int], dict]:
    h = index.hnsw
    levels = faiss.vector_to_array(h.levels)              # per node: number of layers (>= 1)
    counts = [int((levels > l).sum()) for l in range(int(levels.max()))]
    offsets = faiss.vector_to_array(h.offsets)
    neigh = faiss.vector_to_array(h.neighbors)
    deg = {}
    for layer in (0, 1):
        lo, hi = h.cum_nb_neighbors(layer), h.cum_nb_neighbors(layer + 1)
        ds = []
        for node in np.flatnonzero(levels > layer)[:5000]:
            seg = neigh[offsets[node] + lo: offsets[node] + hi]
            ds.append(int((seg >= 0).sum()))
        deg[layer] = (float(np.mean(ds)) if ds else 0.0, max(ds) if ds else 0, hi - lo)
    return counts, deg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=20_000)
    ap.add_argument("--dim", type=int, default=384)
    ap.add_argument("--m", type=int, action="append", help="HNSW M (repeatable); default 16")
    ap.add_argument("--ef-construction", type=int, action="append", help="default 40 (FAISS default)")
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--threads", type=int, default=1, help="FAISS threads (1 = honest per-query latency)")
    a = ap.parse_args()
    faiss.omp_set_num_threads(a.threads)
    x, q = synthetic(a.n, a.dim, a.queries)
    truth = exact_top_k_matrix(q, x, 10)
    print(f"data: {a.n:,} clustered unit vectors x {a.dim} dims, {a.queries} queries, threads={a.threads}\n")

    for m in a.m or [16]:
        for efc in a.ef_construction or [40]:
            idx = faiss.IndexHNSWFlat(a.dim, m, faiss.METRIC_INNER_PRODUCT)
            idx.hnsw.efConstruction = efc
            t0 = time.perf_counter()
            idx.add(x)
            build = time.perf_counter() - t0
            counts, deg = layer_stats(idx)
            size = faiss.serialize_index(idx).size
            formula = a.n * (4 * a.dim + graph_bytes_per_node(m))
            print(f"=== M={m}  efConstruction={efc}  build {build:.1f}s  ({a.n / build:,.0f} vectors/s)")
            print("  layer   nodes      theory (n * M^-l)")
            for l, c in enumerate(counts):
                print(f"  {l:>5}   {c:>7,}    {a.n * m ** -l:>10,.0f}")
            for layer, (avg, mx, cap) in deg.items():
                print(f"  degree on layer {layer}: avg {avg:.1f}, max {mx}, cap {cap}")
            print(f"  memory: serialized {fmt_mb(size)}  vs formula {fmt_mb(formula)}  "
                  f"(vectors alone {fmt_mb(a.n * 4 * a.dim)})")
            for ef in (16, 64, 256):
                idx.hnsw.efSearch = ef
                t0 = time.perf_counter()
                found = [idx.search(v.reshape(1, -1), 10)[1][0] for v in q]
                ms = (time.perf_counter() - t0) / len(q) * 1000
                print(f"  efSearch {ef:>3}: recall@10 {mean_recall(found, truth, 10):.3f}   {ms:.3f} ms/query")
            print()

    print("=== delete")
    idx = faiss.IndexHNSWFlat(a.dim, 16, faiss.METRIC_INNER_PRODUCT)
    idx.add(x[:1000])
    try:
        idx.remove_ids(np.array([1, 2, 3], dtype=np.int64))
        print("  remove_ids worked (unexpected for HNSW in this FAISS version)")
    except RuntimeError as exc:
        print(f"  faiss HNSW remove_ids -> RuntimeError: {str(exc).splitlines()[0][:100]}")
    print("  Databases mark deleted points (tombstones), skip them at search time, and repair or")
    print("  rebuild the graph later: Qdrant's optimizer (vacuum of segments), pgvector's VACUUM.")
    print("  Many tombstones = the walk wastes steps on dead nodes = lower recall at the same ef.")
    for m in a.m or [16]:
        print(f"theory, M={m}: upper layers per node 1/(M-1) = {1 / (m - 1):.3f}; "
              f"top layer ~ log_M(n) = {math.log(a.n) / math.log(m):.1f}")


if __name__ == "__main__":
    main()

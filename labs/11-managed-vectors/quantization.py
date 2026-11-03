"""Exercise 5: quantization: how much memory it saves, how much recall it costs, and how
rescoring buys the recall back.

    python labs/11-managed-vectors/quantization.py                  # FAISS + numpy, offline, ~1 min
    python labs/11-managed-vectors/quantization.py --mine           # RAM column from YOUR index_ram_bytes
    python labs/11-managed-vectors/quantization.py --qdrant         # + the same in Qdrant (server)
    python labs/11-managed-vectors/quantization.py --real e5-small --dim 384   # + Acme's own vectors

Every method is first searched on its compressed codes ONLY (the "raw" column), then with
RESCORING: fetch k x oversample candidates with the compressed codes, re-rank those few
with the float32 originals (which can live on disk: only k x oversample are read), keep k.
  float32   4 bytes/dim, the exact baseline (FAISS IndexFlatIP)
  float16   2 bytes/dim (IndexScalarQuantizer fp16; pgvector halfvec)
  int8      1 byte/dim (IndexScalarQuantizer 8bit; Qdrant scalar)
  binary    1 bit/dim: sign of each coordinate, Hamming distance (Qdrant binary)
  pq        product quantization, --pq-m bytes/vector (Qdrant product, FAISS PQ)
Columns: bytes/vec, RAM at 1M and 10M vectors (codes + HNSW graph M=16; originals on disk
for quantized rows), recall@10 raw, then with rescoring at oversample 2, 4 and 10.
Quantization changes MEMORY and SPEED; the graph walk is separate (here we search the codes
exhaustively so the numbers isolate the quantization error).
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from common import QDRANT_URL, fmt_mb, qdrant_client_or_exit, synthetic  # noqa: E402
from ragkit.vectors.bench import exact_top_k_matrix, mean_recall  # noqa: E402
from ragkit.vectors.sizing import hnsw_ram_bytes  # noqa: E402

OVERSAMPLE = (2, 4, 10)


def rescore(cands: np.ndarray, x: np.ndarray, q: np.ndarray, k: int) -> list[list[int]]:
    out = []
    for qi, row in enumerate(cands):
        row = row[row >= 0]
        s = x[row] @ q[qi]
        out.append(row[np.argsort(-s, kind="stable")[:k]].tolist())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=30_000)
    ap.add_argument("--dim", type=int, default=384)
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--noise", type=float, default=1.4)
    ap.add_argument("--pq-m", type=int, default=48, help="PQ sub-vectors = bytes per vector")
    ap.add_argument("--real", help="mix in the Acme vectors of this embedder (e.g. e5-small)")
    ap.add_argument("--qdrant", nargs="?", const=QDRANT_URL)
    ap.add_argument("--mine", action="store_true", help="RAM column from mine.index_ram_bytes")
    a = ap.parse_args()
    import faiss  # type: ignore
    faiss.omp_set_num_threads(1)
    k = 10

    x, q = synthetic(a.n, a.dim, a.queries, noise=a.noise)
    if a.real:
        from common import acme_vectors
        _, vecs, _, qv = acme_vectors(a.real)
        if vecs.shape[1] != a.dim:
            sys.exit(f"--real {a.real} has {vecs.shape[1]} dims; pass --dim {vecs.shape[1]}")
        x, q = np.vstack([x, vecs]).astype(np.float32), np.vstack([q, qv]).astype(np.float32)
    truth = exact_top_k_matrix(q, x, k)
    d = x.shape[1]
    if a.mine:
        import mine
        try:
            mine.index_ram_bytes(10, 10)
        except NotImplementedError:
            sys.exit("implement mine.index_ram_bytes first (exercise 5)")
        ram = lambda n, quant: mine.index_ram_bytes(n, d, 16, quant)          # noqa: E731
    else:
        ram = lambda n, quant: hnsw_ram_bytes(n, d, m=16, quantization=quant)["total_ram"]  # noqa: E731

    methods = []
    flat = faiss.IndexFlatIP(d)
    flat.add(x)
    methods.append(("float32", None, 4 * d, lambda kk: flat.search(q, kk)[1]))
    for name, qt, bpv in (("float16", faiss.ScalarQuantizer.QT_fp16, 2 * d),
                          ("int8", faiss.ScalarQuantizer.QT_8bit, d)):
        sq = faiss.IndexScalarQuantizer(d, qt, faiss.METRIC_INNER_PRODUCT)
        sq.train(x)
        sq.add(x)
        methods.append((name, name, bpv, lambda kk, sq=sq: sq.search(q, kk)[1]))
    bits = np.packbits(x > 0, axis=1)                       # 1 bit per dimension
    qbits = np.packbits(q > 0, axis=1)
    bidx = faiss.IndexBinaryFlat(d)
    bidx.add(bits)
    methods.append(("binary", "binary", (d + 7) // 8, lambda kk: bidx.search(qbits, kk)[1]))
    pq = faiss.IndexPQ(d, a.pq_m, 8, faiss.METRIC_INNER_PRODUCT)
    t0 = time.perf_counter()
    pq.train(x)
    pq.add(x)
    print(f"(PQ training {time.perf_counter() - t0:.1f}s)", file=sys.stderr)
    methods.append((f"pq{a.pq_m}", "pq", a.pq_m, lambda kk: pq.search(q, kk)[1]))

    print(f"{len(x):,} vectors x {d} dims, {len(q)} queries, recall@{k} vs exact float32\n")
    print(f"{'method':<9} {'bytes/vec':>9} {'RAM @1M':>10} {'RAM @10M':>10} {'raw':>6} "
          + " ".join(f"{'x' + str(o):>6}" for o in OVERSAMPLE))
    for name, quant, bpv, search in methods:
        raw = mean_recall(search(k).tolist(), truth, k)
        resc = [mean_recall(rescore(search(k * o), x, q, k), truth, k) for o in OVERSAMPLE]
        qq = None if quant in (None, "pq") else quant
        r1 = ram(1_000_000, qq) if quant != "pq" else hnsw_ram_bytes(1_000_000, d, quantization="pq", pq_bytes=a.pq_m)["total_ram"]
        r10 = ram(10_000_000, qq) if quant != "pq" else hnsw_ram_bytes(10_000_000, d, quantization="pq", pq_bytes=a.pq_m)["total_ram"]
        print(f"{name:<9} {bpv:>9} {fmt_mb(r1):>10} {fmt_mb(r10):>10} {raw:>6.3f} "
              + " ".join(f"{r:>6.3f}" for r in resc))
    print("\nRAM = codes + HNSW graph (M=16); for quantized rows the float32 originals "
          f"({fmt_mb(4 * d * 1_000_000)} per 1M) sit on disk and are read only for rescoring.")

    if a.qdrant:
        qdrant_quant(a.qdrant, x, q, truth, k)


def qdrant_quant(url, x, q, truth, k):
    from qdrant_client import models
    c = qdrant_client_or_exit(url)
    configs = {
        "none": None,
        "scalar": models.ScalarQuantization(scalar=models.ScalarQuantizationConfig(type=models.ScalarType.INT8, always_ram=True)),
        "binary": models.BinaryQuantization(binary=models.BinaryQuantizationConfig(always_ram=True)),
        "product": models.ProductQuantization(product=models.ProductQuantizationConfig(compression=models.CompressionRatio.X16, always_ram=True)),
    }
    print(f"\nQdrant ({url}): HNSW m=16 ef=128, recall@{k} vs exact float32")
    print(f"{'quantization':<13} {'rescore off':>11} {'on x1':>7} {'on x2':>7} {'on x4':>7} {'ms (x2)':>8}")
    for name, qc in configs.items():
        col = f"l11_quant_{name}_n{len(x)}_d{x.shape[1]}"
        if not c.collection_exists(col):
            c.create_collection(col, vectors_config=models.VectorParams(size=x.shape[1], distance=models.Distance.DOT,
                                                                        on_disk=qc is not None),
                                quantization_config=qc,
                                optimizers_config=models.OptimizersConfigDiff(indexing_threshold=1000))
            for i in range(0, len(x), 1000):
                c.upsert(col, points=models.Batch(ids=list(range(i, min(i + 1000, len(x)))),
                                                  vectors=x[i:i + 1000].tolist()), wait=False)
        while not (str(c.get_collection(col).status).lower().endswith("green")
                   and (c.get_collection(col).indexed_vectors_count or 0) >= len(x) * 0.99):
            time.sleep(1)
        res, ms = [], 0.0
        for rescore_on, over in ((False, None), (True, 1.0), (True, 2.0), (True, 4.0)):
            qp = None if qc is None else models.QuantizationSearchParams(rescore=rescore_on, oversampling=over)
            found, t0 = [], time.perf_counter()
            for v in q:
                r = c.query_points(col, query=v.tolist(), limit=k,
                                   search_params=models.SearchParams(hnsw_ef=128, quantization=qp))
                found.append([p.id for p in r.points])
            if over == 2.0:
                ms = (time.perf_counter() - t0) / len(q) * 1000
            res.append(mean_recall(found, truth, k))
        print(f"{name:<13} {res[0]:>11.3f} {res[1]:>7.3f} {res[2]:>7.3f} {res[3]:>7.3f} {ms:>8.2f}")


if __name__ == "__main__":
    main()

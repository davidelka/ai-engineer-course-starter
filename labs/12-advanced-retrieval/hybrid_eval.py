"""Exercise 3: hybrid search on the golden set. BM25 vs dense vs RRF vs weighted fusion,
per question type, and WHY fusion helps (which questions each retriever finds alone).

    python labs/12-advanced-retrieval/hybrid_eval.py                    # e5-small (local)
    python labs/12-advanced-retrieval/hybrid_eval.py --dense fake       # offline plumbing check
    python labs/12-advanced-retrieval/hybrid_eval.py --sweep-k          # RRF k = 0, 1, 10, 60, 200
    python labs/12-advanced-retrieval/hybrid_eval.py --mine             # fusion with YOUR mine.py

Retrievers (all over the same 210 chunks, heading:400:40:150):
  bm25                    lesson 9's lexical baseline
  dense                   DenseRetriever with --dense
  rrf k=60                HybridRetriever, Reciprocal Rank Fusion, each child fetches 50
  weighted a=<w>          min-max normalized scores, BM25 weight a, dense weight 1-a
  weighted z a=0.5        z-score normalization instead of min-max
Metrics: recall@5 and MRR@10 at document level (ragkit.metrics). Printed as a list per
question type; the cross-lingual group is the 6 questions whose source is in the other language.
Results: results/hybrid_<dense>.json
"""

from __future__ import annotations

import argparse
import json
import sys

from common import DEFAULT_DENSE, DENSE_HELP, RESULTS, acme_qa, bm25_index, chunks, dense_index
from ragkit import metrics as M
from ragkit.hybrid import HybridRetriever


class MineFusion:
    """HybridRetriever with fusion done by mine.py (exercise 1 and 2)."""

    def __init__(self, a, b, method: str, weights=None):
        import mine
        self.a, self.b, self.method, self.weights, self.mine = a, b, method, weights, mine
        self.name = f"mine:{method}"

    def search(self, query, k=5, where=None):
        from ragkit.types import Hit
        ha, hb = self.a.search(query, k=50, where=where), self.b.search(query, k=50, where=where)
        by_id = {h.chunk.id: h.chunk for h in ha + hb}
        if self.method == "rrf":
            fused = self.mine.rrf([[h.chunk.id for h in ha], [h.chunk.id for h in hb]])
        else:
            fused = self.mine.weighted_fusion([{h.chunk.id: h.score for h in ha},
                                               {h.chunk.id: h.score for h in hb}], self.weights)
        return [Hit(chunk=by_id[c], score=s, rank=i) for i, (c, s) in enumerate(fused[:k], 1)]


GROUPS = ["ALL", "single_hop", "multi_hop", "numeric", "version_conflict", "acronym", "hebrew", "cross-lingual"]


def report(tables: dict) -> None:
    for g in GROUPS:
        first = next(iter(tables.values()))
        if g not in first:
            continue
        print(f"\n{g} (n={int(first[g]['n'])})")
        best = max(t[g]["recall@5"] for t in tables.values())
        for name, t in tables.items():
            mark = "  <- best recall@5" if t[g]["recall@5"] == best and len(tables) > 1 else ""
            print(f"  - {name}: recall@5 {t[g]['recall@5']:.3f}, MRR {t[g]['mrr']:.3f}{mark}")


def complementarity(res_a, res_b, name_a="bm25", name_b="dense") -> None:
    both = only_a = only_b = neither = 0
    examples_a, examples_b = [], []
    for ra, rb in zip(res_a, res_b):
        ha, hb = ra.hit(5) > 0, rb.hit(5) > 0
        if ha and hb:
            both += 1
        elif ha:
            only_a += 1
            examples_a.append(ra)
        elif hb:
            only_b += 1
            examples_b.append(rb)
        else:
            neither += 1
    print(f"\nwho finds at least one relevant document in the top 5 (hit@5), per question:")
    print(f"  - both: {both}\n  - only {name_a}: {only_a}\n  - only {name_b}: {only_b}\n  - neither: {neither}")
    for label, ex in ((name_a, examples_a), (name_b, examples_b)):
        for r in ex[:6]:
            print(f"    only {label}: {r.qid} [{r.qtype}] {r.question[:80]}")
    print("  Fusion can only help when each retriever finds questions the other misses.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dense", default=DEFAULT_DENSE, help=DENSE_HELP)
    ap.add_argument("--sweep-k", action="store_true", help="also RRF with k = 0, 1, 10, 200")
    ap.add_argument("--weights", default="0.3,0.5,0.7", help="BM25 weights to try for weighted fusion")
    ap.add_argument("--mine", action="store_true", help="add rrf and weighted fusion computed by mine.py")
    args = ap.parse_args()

    qa = acme_qa()
    cs = chunks()
    bm25 = bm25_index(cs)
    try:
        dense = dense_index(args.dense, cs)
    except ImportError as exc:
        sys.exit(str(exc))
    rs = {"bm25": bm25, f"dense ({args.dense})": dense,
          "rrf k=60": HybridRetriever({"bm25": bm25, "dense": dense}, k_rrf=60)}
    if args.sweep_k:
        for kk in (0, 1, 10, 200):
            rs[f"rrf k={kk}"] = HybridRetriever({"bm25": bm25, "dense": dense}, k_rrf=kk)
    for a in [float(x) for x in args.weights.split(",") if x]:
        rs[f"weighted a={a}"] = HybridRetriever({"bm25": bm25, "dense": dense}, method="weighted",
                                                weights=[a, 1 - a])
    rs["weighted z a=0.5"] = HybridRetriever({"bm25": bm25, "dense": dense}, method="weighted",
                                             weights=[0.5, 0.5], normalize="zscore")
    if args.mine:
        try:
            rs["mine rrf"] = MineFusion(bm25, dense, "rrf")
            rs["mine weighted a=0.5"] = MineFusion(bm25, dense, "weighted", [0.5, 0.5])
            rs["mine rrf"].search("test", 1)
            rs["mine weighted a=0.5"].search("test", 1)
        except NotImplementedError as exc:
            sys.exit(f"{exc}: implement exercises 1-2 in mine.py, or run without --mine")

    results = {n: M.run_queries(r, qa, depth=10) for n, r in rs.items()}
    tables = {n: M.summarize(res) for n, res in results.items()}
    print(f"{len(results['bm25'])} answerable golden questions; dense model: {args.dense}")
    report(tables)
    complementarity(results["bm25"], results[f"dense ({args.dense})"])
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"hybrid_{args.dense.replace(':', '_')}.json"
    out.write_text(json.dumps(tables, indent=1))
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    main()

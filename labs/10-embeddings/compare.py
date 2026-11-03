"""Exercise 5: BM25 vs dense vs a simple union, per question type, on the 69 answerable
golden questions of data/acme/corpus/golden/qa.jsonl.

    python labs/10-embeddings/compare.py                                        # bm25 vs e5-small
    python labs/10-embeddings/compare.py --models e5-small,openai:text-embedding-3-small
    python labs/10-embeddings/compare.py --show cross-lingual,hebrew            # per-question ranks
    python labs/10-embeddings/compare.py --mine                                 # YOUR metrics
    python labs/10-embeddings/compare.py --models fake                          # offline plumbing

Retrievers:
  bm25             lesson 9's baseline (ragkit BM25Index, Hebrew prefix analysis)
  dense:<model>    DenseRetriever over the same chunks, cosine, exact search (numpy)
  union:<model>    BM25 and dense interleaved: 1st BM25, 1st dense, 2nd BM25, 2nd dense...
                   skipping chunks already taken. Deliberately naive: lesson 12 replaces it
                   with reciprocal rank fusion and a reranker.
Metrics (ragkit.metrics, document level): recall@1, recall@5, recall@10, MRR@10.
The "cross-lingual" row = the 6 questions tagged cross-lingual in the golden set (question in
one language, source document in the other): lesson 9's worst group.
Results: results/compare_<models>.json
"""

from __future__ import annotations

import argparse
import json
import sys

from common import RESULTS, acme_qa, bm25_index, chunks, confirm, dense_index, estimate_tokens, is_paid
from ragkit import metrics as M  # noqa: E402
from ragkit.types import Hit  # noqa: E402


class Interleave:
    """Round-robin union of two retrievers (dedup by chunk id). A Retriever."""

    def __init__(self, a, b, name: str):
        self.a, self.b, self.name = a, b, name

    def search(self, query, k=5, where=None):
        ha, hb = self.a.search(query, k, where), self.b.search(query, k, where)
        out, seen = [], set()
        for pair in zip(ha + [None] * len(hb), hb + [None] * len(ha)):
            for h in pair:
                if h is not None and h.chunk.id not in seen:
                    seen.add(h.chunk.id)
                    out.append(Hit(chunk=h.chunk, score=0.0, rank=len(out) + 1,
                                   scores=dict(h.scores), retriever=self.name))
        return out[:k]


def mine_metrics():
    import mine

    class Mine:
        recall_at_k = staticmethod(mine.recall_at_k)
        reciprocal_rank = staticmethod(mine.reciprocal_rank)
    mine.recall_at_k(["a"], ["a"], 1)            # fail early with a clear message if not done
    return Mine


def summarize_with(results, fn) -> dict:
    """Like ragkit.metrics.summarize, with recall/RR functions from `fn` (ragkit or mine)."""
    groups: dict[str, list] = {}
    for r in results:
        for g in ["ALL", r.qtype, *r.groups]:
            groups.setdefault(g, []).append(r)
    out = {}
    for g in sorted(groups, key=lambda n: (n == "ALL", n == "cross-lingual", n)):
        rs = groups[g]
        out[g] = {"n": len(rs),
                  **{f"recall@{k}": M.mean([fn.recall_at_k(r.ranked_docs, r.relevant, k) for r in rs]) for k in (1, 5, 10)},
                  "mrr": M.mean([fn.reciprocal_rank(r.ranked_docs, r.relevant, 10) for r in rs])}
    return out


def first_rank(r) -> str:
    for i, d in enumerate(r.ranked_docs, 1):
        if d in r.relevant:
            return str(i)
    return "-"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="e5-small", help="comma-separated embedder specs")
    ap.add_argument("--no-union", action="store_true")
    ap.add_argument("--show", default="cross-lingual", help="groups to list per question ('' for none)")
    ap.add_argument("--mine", action="store_true", help="compute recall/MRR with mine.py")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    qa = acme_qa()
    cs = chunks()
    retrievers = {"bm25": bm25_index(cs)}
    for spec in [s for s in args.models.split(",") if s]:
        if is_paid(spec):
            tok = estimate_tokens([c.context_text() for c in cs] + [q["question"] for q in qa])
            if not confirm(f"{spec}: up to ~{tok:,} tokens (less if cached by embed_corpus.py), "
                           f"about ${tok * 0.13 / 1e6:.4f} at most. continue?", args.yes):
                continue
        try:
            d = dense_index(spec, cs)
        except ImportError as exc:
            sys.exit(str(exc))
        retrievers[f"dense:{spec}"] = d
        if not args.no_union:
            retrievers[f"union:{spec}"] = Interleave(retrievers["bm25"], d, f"union:{spec}")

    try:
        fn = mine_metrics() if args.mine else M
    except NotImplementedError as exc:
        sys.exit(f"{exc}: implement exercise 3 in mine.py, or run without --mine")

    all_results, tables = {}, {}
    for name, r in retrievers.items():
        res = M.run_queries(r, qa, depth=10)
        all_results[name] = res
        tables[name] = summarize_with(res, fn)

    groups = list(tables["bm25"])
    print(f"\n{len(all_results['bm25'])} answerable golden questions, metrics at document level"
          + ("  (computed with mine.py)" if args.mine else ""))
    for g in groups:
        print(f"\n{g}  (n={tables['bm25'][g]['n']})")
        print(f"  {'retriever':38s} {'R@1':>6s} {'R@5':>6s} {'R@10':>6s} {'MRR':>6s}")
        for name, t in tables.items():
            row = t[g]
            print(f"  {name:38s} {row['recall@1']:6.3f} {row['recall@5']:6.3f} {row['recall@10']:6.3f} {row['mrr']:6.3f}")

    show = [s for s in args.show.split(",") if s]
    if show:
        names = list(retrievers)
        print("\nrank of the first relevant document per question ('-' = not in the top 10)")
        print("  " + " | ".join(names))
        for i, r0 in enumerate(all_results["bm25"]):
            if r0.qtype in show or any(g in show for g in r0.groups):
                ranks = [first_rank(all_results[n][i]) for n in names]
                print(f"  {r0.qid} [{r0.qtype}] {' | '.join(ranks):18s} {r0.question[:70]}")

    # questions where dense and BM25 disagree the most: what each one is good at
    for name in [n for n in retrievers if n.startswith("dense:")]:
        won = [(a, b) for a, b in zip(all_results["bm25"], all_results[name]) if b.rr(10) - a.rr(10) >= 0.5]
        lost = [(a, b) for a, b in zip(all_results["bm25"], all_results[name]) if a.rr(10) - b.rr(10) >= 0.5]
        print(f"\n{name}: clearly better than BM25 on {len(won)} questions, clearly worse on {len(lost)}")
        for a, b in won[:8]:
            print(f"  + {a.qid} [{a.qtype}] bm25 rank {first_rank(a)} -> {first_rank(b)}  {a.question[:64]}")
        for a, b in lost[:8]:
            print(f"  - {a.qid} [{a.qtype}] bm25 rank {first_rank(a)} -> {first_rank(b)}  {a.question[:64]}")

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"compare_{args.models.replace(':', '_').replace(',', '+')}.json"
    out.write_text(json.dumps({"tables": tables, "ranked": {n: {r.qid: r.ranked_docs for r in res}
                                                           for n, res in all_results.items()}},
                              ensure_ascii=False, indent=1))
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    main()

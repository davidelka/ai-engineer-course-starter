"""Exercises 7 and 8: the full pipeline, one stage at a time (ablation), and a per-question trace.

    python labs/12-advanced-retrieval/ablation.py --dense fake --llm replay --reranker fake   # offline, $0
    python labs/12-advanced-retrieval/ablation.py                                             # e5-small, replay, fake
    python labs/12-advanced-retrieval/ablation.py --reranker ce:bge-m3
    python labs/12-advanced-retrieval/ablation.py --llm anthropic:claude-haiku-5-5 --reranker llm:anthropic:claude-haiku-5-5
    python labs/12-advanced-retrieval/ablation.py --dense fake --llm replay --reranker fake --trace q041

Stages, each one adds ONE thing to the previous (same chunks, same 69 questions):
  1. BM25                                   lesson 9's baseline
  2. dense alone                            for reference (not part of the chain)
  3. BM25 + dense, interleaved              lesson 10's naive union
  4. BM25 + dense, RRF (k=60)               HybridRetriever
  5. + query rewrite                        multi + decompose + translate, fused with RRF
  6. + version filter                       drop documents whose newer version is also retrieved
  7. + rerank                               --reranker on the top 30
Printed as a list per stage: recall@5 and MRR for ALL, multi_hop, version_conflict, hebrew and
cross-lingual (with the change from the previous stage), stale documents in the top 5,
latency p50/p95 per question, and cost per question.
--trace <qid> prints the top 5 documents of every stage for one question, with the scores each
stage wrote into Hit.scores, so you can see which stage moved what.
Results: results/ablation_<dense>_<llm>_<reranker>.json
"""

from __future__ import annotations

import argparse
import json
import sys

from common import (DEFAULT_DENSE, DENSE_HELP, LLM_HELP, RESULTS, acme_qa, bm25_index, chunks,
                    confirm, dense_index, is_paid, make_llm)
from ragkit.ablation import evaluate_stage, format_stage
from ragkit.hybrid import HybridRetriever
from ragkit.query import QueryRewriter, RewritingRetriever
from ragkit.rerank import RERANKER_HELP, RerankingRetriever, make_reranker
from ragkit.types import Hit
from ragkit.versions import VersionAwareRetriever


class Interleave:
    """Lesson 10's naive union: 1st of A, 1st of B, 2nd of A, 2nd of B... without duplicates."""

    def __init__(self, a, b):
        self.a, self.b, self.name = a, b, "interleave(bm25+dense)"

    def search(self, query, k=5, where=None):
        ha, hb = self.a.search(query, k, where), self.b.search(query, k, where)
        out, seen = [], set()
        for pair in zip(ha + [None] * len(hb), hb + [None] * len(ha)):
            for h in pair:
                if h is not None and h.chunk.id not in seen:
                    seen.add(h.chunk.id)
                    out.append(Hit(chunk=h.chunk, score=0.0, rank=len(out) + 1, scores=dict(h.scores), retriever=self.name))
        return out[:k]


def build_stages(args):
    cs = chunks()
    bm25 = bm25_index(cs)
    dense = dense_index(args.dense, cs)
    hybrid = HybridRetriever({"bm25": bm25, "dense": dense}, k_rrf=60)
    rewriter = QueryRewriter(make_llm(args.llm))
    rewriting = RewritingRetriever(hybrid, rewriter, modes=("multi", "decompose", "translate"))
    versioned = VersionAwareRetriever(rewriting, mode="retrieved")
    if args.reranker.startswith("llm:"):
        reranker = make_reranker("llm:x", llm=make_llm(args.reranker[4:]))
    else:
        reranker = make_reranker(args.reranker)
        if args.reranker.startswith("ce:"):
            reranker.model
    reranked = RerankingRetriever(versioned, reranker, fetch_k=30)
    return [
        ("1. BM25", bm25, True),
        (f"2. dense alone ({args.dense}), for reference", dense, False),
        ("3. BM25 + dense, interleaved (naive union)", Interleave(bm25, dense), True),
        ("4. BM25 + dense, RRF k=60", hybrid, True),
        (f"5. + query rewrite (multi, decompose, translate; LLM {args.llm})", rewriting, True),
        ("6. + version filter (drop superseded when the newer is retrieved)", versioned, True),
        (f"7. + rerank ({args.reranker}, top 30)", reranked, True),
    ]


def trace(stages, qa, qid: str) -> None:
    q = next((x for x in qa if x["id"] == qid), None)
    if q is None:
        sys.exit(f"unknown question {qid}")
    rel = set(q["source_ids"])
    stale = [t[6:] for t in q.get("tags") or [] if t.startswith("stale:")]
    print(f"\n{qid} [{q['type']}] {q['question']}\nrelevant: {', '.join(sorted(rel))}"
          + (f"   stale (wrong old version): {', '.join(stale)}" if stale else ""))
    keys = ("bm25", "vector", "rank:bm25", "rank:dense", "rrf", "rerank")
    for name, r, _ in stages:
        hits = r.search(q["question"], k=30)
        print(f"\n{name}")
        if isinstance(r, RewritingRetriever) or hasattr(r, "rewriter"):
            for label, text in getattr(r, "last_queries", []):
                print(f"    query [{label}]: {text}")
        seen = []
        for h in hits:
            if h.chunk.doc_id in seen:
                continue
            seen.append(h.chunk.doc_id)
            sc = ", ".join(f"{k}={h.scores[k]:.4g}" for k in keys if k in h.scores)
            print(f"  {len(seen)}. {'*' if h.chunk.doc_id in rel else ' '} {h.chunk.id:30s} {sc}")
            if len(seen) == 5:
                break


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dense", default=DEFAULT_DENSE, help=DENSE_HELP)
    ap.add_argument("--llm", default="replay", help=LLM_HELP)
    ap.add_argument("--reranker", default="fake", help=RERANKER_HELP)
    ap.add_argument("--trace", default="", help="question id: show every stage's top 5 for it")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    paid = [s for s in (args.llm, args.reranker[4:] if args.reranker.startswith("llm:") else "")
            if s and is_paid(s)] + (["cohere"] if args.reranker.startswith("cohere") else [])
    if paid and not args.trace and not confirm(
            f"paid calls ({', '.join(paid)}): rewrite ~$0.015 + LLM rerank ~$0.04 for 69 questions "
            "with Haiku 5.5. continue?", args.yes):
        return
    qa = acme_qa()
    try:
        stages = build_stages(args)
    except ImportError as exc:
        sys.exit(str(exc))
    if args.trace:
        trace(stages, qa, args.trace)
        return

    reports, prev = [], None
    print(f"ablation on {sum(1 for q in qa if q['source_ids'])} answerable golden questions "
          f"(dense {args.dense}, LLM {args.llm}, reranker {args.reranker})\n")
    for name, r, chained in stages:
        rep = evaluate_stage(name, r, qa)
        print(format_stage(rep, prev=prev if chained else None))
        reports.append(rep)
        if chained:
            prev = rep
    offline = [x for x in (args.dense, args.llm, args.reranker) if x in ("fake", "replay", "llm:replay")]
    if offline:
        print(f"\nOFFLINE components: {', '.join(offline)}. Their numbers check the plumbing; they are not "
              "what e5, Claude or a cross-encoder would score. Run with real components for the real table.")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / ("ablation_" + "_".join(x.replace(":", "-") for x in (args.dense, args.llm, args.reranker)) + ".json")
    out.write_text(json.dumps([r.to_dict() for r in reports], indent=1))
    print(f"saved: {out}")


if __name__ == "__main__":
    main()

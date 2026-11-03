"""Exercise 6: rerankers on top of the hybrid retriever. Quality, latency and cost per query.

    python labs/12-advanced-retrieval/rerank_eval.py                                  # fake + llm:replay, offline
    python labs/12-advanced-retrieval/rerank_eval.py --dense e5-small --rerankers ce:mmarco,ce:bge-m3
    python labs/12-advanced-retrieval/rerank_eval.py --dense e5-small --rerankers llm:anthropic:claude-haiku-5-5
    python labs/12-advanced-retrieval/rerank_eval.py --rerankers cohere:rerank-v4.0-fast  # needs COHERE_API_KEY
    python labs/12-advanced-retrieval/rerank_eval.py --rerankers ce:bge-m3 --sweep-fetch 10,20,30,50

First stage: hybrid BM25 + dense (RRF), then the version filter ("retrieved" mode), then the
top --fetch-k candidates (default 30) go to each reranker, which keeps the best 30 in its own
order (the metrics read the top 5 and the top 10).
Rerankers (ragkit.rerank.make_reranker):
  fake                   lexical overlap, NOT a model (offline plumbing only)
  ce:mmarco              cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, ~118M params, Apache-2.0
  ce:bge-m3              BAAI/bge-reranker-v2-m3, ~568M params, Apache-2.0, ~2.3 GB download
  llm:replay             the LLM-reranker code path with a lexical judge (offline)
  llm:<llmkit spec>      e.g. llm:anthropic:claude-haiku-5-5 (~$0.0006 per question)
  cohere:<model>         Cohere Rerank over httpx (COHERE_API_KEY in .env)
For each: recall@5, MRR, latency per query (p50/p95, reranker only), cost per query.
The course sandbox cannot download from Hugging Face: cross-encoder numbers exist only on
your machine. Write them down: lesson 13 uses them.
"""

from __future__ import annotations

import argparse
import statistics
import sys

from common import DEFAULT_DENSE, DENSE_HELP, acme_qa, bm25_index, chunks, confirm, dense_index, make_llm
from ragkit import metrics as M
from ragkit.hybrid import HybridRetriever
from ragkit.rerank import RERANKER_HELP, RerankingRetriever, make_reranker
from ragkit.versions import VersionAwareRetriever

GROUPS = ["ALL", "multi_hop", "version_conflict", "hebrew", "cross-lingual", "numeric"]


def build(spec: str, args):
    if spec.startswith("llm:"):
        llm_spec = spec[4:]
        return make_reranker("llm:x", llm=make_llm(llm_spec))
    rr = make_reranker(spec)
    if spec.startswith("ce:"):
        rr.model          # load (and download once) BEFORE timing, so p50/p95 exclude it
    if spec.startswith("cohere"):
        from common import ROOT
        from llmkit import load_dotenv
        import os
        load_dotenv(str(ROOT / ".env"))
        rr.api_key = rr.api_key or os.environ.get("COHERE_API_KEY", "")
    return rr


def evaluate(name, retr, reranker, qa):
    lat, cost = [], []
    results = []
    for q in qa:
        if not q["source_ids"]:
            continue
        hits = retr.search(q["question"], k=30)
        st = getattr(reranker, "stats", None) if reranker else None
        lat.append(st.latency_s * 1000 if st else 0.0)
        cost.append(st.cost_usd if st else 0.0)
        ranked = M.dedupe(h.chunk.doc_id for h in hits)[:10]
        groups = ["cross-lingual"] if "cross-lingual" in (q.get("tags") or []) else []
        results.append(M.QueryResult(q["id"], q["type"], q["question"], list(q["source_ids"]), ranked, groups))
    return M.summarize(results), lat, cost


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dense", default=DEFAULT_DENSE, help=DENSE_HELP)
    ap.add_argument("--rerankers", default="fake,llm:replay", help=RERANKER_HELP)
    ap.add_argument("--fetch-k", type=int, default=30, help="candidates sent to the reranker")
    ap.add_argument("--sweep-fetch", default="", help="e.g. 10,20,30,50: run the FIRST reranker with each")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    qa = acme_qa()
    cs = chunks()
    try:
        first = VersionAwareRetriever(HybridRetriever({"bm25": bm25_index(cs), "dense": dense_index(args.dense, cs)}))
    except ImportError as exc:
        sys.exit(str(exc))
    specs = [s for s in args.rerankers.split(",") if s]
    # "llm:anthropic:claude-haiku-5-5" was split by the comma rule above only on commas: fine.
    paid = [s for s in specs if (s.startswith("llm:") and s != "llm:replay" and not s.startswith("llm:mock"))
            or s.startswith("cohere")]
    if paid and not confirm(f"paid rerankers {paid}: ~69 calls each (Haiku ~$0.04 total, Cohere a few cents). "
                            "continue?", args.yes):
        return

    rows = {"no reranker": evaluate("no reranker", first, None, qa) + (None,)}
    runs = [(s, args.fetch_k) for s in specs]
    if args.sweep_fetch and specs:
        runs += [(specs[0], int(f)) for f in args.sweep_fetch.split(",") if f and int(f) != args.fetch_k]
    for spec, fk in runs:
        try:
            rr = build(spec, args)
            retr = RerankingRetriever(first, rr, fetch_k=fk)
            t, lat, cost = evaluate(spec, retr, rr, qa)
        except (ImportError, RuntimeError) as exc:
            print(f"- {spec}: skipped ({exc})", file=sys.stderr)
            continue
        rows[f"{spec} @{fk}"] = (t, lat, cost, rr)

    note = {"fake": "lexical, NOT a model", "llm:replay": "offline judge, NOT Claude"}
    print(f"\nfirst stage: hybrid BM25 + {args.dense} (RRF) + version filter; reranker sees the top --fetch-k")
    for g in GROUPS:
        print(f"\n{g} (n={int(rows['no reranker'][0][g]['n'])})")
        for name, (t, lat, cost, rr) in rows.items():
            print(f"  - {name}: recall@5 {t[g]['recall@5']:.3f}, MRR {t[g]['mrr']:.3f}")
    print("\nlatency and cost of the reranking step, per query:")
    for name, (t, lat, cost, rr) in rows.items():
        if rr is None:
            continue
        p50 = statistics.median(lat)
        p95 = sorted(lat)[int(round(0.95 * (len(lat) - 1)))]
        extra = f"  [{note[name.split(' @')[0]]}]" if name.split(" @")[0] in note else ""
        load = f", model load {rr.load_s:.1f}s once" if getattr(rr, "load_s", 0) else ""
        est = " (estimated)" if rr.stats.estimated else ""
        print(f"  - {name}: p50 {p50:.1f} ms, p95 {p95:.1f} ms{load}; ${statistics.fmean(cost):.5f}/query{est}, "
              f"${sum(cost):.4f} total{extra}")


if __name__ == "__main__":
    main()

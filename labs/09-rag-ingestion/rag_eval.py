"""Exercise 7: the baseline RAG over all 79 golden questions, and its failures by question type.

    python labs/09-rag-ingestion/rag_eval.py                                     # free: extractive
    python labs/09-rag-ingestion/rag_eval.py --model anthropic:claude-haiku-5-5  # live, about $0.02
    python labs/09-rag-ingestion/rag_eval.py --model anthropic:claude-haiku-5-5 --types hebrew,version_conflict,multi_hop
    python labs/09-rag-ingestion/rag_eval.py --failures                          # list every failure

Per question type it reports:
  retrieval  doc@k (a source document is in the top-k), all@k (EVERY source document is: what
             multi-hop needs), quote@k (a chunk containing a golden quote is in the top-k)
  answer     abstain_ok (answered when answerable, "not in the documents" when not),
             cited_src (cites a golden source), stale (cites the superseded version),
             bad_cite (cites a number that was never sent)
These are cheap, exact checks, not answer correctness: lesson 13 adds an LLM judge and
fact-level scoring. Results go to results/rag_eval_<model>.jsonl (one row per question).
A paid run asks for confirmation after printing an estimate, unless --yes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB)]

from rag_common import DEFAULT_CHUNKER, MODELS_HELP, build_index, is_paid, make_llm  # noqa: E402
from llmkit.pricing import PRICES  # noqa: E402
from ragkit.acme import acme_qa  # noqa: E402
from ragkit.evaluate import answer_checks, norm  # noqa: E402
from ragkit.rag import answer, build_request  # noqa: E402

RESULTS = LAB / "results"


def estimate(index, qa, k: int, model: str) -> float:
    p = PRICES.get(model.split(":", 1)[1], PRICES["claude-haiku-5-5"])
    tokens = 0
    for q in qa:
        req = build_request(q["question"], index.search(q["question"], k=k))
        tokens += (len(req.system_text) + len(req.messages[0].text)) // 3   # generous chars/token
    return tokens * p["input"] / 1e6 + len(qa) * 200 * p["output"] / 1e6


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="extractive", help=MODELS_HELP)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--chunker", default=DEFAULT_CHUNKER)
    ap.add_argument("--types", default="", help="comma-separated question types to run")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--failures", action="store_true", help="print every failing question")
    ap.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    args = ap.parse_args()

    qa = acme_qa()
    if args.types:
        keep = set(args.types.split(","))
        qa = [q for q in qa if q["type"] in keep]
    if args.limit:
        qa = qa[: args.limit]
    index = build_index(args.chunker)
    if is_paid(args.model):
        est = estimate(index, qa, args.k, args.model)
        print(f"{len(qa)} questions on {args.model}: estimated cost ${est:.3f} (generous)")
        if not args.yes and input("continue? [y/N] ").strip().lower() != "y":
            return
    llm = make_llm(args.model)

    rows, agg = [], defaultdict(lambda: defaultdict(int))
    total_cost = 0.0
    for i, q in enumerate(qa, 1):
        ans = answer(q["question"], index, llm, k=args.k)
        total_cost += ans.cost_usd
        srcs = set(q["source_ids"])
        got = [h.chunk.doc_id for h in ans.hits]
        quotes = [(sq["source_id"], norm(sq["quote"])) for sq in q["source_quotes"]]
        ret = {"doc": bool(srcs & set(got)), "all": bool(srcs) and srcs <= set(got),
               "quote": any(h.chunk.doc_id == s and t in norm(h.chunk.text) for h in ans.hits for s, t in quotes)}
        chk = answer_checks(q, ans)
        row = {"id": q["id"], "type": q["type"], "question": q["question"], "answer": ans.text,
               "reference": q["answer"], "source_ids": q["source_ids"], "retrieved": got,
               "cited": ans.cited_doc_ids, "retrieval": ret, "checks": chk,
               "tags": q.get("tags") or [], "cost_usd": ans.cost_usd}
        rows.append(row)
        a = agg[q["type"]]
        a["n"] += 1
        if srcs:
            a["answerable"] += 1
            a["doc"] += ret["doc"]
            a["all"] += ret["all"]
            a["quote"] += ret["quote"]
            a["cited_src"] += chk["cited_source"]
        a["abstain_ok"] += chk["abstain_ok"]
        a["stale"] += chk["cited_stale"]
        a["bad_cite"] += chk["invalid_citations"] > 0
        print(f"\r  {i}/{len(qa)}  ${total_cost:.4f}", end="", file=sys.stderr)
    print(file=sys.stderr)

    print(f"\nmodel={args.model} chunker={args.chunker} k={args.k} questions={len(qa)} cost=${total_cost:.4f}\n")
    print(f"{'type':17s} {'n':>3s}  {'doc@k':>6s} {'all@k':>6s} {'quote@k':>7s}  {'abstain_ok':>10s} "
          f"{'cited_src':>9s} {'stale':>5s} {'bad_cite':>8s}")
    tot = defaultdict(int)
    for t in sorted(agg):
        a = agg[t]
        for kk, v in a.items():
            tot[kk] += v
        def frac(key, base):
            return f"{a[key]}/{base}" if base else "-"
        print(f"{t:17s} {a['n']:3d}  {frac('doc', a['answerable']):>6s} {frac('all', a['answerable']):>6s} "
              f"{frac('quote', a['answerable']):>7s}  {frac('abstain_ok', a['n']):>10s} "
              f"{frac('cited_src', a['answerable']):>9s} {a['stale']:5d} {a['bad_cite']:8d}")
    print(f"{'ALL':17s} {tot['n']:3d}  {tot['doc']}/{tot['answerable']:<3d} {tot['all']}/{tot['answerable']:<3d} "
          f"{tot['quote']}/{tot['answerable']:<3d}  {tot['abstain_ok']}/{tot['n']:<6d} {tot['cited_src']}/{tot['answerable']:<5d}"
          f" {tot['stale']:5d} {tot['bad_cite']:8d}")

    if args.failures:
        print("\nFAILURES")
        for r in rows:
            bad = []
            if r["source_ids"] and not r["retrieval"]["doc"]:
                bad.append("retrieval: no source doc in top-k")
            elif r["source_ids"] and not r["retrieval"]["all"]:
                bad.append("retrieval: not all source docs")
            if not r["checks"]["abstain_ok"]:
                bad.append("abstained wrongly" if r["source_ids"] else "answered an unanswerable question")
            if r["checks"]["cited_stale"]:
                bad.append("cited a superseded version")
            if r["checks"]["invalid_citations"]:
                bad.append("invented a citation")
            if bad:
                print(f"- {r['id']} [{r['type']}] {r['question'][:80]}\n    {'; '.join(bad)}\n"
                      f"    answer: {r['answer'][:160]}\n    should use: {r['source_ids']}  retrieved: {r['retrieved']}")
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"rag_eval_{args.model.replace(':', '_')}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nrows: {out}")


if __name__ == "__main__":
    main()

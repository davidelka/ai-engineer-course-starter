"""Exercise 6: the whole loop for one question, with every stage visible.

    python labs/09-rag-ingestion/rag_answer.py "How many vacation days can I carry over?"
    python labs/09-rag-ingestion/rag_answer.py --qid q041                       # a golden question by id
    python labs/09-rag-ingestion/rag_answer.py --qid q041 --model anthropic:claude-haiku-5-5
    python labs/09-rag-ingestion/rag_answer.py --qid q001 --where-latest       # filter out superseded docs
    python labs/09-rag-ingestion/rag_answer.py --qid q059 --show-prompt

Stages printed: RETRIEVE (top-k chunks with BM25 score, section path, date, and the terms that
scored), AUGMENT (prompt size; --show-prompt prints it), GENERATE (answer, tokens, cost), CITE
(each [n] resolved to document, section and character offsets; invented numbers flagged).
For a golden question it also prints the reference answer and which documents should be cited.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB)]

from rag_common import DEFAULT_CHUNKER, MODELS_HELP, build_index, make_llm  # noqa: E402
from ragkit.acme import acme_documents, acme_qa  # noqa: E402
from ragkit.rag import answer  # noqa: E402


def superseded_ids() -> set[str]:
    return {str(d.meta["supersedes"]) for d in acme_documents() if d.meta.get("supersedes")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="?")
    ap.add_argument("--qid", help="a golden question id, e.g. q041")
    ap.add_argument("--model", default="extractive", help=MODELS_HELP)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--chunker", default=DEFAULT_CHUNKER)
    ap.add_argument("--where-latest", action="store_true",
                    help="drop documents that a newer version supersedes (metadata filter)")
    ap.add_argument("--show-prompt", action="store_true")
    args = ap.parse_args()

    gold = None
    if args.qid:
        gold = next((q for q in acme_qa() if q["id"] == args.qid), None)
        if not gold:
            raise SystemExit(f"no golden question {args.qid}")
        question = gold["question"]
    elif args.question:
        question = args.question
    else:
        raise SystemExit("give a question or --qid")

    index = build_index(args.chunker)
    where = None
    if args.where_latest:
        old = superseded_ids()
        where = lambda c: c.doc_id not in old  # noqa: E731
    llm = make_llm(args.model)
    ans = answer(question, index, llm, k=args.k, where=where)

    print(f"QUESTION  {question}")
    if gold:
        print(f"          type={gold['type']} difficulty={gold['difficulty']} tags={gold.get('tags') or []}")
    print(f"\n1. RETRIEVE  BM25 over {len(index)} chunks ({args.chunker}), k={args.k}"
          + (", superseded documents filtered out" if where else ""))
    for i, h in enumerate(ans.hits, 1):
        c = h.chunk
        terms = {t: s for t, s in index.explain(question, c.id).items() if s > 0}
        top = ", ".join(f"{t}:{s:.1f}" for t, s in sorted(terms.items(), key=lambda x: -x[1])[:5])
        print(f"  [{i}] {h.score:5.2f}  {c.id:28s} {c.effective_date}  {c.section[:60]}")
        print(f"            terms: {top}")
    req = ans.request
    chars = len(req.system_text) + len(req.messages[0].text)
    print(f"\n2. AUGMENT   system {len(req.system_text)} chars + user {len(req.messages[0].text)} chars "
          f"(~{chars // 4} tokens)")
    if args.show_prompt:
        print("-" * 70 + "\n" + req.system_text + "\n" + "-" * 70 + "\n" + req.messages[0].text + "\n" + "-" * 70)
    r = ans.result
    print(f"\n3. GENERATE  {args.model}: {r.usage.input_tokens} in / {r.usage.output_tokens} out tokens, "
          f"${ans.cost_usd:.5f}, {r.latency_s:.2f}s")
    print("  " + ans.text.replace("\n", "\n  "))
    print("\n4. CITE")
    if not ans.citations:
        print("  no citations" + (" (abstained)" if ans.abstained else "  <- every factual sentence should cite"))
    for n in ans.citations:
        if 1 <= n <= len(ans.hits):
            c = ans.hits[n - 1].chunk
            print(f"  [{n}] -> {c.doc_id} | {c.title} | {c.section or '(no section)'} | chars {c.start}-{c.end}")
        else:
            print(f"  [{n}] -> INVALID: no source {n} was sent (the model invented it)")
    if gold:
        print(f"\nREFERENCE  {gold['answer']}")
        print(f"           should cite: {gold['source_ids'] or 'nothing (unanswerable)'}; "
              f"cited: {ans.cited_doc_ids or 'nothing'}")


if __name__ == "__main__":
    main()

"""Exercise 4: compare chunking strategies and sizes on the Acme corpus, ranked.

    python labs/09-rag-ingestion/chunk_compare.py
    python labs/09-rag-ingestion/chunk_compare.py --mine                 # add your heading_chunks
    python labs/09-rag-ingestion/chunk_compare.py --budget 600 --show-split fixed:128:0
    python labs/09-rag-ingestion/chunk_compare.py --specs fixed:256:0,heading:400:40

For every configuration (strategy:size:overlap) it chunks all 55 documents, indexes them with
BM25, and measures, for the 69 answerable golden questions (102 source quotes):

  coverage    share of golden quotes that sit fully inside ONE chunk (uses mine.quote_status
              when implemented, else the reference). A split quote can never be retrieved whole.
  q@5         share of questions whose top-5 chunks contain a golden quote
  q@budget    the same, but retrieving chunks until a TOKEN budget is full (default 1000), so big
              chunks do not win just by sending more text. This is the fair comparison.
  ctx/q       average context tokens per question at k=5 (what you pay for on every call)
  index       total tokens stored (overlap makes it bigger; for embeddings this is money)

Ranked by q@budget, then coverage, then smaller index.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
sys.path[:0] = [str(LAB), str(LAB.parents[1])]

from ragkit.acme import acme_documents, acme_qa  # noqa: E402
from ragkit.chunking import Chunker, make_chunker  # noqa: E402
from ragkit.evaluate import norm, quote_status as ref_quote_status  # noqa: E402
from ragkit.retrieval import BM25Index  # noqa: E402
from ragkit.tokens import get_tokenizer  # noqa: E402

DEFAULT_SPECS = ("fixed:128:0,fixed:256:0,fixed:256:64,fixed:512:64,recursive:128:0,recursive:256:0,"
                 "recursive:512:50,sentence:128:1,sentence:256:1,heading:400:40,heading:400:40:150,"
                 "heading:800:0:300")
RESULTS = LAB / "results"


def status_fn():
    try:
        import mine
        mine.quote_status("a", "a", ["a"])
        return mine.quote_status, "mine.quote_status"
    except (ImportError, NotImplementedError):
        return ref_quote_status, "reference quote_status (mine.quote_status not implemented yet)"


class MineChunker(Chunker):
    name = "mine-heading"

    def __init__(self, max_tokens, overlap, tokenizer):
        super().__init__(tokenizer)
        self.max_tokens, self.overlap = max_tokens, overlap

    def params(self):
        return {"max_tokens": self.max_tokens, "overlap": self.overlap}

    def split(self, doc):
        import mine
        return mine.heading_chunks(doc, self.max_tokens, self.overlap, self.tokenizer)


def budget_hits(index: BM25Index, question: str, budget: int):
    out, used = [], 0
    for h in index.search(question, k=50):
        if used + h.chunk.n_tokens > budget and out:
            break
        out.append(h)
        used += h.chunk.n_tokens
    return out


def evaluate(name: str, chunker: Chunker, docs, qa, status, budget: int, k: int) -> dict:
    chunks = chunker.split_all(docs)
    by_doc: dict[str, list[str]] = {}
    for c in chunks:
        by_doc.setdefault(c.doc_id, []).append(c.text)
    doc_text = {d.id: d.text for d in docs}
    statuses = []
    for q in qa:
        for sq in q["source_quotes"]:
            statuses.append((q["id"], sq["source_id"], sq["quote"],
                             status(sq["quote"], doc_text[sq["source_id"]], by_doc.get(sq["source_id"], []))))
    idx = BM25Index()
    idx.add(chunks)
    answerable = [q for q in qa if q["source_ids"]]
    hit_k = hit_b = ctx = 0
    for q in answerable:
        quotes = [(sq["source_id"], norm(sq["quote"])) for sq in q["source_quotes"]]
        def has(hits):
            return any(h.chunk.doc_id == s and t in norm(h.chunk.text) for h in hits for s, t in quotes)
        top = idx.search(q["question"], k=k)
        ctx += sum(h.chunk.n_tokens for h in top)
        hit_k += has(top)
        hit_b += has(budget_hits(idx, q["question"], budget))
    n = len(answerable)
    return {"spec": name, "chunks": len(chunks), "avg_tokens": sum(c.n_tokens for c in chunks) / len(chunks),
            "index_tokens": sum(c.n_tokens for c in chunks),
            "coverage": sum(s[3] == "covered" for s in statuses) / len(statuses),
            "split": [s[:3] for s in statuses if s[3] == "split"],
            "missing": [s[:3] for s in statuses if s[3] == "missing"],
            "q_at_k": hit_k / n, "q_at_budget": hit_b / n, "ctx_per_q": ctx / n}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--specs", default=DEFAULT_SPECS)
    ap.add_argument("--mine", action="store_true", help="add mine.heading_chunks (400/40)")
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--tokenizer", default="approx", help="approx (default, matches the lesson) or tiktoken")
    ap.add_argument("--show-split", default="", help="print the split quotes of this spec")
    args = ap.parse_args()

    tok = get_tokenizer(args.tokenizer)
    docs, qa = acme_documents(), acme_qa()
    status, status_name = status_fn()
    print(f"{len(docs)} docs, {sum(1 for q in qa if q['source_ids'])} answerable questions, "
          f"tokenizer={tok.name}, coverage via {status_name}\n")
    configs = [(s, make_chunker(s, tok)) for s in args.specs.split(",") if s]
    if args.mine:
        configs.append(("mine:400:40", MineChunker(400, 40, tok)))
    rows = []
    for name, ch in configs:
        try:
            rows.append(evaluate(name, ch, docs, qa, status, args.budget, args.k))
        except NotImplementedError as e:
            print(f"  skip {name}: {e}")
    rows.sort(key=lambda r: (-r["q_at_budget"], -r["coverage"], r["index_tokens"]))
    print(f"rank  {'config':20s} chunks  avg_tok  coverage  split  q@{args.k}   q@{args.budget}tok  ctx/q  index")
    for i, r in enumerate(rows, 1):
        print(f"{i:4d}  {r['spec']:20s} {r['chunks']:6d} {r['avg_tokens']:8.0f} {r['coverage']:8.1%} "
              f"{len(r['split']):6d} {r['q_at_k']:6.1%} {r['q_at_budget']:9.1%} {r['ctx_per_q']:6.0f} {r['index_tokens']:6d}")
    if args.show_split:
        r = next((x for x in rows if x["spec"] == args.show_split), None)
        if r:
            print(f"\nsplit quotes for {args.show_split}:")
            for qid, sid, quote in r["split"]:
                print(f"  {qid} {sid}: \"{quote[:90]}\"")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "chunk_compare.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nfull results: results/chunk_compare.json")


if __name__ == "__main__":
    main()

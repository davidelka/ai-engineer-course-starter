"""Exercise 6: the nearest-neighbors explorer. What is close to what, and why.

    python labs/10-embeddings/neighbors.py "כמה ימי חופשה אפשר להעביר?"           # e5-small
    python labs/10-embeddings/neighbors.py "il-central-1" --bm25                    # side by side
    python labs/10-embeddings/neighbors.py "parking" --where language=he
    python labs/10-embeddings/neighbors.py --chunk it-laptop-policy#2               # neighbors of a chunk
    python labs/10-embeddings/neighbors.py --dups 0.95                              # near-duplicate chunks
    python labs/10-embeddings/neighbors.py                                          # interactive
    python labs/10-embeddings/neighbors.py "..." --model openai:text-embedding-3-small

For each hit: rank, cosine score, chunk id, language, section path and the first line of the
text. --bm25 adds BM25's ranking for the same query, so you can see where lexical and
semantic search disagree. Try exact identifiers (il-central-1, #sec-incidents, FIDO2,
extension 5000), synonyms ("time off" vs "vacation"), Hebrew questions about English
documents, and a negation.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from common import DEFAULT_MODEL, MODEL_HELP, bm25_index, chunks, dense_index


def parse_where(items):
    if not items:
        return None
    out = {}
    for it in items:
        k, _, v = it.partition("=")
        out[k] = v.split("|") if "|" in v else v
    return out


def line(h, width=90) -> str:
    c = h.chunk
    first = " ".join(c.text.split())[:width]
    sec = c.section[:40]
    return f"{h.rank:2d}. {h.score:7.3f}  {c.id:28s} [{c.language or '?'}] {sec}\n      {first}"


def show_query(q, dense, bm25, k, where):
    print(f"\nquery: {q}" + (f"   where={where}" if where else ""))
    print(f"--- dense ({dense.embedder.model_id})")
    for h in dense.search(q, k, where):
        print(line(h))
    if bm25 is not None:
        print("--- bm25")
        hits = bm25.search(q, k, where)
        if not hits:
            print("  (no chunk shares a single term with the query)")
        for h in hits:
            print(line(h))


def neighbors_of_chunk(cid, dense, k):
    chunks_, m = dense.store.vectors()
    ids = [c.id for c in chunks_]
    if cid not in ids:
        sys.exit(f"unknown chunk id {cid}. Example ids: {', '.join(ids[:5])}")
    i = ids.index(cid)
    print(f"\nneighbors of {cid}: {' '.join(chunks_[i].text.split())[:120]}")
    hits = [h for h in dense.search_vector(m[i], k + 1) if h.chunk.id != cid][:k]
    for r, h in enumerate(hits, 1):
        h.rank = r
        print(line(h))


def near_duplicates(dense, threshold):
    chunks_, m = dense.store.vectors()
    sim = m @ m.T
    np.fill_diagonal(sim, -1)
    pairs = [(float(sim[i, j]), chunks_[i].id, chunks_[j].id)
             for i, j in zip(*np.nonzero(np.triu(sim, 1) >= threshold))
             if chunks_[i].doc_id != chunks_[j].doc_id]
    pairs.sort(reverse=True)
    print(f"\n{len(pairs)} chunk pairs from DIFFERENT documents with cosine >= {threshold}:")
    for s, a, b in pairs[:40]:
        print(f"  {s:.3f}  {a:30s} {b}")
    print("Near-duplicates waste top-k slots (two copies of one fact) and, across versions,"
          " put the stale policy right next to the current one.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=MODEL_HELP)
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--bm25", action="store_true", help="also show BM25's ranking")
    ap.add_argument("--where", action="append", help="metadata filter key=value (value a|b = any of)")
    ap.add_argument("--chunk", help="show the neighbors of this chunk id")
    ap.add_argument("--dups", type=float, help="list near-duplicate chunk pairs above this cosine")
    args = ap.parse_args()

    cs = chunks()
    try:
        dense = dense_index(args.model, cs)
    except ImportError as exc:
        sys.exit(str(exc))
    bm25 = bm25_index(cs) if args.bm25 else None
    where = parse_where(args.where)
    if args.chunk:
        neighbors_of_chunk(args.chunk, dense, args.k)
    elif args.dups is not None:
        near_duplicates(dense, args.dups)
    elif args.query:
        show_query(args.query, dense, bm25, args.k, where)
    else:
        print("type a query (empty line to quit). Prefix with 'bm25:' to compare with BM25.")
        bm25 = bm25 or bm25_index(cs)
        while True:
            try:
                q = input("\n> ").strip()
            except EOFError:
                break
            if not q:
                break
            if q.startswith("bm25:"):
                show_query(q[5:].strip(), dense, bm25, args.k, where)
            else:
                show_query(q, dense, None, args.k, where)


if __name__ == "__main__":
    main()

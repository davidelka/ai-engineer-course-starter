"""Exercise 4: embed the Acme corpus with a local model and with OpenAI, cached on disk.

    python labs/10-embeddings/embed_corpus.py                                   # e5-small, free
    python labs/10-embeddings/embed_corpus.py                                   # again: all cache hits
    python labs/10-embeddings/embed_corpus.py --model openai:text-embedding-3-small   # ~$0.001
    python labs/10-embeddings/embed_corpus.py --model openai:text-embedding-3-large   # ~$0.006
    python labs/10-embeddings/embed_corpus.py --model e5-small --mine-cache     # YOUR embed_with_cache
    python labs/10-embeddings/embed_corpus.py --model fake                      # offline plumbing check

What is embedded: chunk.context_text() (title > section path, newline, chunk text) for every
chunk of lesson 9's baseline chunker (heading:400:40:150, ~210 chunks), plus the 79 golden
questions as queries (so compare.py and dims.py run without new model calls).
Cache: labs/10-embeddings/results/cache/<model>.sqlite, key = sha256(model_id, kind, text).
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

from common import (CACHE_DIR, DEFAULT_MODEL, MODEL_HELP, ROOT, acme_qa, chunks, confirm, embedder,
                    estimate_tokens, is_paid)
from ragkit.embed import SqliteVectorCache, cache_file  # noqa: E402
from ragkit.embed.openai import estimate_cost  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", action="append", help=MODEL_HELP + " (repeatable)")
    ap.add_argument("--mine-cache", action="store_true", help="use mine.embed_with_cache")
    ap.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    args = ap.parse_args()
    specs = args.model or [DEFAULT_MODEL]

    cs = chunks()
    docs = [c.context_text() for c in cs]
    queries = [q["question"] for q in acme_qa()]
    print(f"{len(docs)} chunks ({sum(map(len, docs)):,} characters), {len(queries)} golden questions")

    for spec in specs:
        print(f"\n=== {spec} ===")
        if is_paid(spec):
            model = spec.split(":")[1]
            tok = estimate_tokens(docs + queries)
            print(f"estimated {tok:,} tokens (generous, ~3 chars/token) -> about ${estimate_cost(tok, model):.4f}"
                  " if nothing is cached yet")
            if not confirm("continue?", args.yes):
                continue
        try:
            emb = embedder(spec)
        except ImportError as exc:
            sys.exit(str(exc))
        inner = emb.inner
        t0 = time.perf_counter()
        try:
            if args.mine_cache:
                import mine
                cache = SqliteVectorCache(cache_file(CACHE_DIR, emb.model_id))
                dv = mine.embed_with_cache(docs, inner.embed_documents, cache, emb.model_id, "document")
                qv = mine.embed_with_cache(queries, inner.embed_queries, cache, emb.model_id, "query")
                print("(cache handled by mine.embed_with_cache)")
            else:
                dv = emb.embed_documents(docs)
                qv = emb.embed_queries(queries)
        except ImportError as exc:
            sys.exit(str(exc))
        except NotImplementedError as exc:
            sys.exit(f"{exc}: implement exercise 4 in mine.py, or run without --mine-cache")
        secs = time.perf_counter() - t0
        print(f"documents {dv.shape}, queries {qv.shape}, dtype {dv.dtype}, in {secs:.1f}s")
        print(f"norms: min {np.linalg.norm(dv, axis=1).min():.4f} max {np.linalg.norm(dv, axis=1).max():.4f}")
        mb = dv.nbytes / 1e6
        print(f"memory: {dv.shape[0]} x {dv.shape[1]} x 4 bytes = {mb:.2f} MB "
              f"(1M chunks would be {dv.shape[1] * 4 * 1e6 / 1e9:.2f} GB as float32)")
        if not args.mine_cache:
            s = emb.stats
            print(f"cache: {s['hits']} hits, {s['misses']} embedded now, {s['calls']} model calls")
        f = cache_file(CACHE_DIR, emb.model_id)
        print(f"cache file: {f.relative_to(ROOT)} ({f.stat().st_size / 1e6:.2f} MB)")
        if hasattr(inner, "tokens"):
            print(f"OpenAI billed tokens this run: {inner.tokens:,}  cost ${inner.cost_usd:.5f}  "
                  f"requests {inner.requests}")


if __name__ == "__main__":
    main()

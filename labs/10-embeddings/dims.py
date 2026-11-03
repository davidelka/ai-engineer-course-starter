"""Exercise 8: fewer dimensions (Matryoshka truncation): how much recall do we lose, how much
memory do we save?

    python labs/10-embeddings/dims.py                                         # e5-small: 384 -> 48
    python labs/10-embeddings/dims.py --model openai:text-embedding-3-small   # 1536 -> 64 (Matryoshka-trained)
    python labs/10-embeddings/dims.py --model qwen3-0.6b                      # optional, 1.2 GB download
    python labs/10-embeddings/dims.py --model openai:text-embedding-3-small --api-check   # 2 paid calls

For each size d we keep the first d numbers of every cached vector (documents AND queries),
re-normalize, and rerun the golden-set retrieval (recall@5, MRR@10, document level). No new
embedding calls are needed if embed_corpus.py already ran for that model.

Matryoshka Representation Learning trains a model so that every PREFIX of the vector is
itself a good embedding: the first 64 numbers carry the coarse meaning, later ones refine it.
OpenAI's text-embedding-3 models and Qwen3-Embedding are trained that way; multilingual-e5
is not, so its curve should drop faster. Compare the two curves; that is the exercise.

--api-check asks OpenAI for one text with dimensions=256 and compares it to our own
truncate-and-renormalize of the full vector (the guide says the API "removes numbers from the
end"; this shows whether the two are the same vector on your account today).
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from common import DEFAULT_MODEL, MODEL_HELP, acme_qa, chunks, embedder, is_paid, load_dotenv, ROOT
from ragkit.dense import DenseRetriever  # noqa: E402
from ragkit.metrics import run_queries, summarize  # noqa: E402
from ragkit.vectors import NumpyVectorStore, truncate_dims  # noqa: E402


class Truncated:
    """An Embedder view that keeps the first `dims` numbers of another embedder's vectors."""

    def __init__(self, inner, dims: int):
        self.inner, self.dims = inner, dims
        self.model_id = f"{inner.model_id}|first{dims}"
        self.dim, self.normalized = dims, True

    def embed_documents(self, texts):
        return truncate_dims(self.inner.embed_documents(texts), self.dims)

    def embed_queries(self, texts):
        return truncate_dims(self.inner.embed_queries(texts), self.dims)


def api_check(model: str) -> None:
    from ragkit.embed import OpenAIEmbedder
    load_dotenv(str(ROOT / ".env"))
    text = "Up to 5 unused vacation days may be carried over to the next calendar year."
    full = OpenAIEmbedder(model).embed_documents([text])
    short_api = OpenAIEmbedder(model, dims=256).embed_documents([text])
    short_ours = truncate_dims(full, 256)
    cos = float(short_api[0] @ short_ours[0])
    print(f"\nAPI dimensions=256 vs our truncate(full, 256): cosine {cos:.6f} "
          f"({'the same vector' if cos > 0.9999 else 'NOT the same: say so in your notes'})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL, help=MODEL_HELP)
    ap.add_argument("--dims", default="", help="comma-separated sizes (default: halve while the size is at least 32, so 384 ends at 48)")
    ap.add_argument("--api-check", action="store_true", help="OpenAI only: compare API dims vs truncation")
    args = ap.parse_args()

    cs, qa = chunks(), acme_qa()
    try:
        emb = embedder(args.model)
        full = emb.embed_documents([c.context_text() for c in cs[:1]])
    except ImportError as exc:
        sys.exit(str(exc))
    D = full.shape[1]
    sizes = [int(x) for x in args.dims.split(",")] if args.dims else []
    if not sizes:
        d = D
        while d >= 32:
            sizes.append(d)
            d //= 2
    print(f"model {emb.model_id}, full size {D}\n")
    print(f"  {'dims':>5s} {'R@1':>6s} {'R@5':>6s} {'MRR':>6s}  {'x-ling R@5':>10s}  {'bytes/vec':>9s} {'1M chunks':>9s}")
    for d in sizes:
        r = DenseRetriever(Truncated(emb, d), NumpyVectorStore())
        r.add(cs)
        t = summarize(run_queries(r, qa, depth=10))
        a, x = t["ALL"], t.get("cross-lingual", {"recall@5": float("nan")})
        print(f"  {d:5d} {a['recall@1']:6.3f} {a['recall@5']:6.3f} {a['mrr']:6.3f}  {x['recall@5']:10.3f}  "
              f"{4 * d:9d} {4 * d * 1e6 / 1e9:7.2f} GB")
    print("\nbytes/vec is float32. int8 quantization would divide it by 4 again, binary by 32"
          " (lesson 11 measures what that costs in recall).")
    if emb.stats["misses"]:
        print(f"(embedded {emb.stats['misses']} new texts for this run; the rest came from the cache)")
    if args.api_check:
        if not is_paid(args.model):
            sys.exit("--api-check needs an openai:<model> spec")
        api_check(args.model.split(":")[1])


if __name__ == "__main__":
    main()

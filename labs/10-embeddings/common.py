"""Shared by the lesson 10 scripts: paths, the Acme chunks, embedders with a disk cache."""

from __future__ import annotations

import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
for p in (str(ROOT), str(LAB)):
    if p not in sys.path:
        sys.path.insert(0, p)

from llmkit import load_dotenv  # noqa: E402
from ragkit.acme import acme_chunks, acme_documents, acme_qa  # noqa: E402
from ragkit.chunking import make_chunker  # noqa: E402
from ragkit.dense import DenseRetriever  # noqa: E402
from ragkit.embed import EMBEDDER_HELP, CachedEmbedder, make_embedder  # noqa: E402
from ragkit.retrieval import BM25Index  # noqa: E402

RESULTS = LAB / "results"
CACHE_DIR = RESULTS / "cache"            # one SQLite file per embedding model (git-ignored)
DEFAULT_CHUNKER = "heading:400:40:150"   # the same chunks as lesson 9's baseline
DEFAULT_MODEL = "e5-small"
MODEL_HELP = EMBEDDER_HELP


def chunks(chunker: str = DEFAULT_CHUNKER):
    return acme_chunks(make_chunker(chunker, "approx"))


def is_paid(spec: str) -> bool:
    return spec.startswith("openai:")


def embedder(spec: str, *, cache: bool = True):
    """make_embedder + .env + disk cache. Prints which model produced the numbers."""
    if is_paid(spec):
        load_dotenv(str(ROOT / ".env"))
    emb = make_embedder(spec, cache_dir=CACHE_DIR if cache else None)
    if spec.startswith("fake"):
        print("note: model 'fake' is a hashing embedder (lexical, NOT semantic). Use it to test "
              "the plumbing, not to judge embeddings.", file=sys.stderr)
    return emb


def dense_index(spec: str, chunk_list=None, store=None) -> DenseRetriever:
    t0 = time.perf_counter()
    emb = embedder(spec)
    d = DenseRetriever(emb, store)
    d.add(chunk_list if chunk_list is not None else chunks())
    if isinstance(emb, CachedEmbedder):
        s = emb.stats
        print(f"[{spec}] {len(d)} chunks indexed in {time.perf_counter() - t0:.1f}s "
              f"(cache hits {s['hits']}, embedded now {s['misses']})", file=sys.stderr)
    return d


def bm25_index(chunk_list=None) -> BM25Index:
    idx = BM25Index()
    idx.add(chunk_list if chunk_list is not None else chunks())
    return idx


def estimate_tokens(texts) -> int:
    """Generous estimate for cost confirmation: ~3 characters per token (Hebrew is denser)."""
    return sum(len(t) for t in texts) // 3 + len(texts)


def confirm(prompt: str, yes: bool) -> bool:
    if yes:
        return True
    return input(f"{prompt} [y/N] ").strip().lower() == "y"


__all__ = ["LAB", "ROOT", "RESULTS", "CACHE_DIR", "DEFAULT_CHUNKER", "DEFAULT_MODEL", "MODEL_HELP",
           "chunks", "embedder", "dense_index", "bm25_index", "is_paid", "estimate_tokens", "confirm",
           "acme_qa", "acme_documents"]

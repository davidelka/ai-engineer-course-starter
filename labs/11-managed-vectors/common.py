"""Shared by the lesson 11 scripts: paths, the Acme chunks and vectors, stores, synthetic data.

Embeddings come from lesson 10's disk cache (labs/10-embeddings/results/cache/), so if you
ran lesson 10 with e5-small, nothing is embedded again. `--model fake` works offline
(hashing embedder: lexical, NOT semantic; fine for plumbing, useless for judging quality).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
for p in (str(ROOT), str(LAB)):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np  # noqa: E402

from llmkit import load_dotenv  # noqa: E402
from ragkit.acme import acme_chunks, acme_qa  # noqa: E402
from ragkit.chunking import make_chunker  # noqa: E402
from ragkit.embed import make_embedder  # noqa: E402
from ragkit.vectors import NumpyVectorStore  # noqa: E402
from ragkit.vectors.bench import synth_clustered  # noqa: E402

RESULTS = LAB / "results"
L10_CACHE = ROOT / "labs" / "10-embeddings" / "results" / "cache"   # reuse lesson 10's vectors
DEFAULT_CHUNKER = "heading:400:40:150"
DEFAULT_MODEL = "e5-small"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
PG_DSN = os.environ.get("PGVECTOR_DSN", "postgresql://ragkit:ragkit@localhost:5432/ragkit")


def chunks(chunker: str = DEFAULT_CHUNKER):
    return acme_chunks(make_chunker(chunker, "approx"))


def embedder(spec: str = DEFAULT_MODEL):
    if spec.startswith("openai:"):
        load_dotenv(str(ROOT / ".env"))
    if spec.startswith("fake"):
        print("note: model 'fake' is a hashing embedder (lexical, NOT semantic): plumbing only.",
              file=sys.stderr)
    return make_embedder(spec, cache_dir=L10_CACHE)


def acme_vectors(spec: str = DEFAULT_MODEL):
    """(chunks, chunk vectors, golden questions, question vectors) for the Acme corpus."""
    t0 = time.perf_counter()
    emb = embedder(spec)
    ch = chunks()
    vecs = emb.embed_documents([c.context_text() for c in ch])
    qa = acme_qa()
    qv = emb.embed_queries([q["question"] for q in qa])
    print(f"[{spec}] {len(ch)} chunks, {len(qa)} questions, dim {vecs.shape[1]} "
          f"({time.perf_counter() - t0:.1f}s)", file=sys.stderr)
    return ch, vecs, qa, qv


def numpy_store(ch, vecs) -> NumpyVectorStore:
    s = NumpyVectorStore(metric="cosine")
    s.add(ch, vecs)
    return s


def synthetic(n: int, dim: int = 384, queries: int = 300, clusters: int = 2000, seed: int = 0,
              noise: float = 1.4):
    """Clustered unit vectors (like embeddings) and held-out queries from the same clusters.
    Bigger noise = clusters overlap more = harder for ANN (real embeddings sit in between)."""
    x = synth_clustered(n + queries, dim, clusters=clusters, noise=noise, seed=seed)
    return x[:n], x[n:]


def qdrant_client_or_exit(url: str):
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        sys.exit("needs qdrant-client: uv pip install -r labs/11-managed-vectors/requirements.txt")
    c = QdrantClient(url=url, timeout=120)
    try:
        c.get_collections()
    except Exception as exc:  # pragma: no cover - needs the server
        sys.exit(f"cannot reach Qdrant at {url} ({type(exc).__name__}). Start it with:\n"
                 f"  docker compose -f labs/11-managed-vectors/compose.yaml up -d")
    return c


def fmt_mb(b: float) -> str:
    return f"{b / 1024 ** 2:,.1f} MB" if b < 1024 ** 3 else f"{b / 1024 ** 3:,.2f} GB"


__all__ = ["LAB", "ROOT", "RESULTS", "L10_CACHE", "DEFAULT_MODEL", "QDRANT_URL", "PG_DSN", "chunks",
           "embedder", "acme_vectors", "numpy_store", "synthetic", "qdrant_client_or_exit", "fmt_mb"]

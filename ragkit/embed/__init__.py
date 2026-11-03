"""Embeddings (lesson 10): the Embedder protocol, three implementations, and a disk cache.

    from ragkit.embed import make_embedder
    emb = make_embedder("e5-small", cache_dir=".cache/embeddings")   # local, free
    emb = make_embedder("openai:text-embedding-3-small")             # paid, ~$0.001 for Acme
    emb = make_embedder("openai:text-embedding-3-small:256")         # Matryoshka: 256 dims
    emb = make_embedder("fake")                                       # tests: hashing, NOT semantic

Specs: fake[:dim] | e5-small | e5-base | bge-m3 | qwen3-0.6b | st:<hf model id> |
openai:<model>[:dims]. With cache_dir, the embedder is wrapped in CachedEmbedder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .base import BaseEmbedder, Embedder
from .cache import CachedEmbedder, SqliteVectorCache, cache_file, cache_key, embed_with_cache
from .fake import HashingEmbedder
from .local import PRESETS, SentenceTransformerEmbedder
from .openai import OpenAIEmbedder

EMBEDDER_HELP = ("fake[:dim] (offline hashing, NOT semantic) | e5-small | e5-base | bge-m3 | "
                 "qwen3-0.6b | st:<hf id> | openai:text-embedding-3-small[:dims] | "
                 "openai:text-embedding-3-large[:dims]")


def make_embedder(spec: str = "fake", *, cache_dir: Optional[Union[str, Path]] = None,
                  **kw) -> BaseEmbedder:
    kind, _, rest = spec.partition(":")
    if kind == "fake":
        emb: BaseEmbedder = HashingEmbedder(int(rest) if rest else 256)
    elif kind in PRESETS:
        emb = SentenceTransformerEmbedder.preset(kind, **kw)
    elif kind == "st":
        emb = SentenceTransformerEmbedder(rest, **kw)
    elif kind == "openai":
        model, _, dims = rest.partition(":")
        emb = OpenAIEmbedder(model or "text-embedding-3-small", int(dims) if dims else None, **kw)
    else:
        raise ValueError(f"unknown embedder {spec!r}. Known: {EMBEDDER_HELP}")
    return CachedEmbedder(emb, cache_dir) if cache_dir else emb


__all__ = ["Embedder", "BaseEmbedder", "HashingEmbedder", "SentenceTransformerEmbedder", "PRESETS",
           "OpenAIEmbedder", "CachedEmbedder", "SqliteVectorCache", "cache_key", "cache_file",
           "embed_with_cache", "make_embedder", "EMBEDDER_HELP"]

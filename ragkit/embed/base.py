"""The Embedder contract (lesson 10).

    emb.embed_documents(texts) -> np.ndarray (len(texts), emb.dim), float32
    emb.embed_queries(texts)   -> np.ndarray (len(texts), emb.dim), float32
    emb.model_id               str: everything that changes the vectors (model, dims, prefixes)
    emb.dim                    int (may be known only after the first call for local models)
    emb.normalized             bool: rows have length 1, so dot == cosine

Why two methods and not one: many retrieval models are ASYMMETRIC. They were trained on
(short question, long passage) pairs with a marker on each side, e.g. multilingual-e5 expects
"query: " before questions and "passage: " before documents; without them quality drops
(the model card says so explicitly). Others (bge-m3, OpenAI text-embedding-3) use no markers,
and then both methods do the same thing. Keeping the distinction in the interface means the
caller never has to know which kind of model it holds.

`model_id` is the cache key prefix (ragkit.embed.cache): two embedders with the same model_id
MUST produce the same vector for the same (kind, text). So it includes the dims and the
prefixes, not just the model name.

What to embed for a chunk: `chunk.context_text()` (title > section path + text), the same
text BM25 indexes. A chunk that says "Up to 5 days may be carried over" never says
"vacation"; its title does.
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

import numpy as np


@runtime_checkable
class Embedder(Protocol):
    model_id: str
    dim: int
    normalized: bool

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray: ...

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray: ...


class BaseEmbedder:
    """Shared plumbing: subclasses implement _embed(texts, kind) for kind in {"query", "document"}."""

    model_id: str = "base"
    dim: int = 0
    normalized: bool = True
    batch_size: int = 64

    def _embed(self, texts: list[str], kind: str) -> np.ndarray:  # pragma: no cover - abstract
        raise NotImplementedError

    def _run(self, texts: Sequence[str], kind: str) -> np.ndarray:
        texts = list(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        parts = [self._embed(texts[i:i + self.batch_size], kind)
                 for i in range(0, len(texts), self.batch_size)]
        out = np.ascontiguousarray(np.vstack(parts), dtype=np.float32)
        if out.shape[0] != len(texts):
            raise RuntimeError(f"{self.model_id}: got {out.shape[0]} vectors for {len(texts)} texts")
        self.dim = out.shape[1]
        return out

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._run(texts, "document")

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._run(texts, "query")

    def embed_query(self, text: str) -> np.ndarray:
        """Convenience: one query -> one 1-D vector."""
        return self.embed_queries([text])[0]

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.model_id!r}, dim={self.dim})"

"""HashingEmbedder: a deterministic, free, offline stand-in for an embedding model.

It is NOT a semantic model. It hashes words (ragkit's analyzer, with Hebrew prefix variants)
and character 4-grams into `dim` buckets with a random sign (the "hashing trick"), then
L2-normalizes. Cosine between two such vectors measures shared words and word pieces, i.e.
it behaves like a fuzzy lexical retriever: "vacation" and "חופשה" share nothing, so it will
NOT fix lesson 9's cross-language failures. That is on purpose: tests need vectors that are
stable across machines and versions, and you should never mistake its numbers for a real
model's. Every script prints which embedder produced its numbers.

Hashing uses blake2b, not Python's hash(), which is randomized per process.
"""

from __future__ import annotations

import hashlib

import numpy as np

from ..clean import normalize
from ..retrieval.analyzer import analyze
from .base import BaseEmbedder


def _bucket(token: str, dim: int) -> tuple[int, float]:
    h = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "little")
    return h % dim, (1.0 if (h >> 63) & 1 else -1.0)


class HashingEmbedder(BaseEmbedder):
    def __init__(self, dim: int = 256, *, char_ngrams: int = 4, word_weight: float = 1.0,
                 ngram_weight: float = 0.3):
        self.dim = dim
        self.char_ngrams = char_ngrams
        self.word_weight, self.ngram_weight = word_weight, ngram_weight
        self.model_id = f"fake:hashing-{dim}-n{char_ngrams}"
        self.normalized = True
        self.batch_size = 512
        self.calls = 0              # how many batches were embedded (tests check caching)
        self.texts_embedded = 0

    def _vector(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for w in analyze(normalize(text)):
            i, s = _bucket("w:" + w, self.dim)
            v[i] += s * self.word_weight
            if self.char_ngrams and len(w) > self.char_ngrams:
                padded = f"<{w}>"
                for j in range(len(padded) - self.char_ngrams + 1):
                    i, s = _bucket("g:" + padded[j:j + self.char_ngrams], self.dim)
                    v[i] += s * self.ngram_weight
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def _embed(self, texts: list[str], kind: str) -> np.ndarray:
        # symmetric: queries and documents are embedded the same way
        self.calls += 1
        self.texts_embedded += len(texts)
        return np.stack([self._vector(t) for t in texts])

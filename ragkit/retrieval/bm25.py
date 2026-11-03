"""BM25: the lexical baseline that needs no embeddings, no GPU and no API key.

score(q, d) = sum over query terms t of
    idf(t) * tf(t,d) * (k1 + 1) / (tf(t,d) + k1 * (1 - b + b * |d| / avgdl))
    idf(t)  = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))        (Lucene's non-negative idf)

k1 (default 1.2) saturates term frequency: the 5th "vacation" adds little after the 2nd.
b (default 0.75) normalizes by length: a match in a short chunk counts more than in a long one.
Same defaults as Elasticsearch/Lucene.

Pure Python on purpose: ~80 lines you can read, Hebrew-aware analysis, metadata filters, and
add/remove for incremental ingestion. For big corpora use bm25s (fast, maintained) or a
search engine; rank-bm25, the classic package, has not been released since 2022.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from ..types import Chunk, Hit
from .analyzer import analyze
from .base import Where, matches


class BM25Index:
    name = "bm25"

    def __init__(self, k1: float = 1.2, b: float = 0.75, *, with_context: bool = True,
                 analyzer: Optional[Callable[[str], list[str]]] = None):
        self.k1, self.b = k1, b
        self.with_context = with_context          # index title + section path with the text
        self.analyzer = analyzer or analyze
        self.chunks: dict[str, Chunk] = {}
        self.tfs: dict[str, Counter] = {}
        self._stats: Optional[tuple[dict[str, int], float]] = None

    # -- building
    def _text(self, c: Chunk) -> str:
        return c.context_text() if self.with_context else c.text

    def add(self, chunks: Iterable[Chunk]) -> None:
        for c in chunks:
            self.chunks[c.id] = c
            self.tfs[c.id] = Counter(self.analyzer(self._text(c)))
        self._stats = None

    def remove(self, doc_id: str) -> int:
        ids = [cid for cid, c in self.chunks.items() if c.doc_id == doc_id]
        for cid in ids:
            del self.chunks[cid], self.tfs[cid]
        self._stats = None
        return len(ids)

    def __len__(self) -> int:
        return len(self.chunks)

    def _df(self) -> tuple[dict[str, int], float]:
        if self._stats is None:
            df: Counter = Counter()
            total = 0
            for tf in self.tfs.values():
                df.update(tf.keys())
                total += sum(tf.values())
            self._stats = (dict(df), total / max(1, len(self.tfs)))
        return self._stats

    # -- searching
    def idf(self, term: str) -> float:
        df, _ = self._df()
        n = len(self.tfs)
        d = df.get(term, 0)
        return math.log(1 + (n - d + 0.5) / (d + 0.5))

    def score(self, q_terms: list[str], cid: str) -> float:
        _, avgdl = self._df()
        tf = self.tfs[cid]
        dl = sum(tf.values())
        s = 0.0
        for t in q_terms:
            f = tf.get(t, 0)
            if f:
                s += self.idf(t) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / avgdl))
        return s

    def search(self, query: str, k: int = 5, where: Where = None) -> list[Hit]:
        q_terms = list(dict.fromkeys(self.analyzer(query)))  # each query term once
        scored = []
        for cid, c in self.chunks.items():
            if not matches(c, where):
                continue
            s = self.score(q_terms, cid)
            if s > 0:
                scored.append((s, cid))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [Hit(chunk=self.chunks[cid], score=s, rank=i + 1, scores={"bm25": s}, retriever=self.name)
                for i, (s, cid) in enumerate(scored[:k])]

    def explain(self, query: str, chunk_id: str) -> dict[str, float]:
        """Per-term contribution to one chunk's score: why did this chunk rank here?"""
        _, avgdl = self._df()
        tf = self.tfs[chunk_id]
        dl = sum(tf.values())
        out = {}
        for t in dict.fromkeys(self.analyzer(query)):
            f = tf.get(t, 0)
            out[t] = round(self.idf(t) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / avgdl)), 3) if f else 0.0
        return out

    # -- persistence (chunks only; term stats are rebuilt on load, it takes milliseconds)
    def save(self, path: Union[str, Path]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for c in self.chunks.values():
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Union[str, Path], **kw) -> "BM25Index":
        idx = cls(**kw)
        with open(path, encoding="utf-8") as f:
            idx.add(Chunk.from_dict(json.loads(line)) for line in f if line.strip())
        return idx

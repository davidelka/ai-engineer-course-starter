"""Embedding cache: never pay twice for the same vector.

Key = sha256(model_id, kind, text). The text is the exact string sent to the model (for a
chunk, its context_text()), so editing a document changes only the keys of the chunks whose
text changed, and switching models or dims changes every key (model_id includes them).
This works together with lesson 9's manifest: the manifest decides WHICH documents to
re-chunk; the cache makes re-embedding unchanged chunks free even when the chunker moved a
boundary somewhere else in the document.

Storage: one SQLite file per model in `cache_dir` (stdlib, atomic writes, safe to Ctrl-C).
Rows: key TEXT PRIMARY KEY, dim INTEGER, vec BLOB (float32 bytes).

    emb = CachedEmbedder(SentenceTransformerEmbedder.preset("e5-small"), ".cache/embeddings")
    emb.embed_documents(texts)     # first run: misses, calls the model
    emb.embed_documents(texts)     # second run: all hits, no model call
    print(emb.stats)               # {'hits': ..., 'misses': ..., 'calls': ...}
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import MutableMapping
from pathlib import Path
from typing import Callable, Iterator, Optional, Sequence, Union

import numpy as np

from .base import BaseEmbedder, Embedder

SEP = "\x1f"


def cache_key(model_id: str, kind: str, text: str) -> str:
    """sha256 hex of model_id, kind and text joined by the unit separator \\x1f."""
    return hashlib.sha256(f"{model_id}{SEP}{kind}{SEP}{text}".encode("utf-8")).hexdigest()


def embed_with_cache(texts: Sequence[str], embed_fn: Callable[[list[str]], np.ndarray],
                     cache: MutableMapping, model_id: str, kind: str = "document") -> np.ndarray:
    """Vectors for `texts` in order, calling embed_fn ONCE with only the missing texts
    (each distinct missing text once, in first-seen order), and storing them in `cache`."""
    texts = list(texts)
    keys = [cache_key(model_id, kind, t) for t in texts]
    found: dict[str, np.ndarray] = {}
    missing: dict[str, str] = {}
    for k, t in zip(keys, texts):
        if k in found or k in missing:
            continue
        v = cache.get(k)
        if v is None:
            missing[k] = t
        else:
            found[k] = np.asarray(v, dtype=np.float32)
    if missing:
        vecs = np.asarray(embed_fn(list(missing.values())), dtype=np.float32)
        if vecs.shape[0] != len(missing):
            raise RuntimeError(f"embed_fn returned {vecs.shape[0]} vectors for {len(missing)} texts")
        for k, v in zip(missing, vecs):
            cache[k] = v
            found[k] = v
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    return np.stack([found[k] for k in keys]).astype(np.float32)


class SqliteVectorCache(MutableMapping):
    """A dict-like key -> float32 vector store in one SQLite file."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path))
        self._db.execute("CREATE TABLE IF NOT EXISTS vec (key TEXT PRIMARY KEY, dim INTEGER, vec BLOB)")
        self._db.commit()

    def __getitem__(self, key: str) -> np.ndarray:
        row = self._db.execute("SELECT vec FROM vec WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return np.frombuffer(row[0], dtype=np.float32).copy()

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key: str, value) -> None:
        v = np.asarray(value, dtype=np.float32).ravel()
        self._db.execute("INSERT OR REPLACE INTO vec VALUES (?, ?, ?)", (key, v.shape[0], v.tobytes()))
        self._db.commit()

    def update_many(self, items: dict) -> None:
        rows = [(k, int(np.asarray(v).size), np.asarray(v, dtype=np.float32).tobytes()) for k, v in items.items()]
        self._db.executemany("INSERT OR REPLACE INTO vec VALUES (?, ?, ?)", rows)
        self._db.commit()

    def __delitem__(self, key: str) -> None:
        self._db.execute("DELETE FROM vec WHERE key = ?", (key,))
        self._db.commit()

    def __iter__(self) -> Iterator[str]:
        return iter([r[0] for r in self._db.execute("SELECT key FROM vec")])

    def __len__(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM vec").fetchone()[0]

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def close(self) -> None:
        self._db.close()


def cache_file(cache_dir: Union[str, Path], model_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", model_id)[:80]
    return Path(cache_dir) / f"{safe}-{hashlib.sha1(model_id.encode()).hexdigest()[:8]}.sqlite"


class CachedEmbedder(BaseEmbedder):
    """Wraps any Embedder; same interface, plus `stats`."""

    def __init__(self, inner: Embedder, cache_dir: Union[str, Path, None] = None, *,
                 cache: Optional[MutableMapping] = None):
        self.inner = inner
        self.model_id = inner.model_id
        self.normalized = inner.normalized
        self.dim = inner.dim
        self.cache = cache if cache is not None else SqliteVectorCache(cache_file(cache_dir or ".cache/embeddings", inner.model_id))
        self.hits = self.misses = self.calls = 0

    @property
    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "calls": self.calls}

    def _cached(self, texts: Sequence[str], kind: str, fn) -> np.ndarray:
        texts = list(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        pending: dict = {}

        def call(batch: list[str]) -> np.ndarray:
            self.calls += 1
            self.misses += len(batch)
            return fn(batch)

        view = _WriteBehind(self.cache, pending)
        before = self.misses
        out = embed_with_cache(texts, call, view, self.model_id, kind)
        if pending:
            if isinstance(self.cache, SqliteVectorCache):
                self.cache.update_many(pending)
            else:
                self.cache.update(pending)
        self.hits += len(texts) - (self.misses - before)
        self.dim = out.shape[1]
        return out

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._cached(texts, "document", self.inner.embed_documents)

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._cached(texts, "query", self.inner.embed_queries)

    def __getattr__(self, name):
        # expose inner attributes such as tokens / cost_usd of an OpenAIEmbedder
        if name in ("inner",):
            raise AttributeError(name)
        return getattr(self.inner, name)


class _WriteBehind(MutableMapping):
    """Reads from the real cache, collects writes in `pending` (one transaction later)."""

    def __init__(self, base: MutableMapping, pending: dict):
        self.base, self.pending = base, pending

    def __getitem__(self, k):
        if k in self.pending:
            return self.pending[k]
        return self.base[k]

    def get(self, k, default=None):
        if k in self.pending:
            return self.pending[k]
        return self.base.get(k, default)

    def __setitem__(self, k, v):
        self.pending[k] = v

    def __delitem__(self, k):
        self.pending.pop(k, None)

    def __iter__(self):
        return iter(set(self.base) | set(self.pending))

    def __len__(self):
        return len(set(self.base) | set(self.pending))

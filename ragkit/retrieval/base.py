"""The Retriever contract, and metadata filters every retriever shares.

Anything with   search(query, k=5, where=None) -> list[Hit]   is a retriever: BM25 today,
a vector store in lesson 11, a hybrid of both in lesson 12, a reranker wrapping either in
lesson 12. rag.answer() only needs this method, so swapping retrievers is one line.

Index-like retrievers also implement add(chunks) and remove(doc_id), which is what the
ingestion pipeline calls for incremental updates.

`where` filters on chunk metadata BEFORE ranking:
    {"language": "he"}                      equality
    {"classification": ["public", "internal"]}   membership (e.g. the user's clearance)
    {"effective_date": {"$gte": "2026-01-01"}}   comparison ($gte $gt $lte $lt $ne)
    callable(chunk) -> bool                 anything else
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Protocol, Union, runtime_checkable

from ..types import Chunk, Hit

Where = Optional[Union[dict[str, Any], Callable[[Chunk], bool]]]


@runtime_checkable
class Retriever(Protocol):
    def search(self, query: str, k: int = 5, where: Where = None) -> list[Hit]: ...


@runtime_checkable
class Index(Retriever, Protocol):
    def add(self, chunks: Iterable[Chunk]) -> None: ...

    def remove(self, doc_id: str) -> int: ...


def _value(chunk: Chunk, key: str):
    if key in ("doc_id", "id", "index", "n_tokens"):
        return getattr(chunk, key)
    if key == "section":
        return chunk.section
    return chunk.meta.get(key)


OPS = {"$gte": lambda a, b: a is not None and a >= b, "$gt": lambda a, b: a is not None and a > b,
       "$lte": lambda a, b: a is not None and a <= b, "$lt": lambda a, b: a is not None and a < b,
       "$ne": lambda a, b: a != b}


def matches(chunk: Chunk, where: Where) -> bool:
    if where is None:
        return True
    if callable(where):
        return bool(where(chunk))
    for key, cond in where.items():
        v = _value(chunk, key)
        if isinstance(cond, dict):
            if not all(OPS[op](v, arg) for op, arg in cond.items()):
                return False
        elif isinstance(cond, (list, tuple, set, frozenset)):
            if v not in cond:
                return False
        elif v != cond:
            return False
    return True

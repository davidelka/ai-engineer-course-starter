"""DenseRetriever: Embedder + VectorStore = a Retriever (and an Index) like BM25Index.

    from ragkit.dense import DenseRetriever
    from ragkit.embed import make_embedder
    dense = DenseRetriever(make_embedder("e5-small", cache_dir=".cache/embeddings"))
    dense.add(chunks)                          # embeds chunk.context_text() as documents
    hits = dense.search("כמה ימי חופשה אפשר להעביר?", k=5, where={"language": "en"})

Because it has search(query, k, where), add(chunks) and remove(doc_id), it drops into
everything lesson 9 built: rag.answer(question, dense, llm), IngestPipeline(index=dense),
evaluate.retrieval_eval(dense, qa). Lesson 11 passes a managed database as `store`;
lesson 12 fuses it with BM25 (each Hit carries scores["vector"]).
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from .embed.base import Embedder
from .retrieval.base import Where
from .types import Chunk, Hit
from .vectors import NumpyVectorStore, VectorStore


class DenseRetriever:
    def __init__(self, embedder: Embedder, store: Optional[VectorStore] = None, *,
                 with_context: bool = True, name: Optional[str] = None):
        self.embedder = embedder
        self.store = store if store is not None else NumpyVectorStore(metric="cosine")
        self.with_context = with_context
        self.name = name or f"dense:{embedder.model_id}"

    def _text(self, c: Chunk) -> str:
        return c.context_text() if self.with_context else c.text

    def add(self, chunks: Iterable[Chunk]) -> None:
        chunks = list(chunks)
        if chunks:
            self.store.add(chunks, self.embedder.embed_documents([self._text(c) for c in chunks]))

    def remove(self, doc_id: str) -> int:
        return self.store.remove(doc_id)

    def __len__(self) -> int:
        return len(self.store)

    def embed_query(self, query: str) -> np.ndarray:
        return self.embedder.embed_queries([query])[0]

    def search(self, query: str, k: int = 5, where: Where = None) -> list[Hit]:
        return self.search_vector(self.embed_query(query), k, where)

    def search_vector(self, vector, k: int = 5, where: Where = None) -> list[Hit]:
        hits = self.store.search(vector, k=k, where=where)
        for h in hits:
            h.retriever = self.name
        return hits

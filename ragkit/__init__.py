"""ragkit: the course's RAG library (lesson 9 onward). See ragkit/README.md.

    from ragkit import load_document, make_chunker, BM25Index, answer
    doc = load_document("data/acme/corpus/docs/sales-sla-2026.pdf")
    chunks = make_chunker("heading:400:40").split(doc)
    index = BM25Index(); index.add(chunks)
    ans = answer("What is the Enterprise uptime commitment?", index, llm)

Modules: types (Document, Chunk, Hit) · loaders (md/html/pdf/docx) · clean · tokens ·
structure (headings) · chunking (fixed/recursive/heading/sentence) · manifest + pipeline
(incremental ingestion) · retrieval (Retriever protocol, BM25) · rag (prompt, citations,
answer loop) · fake (offline answerer) · evaluate (quote coverage, retrieval hits) · acme.
Lesson 10 (need numpy, imported lazily so lesson 9 code runs without it): embed (Embedder
protocol, local/OpenAI/fake embedders, disk cache) · vectors (VectorStore protocol, numpy and
FAISS stores, vector math) · dense (DenseRetriever) · metrics (recall@k, MRR).
"""

from .chunking import (CHUNKERS, Chunker, FixedTokenChunker, HeadingChunker, RecursiveChunker,
                       SentenceChunker, make_chunker)
from .clean import collapse_ws, normalize
from .loaders import iter_sources, load_directory, load_document, register_loader
from .manifest import IngestPlan, Manifest, content_hash, plan_ingest
from .pipeline import IngestPipeline, IngestReport
from .rag import NOT_FOUND, RagAnswer, answer, build_request, parse_citations
from .retrieval import BM25Index, Retriever, analyze, matches
from .tokens import get_tokenizer
from .types import Chunk, Document, Hit

__all__ = [
    "Chunk", "Document", "Hit", "normalize", "collapse_ws", "get_tokenizer",
    "load_document", "load_directory", "iter_sources", "register_loader",
    "Chunker", "CHUNKERS", "make_chunker", "FixedTokenChunker", "RecursiveChunker",
    "HeadingChunker", "SentenceChunker", "Manifest", "IngestPlan", "plan_ingest", "content_hash",
    "IngestPipeline", "IngestReport", "BM25Index", "Retriever", "analyze", "matches",
    "answer", "build_request", "parse_citations", "RagAnswer", "NOT_FOUND",
]

# Lesson 10 additions, resolved on first access (they import numpy; lesson 9 code does not).
_LAZY = {
    "DenseRetriever": ("ragkit.dense", "DenseRetriever"),
    "Embedder": ("ragkit.embed", "Embedder"),
    "make_embedder": ("ragkit.embed", "make_embedder"),
    "VectorStore": ("ragkit.vectors", "VectorStore"),
    "NumpyVectorStore": ("ragkit.vectors", "NumpyVectorStore"),
    "FaissVectorStore": ("ragkit.vectors", "FaissVectorStore"),
}


def __getattr__(name):
    if name in _LAZY:
        import importlib
        mod, attr = _LAZY[name]
        return getattr(importlib.import_module(mod), attr)
    raise AttributeError(f"module 'ragkit' has no attribute {name!r}")

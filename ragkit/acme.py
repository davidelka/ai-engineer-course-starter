"""Shortcuts for the Acme corpus (data/acme/corpus): documents, golden questions, an index."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional, Union

from .chunking import Chunker, make_chunker
from .loaders import load_directory
from .retrieval import BM25Index
from .types import Chunk, Document

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "data" / "acme" / "corpus"
DOCS_DIR = CORPUS / "docs"
QA_PATH = CORPUS / "golden" / "qa.jsonl"


def acme_documents(**loader_options) -> list[Document]:
    """All 55 documents, loaded and cleaned (PDF/HTML/DOCX extracted, sidecars attached)."""
    return list(_cached_docs(tuple(sorted(loader_options.items()))))


@lru_cache(maxsize=8)
def _cached_docs(opts: tuple) -> tuple[Document, ...]:
    return tuple(load_directory(DOCS_DIR, **dict(opts)))


def acme_qa(path: Optional[Path] = None) -> list[dict]:
    with open(path or QA_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def acme_chunks(chunker: Union[str, Chunker] = "heading:400:40", **loader_options) -> list[Chunk]:
    return make_chunker(chunker).split_all(acme_documents(**loader_options))


def acme_index(chunker: Union[str, Chunker] = "heading:400:40", **bm25_options) -> BM25Index:
    idx = BM25Index(**bm25_options)
    idx.add(acme_chunks(chunker))
    return idx

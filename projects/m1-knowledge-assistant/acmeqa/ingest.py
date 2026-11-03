"""The ingestion job: files -> Documents -> chunks -> hybrid index, incrementally.

    job = IngestJob(settings)            # loads manifest.json, chunks.jsonl, docs.jsonl
    report = job.run()                   # first run: added 55; next run: unchanged 55
    job.index                            # HybridRetriever({"bm25": BM25Index, "dense": DenseRetriever})
    job.docs["hr-vacation-2026"]         # StoredDoc(id, meta, text): the CLEANED text citations point into

This is ragkit's IngestPipeline (lesson 9) with two additions the assistant needs:

1. The index is a HybridRetriever (lesson 12) over BM25 and a DenseRetriever (lesson 10). Both
   are rebuilt from chunks.jsonl when the job starts: BM25 in milliseconds, dense from the
   embedding cache (CachedEmbedder, SQLite keyed by model + text), so a restart embeds nothing
   new and costs nothing. Only added or changed chunks are embedded.
2. A docs store (docs.jsonl): the cleaned text and metadata of every ingested document. Chunk
   offsets point into this text (doc.text[c.start:c.end] == c.text), so a citation can be
   opened at the exact passage (GET /docs/{id}). The manifest decides which documents change;
   the docs store follows it (changed -> rewritten, removed -> deleted).

State lives in settings.index_path (one folder per embedder, because vectors from two models
cannot share an index): manifest.json, chunks.jsonl, docs.jsonl.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ragkit.dense import DenseRetriever
from ragkit.hybrid import HybridRetriever
from ragkit.pipeline import IngestPipeline, IngestReport
from ragkit.retrieval import BM25Index
from ragkit.types import Chunk, Document

from .config import Settings


@dataclass
class StoredDoc:
    id: str
    meta: dict
    text: str

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.id)


@dataclass
class JobStats:
    documents: int = 0
    chunks: int = 0
    by_classification: dict = field(default_factory=dict)
    by_language: dict = field(default_factory=dict)
    by_format: dict = field(default_factory=dict)
    embedder: str = ""
    embed_cache: dict = field(default_factory=dict)
    startup_s: float = 0.0


class IngestJob:
    def __init__(self, settings: Optional[Settings] = None):
        self.s = settings or Settings.from_env()
        t0 = time.perf_counter()
        self.dir = self.s.index_path
        self.embedder = self.s.make_embedder()
        self.bm25 = BM25Index()
        self.dense = DenseRetriever(self.embedder)
        self.index = HybridRetriever({"bm25": self.bm25, "dense": self.dense}, fetch_k=50)
        self.docs: dict[str, StoredDoc] = self._load_docs()
        self._fresh: dict[str, StoredDoc] = {}
        self.pipe = IngestPipeline(self.dir, chunker=self.s.chunker, index=self.index, transform=self._capture)
        self.startup_s = time.perf_counter() - t0

    # ------------------------------------------------------------ docs store
    def _docs_path(self) -> Path:
        return self.dir / "docs.jsonl"

    def _load_docs(self) -> dict[str, StoredDoc]:
        p = self._docs_path()
        out: dict[str, StoredDoc] = {}
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    out[d["id"]] = StoredDoc(d["id"], d["meta"], d["text"])
        return out

    def _capture(self, doc: Document) -> Document:
        """IngestPipeline's transform hook: called once per (re)ingested document, before chunking."""
        meta = {k: v for k, v in doc.meta.items() if isinstance(v, (str, int, float, bool, list, type(None)))}
        self._fresh[doc.id] = StoredDoc(doc.id, meta, doc.text)
        return doc

    def _save_docs(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._docs_path().with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for doc_id in sorted(self.docs):
                d = self.docs[doc_id]
                f.write(json.dumps({"id": d.id, "meta": d.meta, "text": d.text}, ensure_ascii=False) + "\n")
        tmp.replace(self._docs_path())

    # ------------------------------------------------------------ the job
    def run(self, root: Optional[Path] = None, *, dry_run: bool = False) -> IngestReport:
        self._fresh = {}
        report = self.pipe.run(root or self.s.docs_dir, dry_run=dry_run)
        if dry_run:
            return report
        for doc_id in report.plan.removed:
            self.docs.pop(doc_id, None)
        for doc_id in report.errors:
            self.docs.pop(doc_id, None)
        self.docs.update(self._fresh)
        self._save_docs()
        return report

    def ensure(self) -> Optional[IngestReport]:
        """Ingest if the index is empty (first start), else keep what is on disk."""
        if not self.pipe.chunks or not self.docs:
            return self.run()
        return None

    # ------------------------------------------------------------ views
    def all_chunks(self) -> list[Chunk]:
        return self.pipe.all_chunks()

    def documents(self) -> list[Document]:
        """The stored docs as ragkit Documents (for quote coverage and diagnosis)."""
        return [Document(id=d.id, text=d.text, meta=dict(d.meta)) for d in self.docs.values()]

    def stats(self) -> JobStats:
        from collections import Counter
        chunks = self.all_chunks()
        st = JobStats(documents=len(self.docs), chunks=len(chunks), embedder=getattr(self.embedder, "model_id", "?"),
                      startup_s=round(self.startup_s, 3))
        st.by_classification = dict(Counter(d.meta.get("classification", "?") for d in self.docs.values()))
        st.by_language = dict(Counter(d.meta.get("language", "?") for d in self.docs.values()))
        st.by_format = dict(Counter(d.meta.get("format", "?") for d in self.docs.values()))
        stats = getattr(self.embedder, "stats", None)      # CachedEmbedder: {"hits", "misses", "calls"}
        if isinstance(stats, dict):
            st.embed_cache = dict(stats)
        return st

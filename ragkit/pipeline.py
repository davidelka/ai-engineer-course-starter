"""The ingestion pipeline: sources -> (skip unchanged) -> load -> clean -> chunk -> index.

    pipe = IngestPipeline("indexes/acme", chunker="heading:400:40")
    report = pipe.run("data/acme/corpus/docs")      # first run: everything is "added"
    report = pipe.run("data/acme/corpus/docs")      # second run: everything "unchanged"
    hits = pipe.index.search("carry over vacation days")

State on disk, in `store_dir`:
    manifest.json   doc_id -> content hash, path, chunk ids, time      (ragkit.manifest)
    chunks.jsonl    every chunk with its metadata and offsets          (the source of truth)
The index is rebuilt from chunks.jsonl when the pipeline starts (BM25 builds in
milliseconds). A vector index (lesson 11) persists itself instead, because embeddings cost
money: that is exactly why the manifest must know which chunks belong to which document.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Union

from .chunking import Chunker, make_chunker
from .loaders import Source, iter_sources, load_document
from .manifest import IngestPlan, Manifest, plan_ingest
from .retrieval import BM25Index
from .retrieval.base import Index
from .types import Chunk, Document


@dataclass
class IngestReport:
    plan: IngestPlan
    chunks_added: int = 0
    chunks_removed: int = 0
    seconds: float = 0.0
    errors: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        s = (f"{self.plan.summary()} | chunks +{self.chunks_added} -{self.chunks_removed} | "
             f"{self.seconds:.2f}s")
        if self.errors:
            s += f" | {len(self.errors)} errors: {', '.join(self.errors)}"
        return s


class IngestPipeline:
    def __init__(self, store_dir: Union[str, Path], chunker: Union[str, Chunker] = "heading:400:40",
                 index: Optional[Index] = None, loader_options: Optional[dict] = None,
                 transform: Optional[Callable[[Document], Document]] = None,
                 planner: Callable[..., IngestPlan] = plan_ingest,
                 hasher: Optional[Callable[[bytes, dict], str]] = None):
        self.dir = Path(store_dir)
        self.chunker = make_chunker(chunker)
        self.loader_options = loader_options or {}
        self.transform = transform          # hook: e.g. redact PII before chunking (lesson 27)
        self.planner = planner              # the lab swaps in mine.plan_ingest here
        self.hasher = hasher                # ... and mine.content_hash here
        self.manifest = Manifest.load(self.dir / "manifest.json")
        self.chunks: dict[str, list[Chunk]] = self._load_chunks()
        self.index = index if index is not None else BM25Index()
        for cs in self.chunks.values():
            self.index.add(cs)

    @property
    def pipeline_signature(self) -> str:
        opts = ",".join(f"{k}={v}" for k, v in sorted(self.loader_options.items()))
        return f"{self.chunker.signature}|loaders({opts})"

    def _load_chunks(self) -> dict[str, list[Chunk]]:
        p = self.dir / "chunks.jsonl"
        out: dict[str, list[Chunk]] = {}
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    c = Chunk.from_dict(json.loads(line))
                    out.setdefault(c.doc_id, []).append(c)
        return out

    def _save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.dir / "chunks.jsonl"
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for doc_id in sorted(self.chunks):
                for c in self.chunks[doc_id]:
                    f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        tmp.replace(p)
        self.manifest.pipeline = self.pipeline_signature
        self.manifest.save(self.dir / "manifest.json")

    def all_chunks(self) -> list[Chunk]:
        return [c for doc_id in sorted(self.chunks) for c in self.chunks[doc_id]]

    def plan(self, root: Union[str, Path]) -> tuple[IngestPlan, dict[str, Source]]:
        sources = {s.id: s for s in iter_sources(root, hasher=self.hasher)}
        changed = bool(self.manifest.docs) and self.manifest.pipeline != self.pipeline_signature
        plan = self.planner(self.manifest.hashes(), {k: s.content_hash for k, s in sources.items()},
                            pipeline_changed=changed)
        return plan, sources

    def run(self, root: Union[str, Path], *, dry_run: bool = False) -> IngestReport:
        t0 = time.perf_counter()
        plan, sources = self.plan(root)
        report = IngestReport(plan=plan)
        if dry_run:
            return report
        for doc_id in plan.removed + plan.changed:
            report.chunks_removed += self.index.remove(doc_id)
            self.chunks.pop(doc_id, None)
            if doc_id in plan.removed:
                self.manifest.forget(doc_id)
        for doc_id in plan.to_process:
            src = sources[doc_id]
            try:
                doc = load_document(src, **self.loader_options)
                if self.transform:
                    doc = self.transform(doc)
                cs = self.chunker.split(doc)
            except Exception as exc:  # one broken file must not stop the batch
                report.errors[doc_id] = f"{type(exc).__name__}: {exc}"
                self.manifest.forget(doc_id)  # so the next run retries it as "added"
                continue
            self.chunks[doc_id] = cs
            self.index.add(cs)
            report.chunks_added += len(cs)
            self.manifest.record(doc_id, src.content_hash, str(src.path), [c.id for c in cs])
        self._save()
        report.seconds = time.perf_counter() - t0
        return report

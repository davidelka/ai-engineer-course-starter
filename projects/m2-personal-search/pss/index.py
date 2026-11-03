"""PersonalIndex: scan -> extract -> chunk -> embed -> BM25 + vectors on disk, updated incrementally.

On disk (settings.index_dir, default state/sample for the sample folder):
    manifest.json   per file: hash, size, mtime, title, format, date, pages, chunk count, warnings
    chunks.jsonl    every chunk (ragkit Chunk.to_dict), with page / file / folder / date in meta
    vectors.npy     float32 matrix, row-aligned with chunks.jsonl
    dups.json       near-duplicate groups
    egress.jsonl    the cloud egress log (pss.privacy); never touched by indexing
The embedding cache lives outside (settings.embed_cache_dir, SQLite, ragkit CachedEmbedder),
so rebuilding the index or indexing a renamed file costs no embedding work.

Retrieval reuses ragkit unchanged: BM25Index (with Hebrew prefix variants), DenseRetriever over
a NumpyVectorStore (exact search; FAISS HNSW optional), and HybridRetriever with RRF (k=60).
Filters from the query become a `where` callable that every retriever applies before ranking.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from ragkit.chunking import make_chunker
from ragkit.dense import DenseRetriever
from ragkit.embed import make_embedder
from ragkit.hybrid import HybridRetriever
from ragkit.retrieval import BM25Index
from ragkit.types import Chunk, Document, Hit
from ragkit.vectors import NumpyVectorStore

from . import hooks
from .config import Settings
from .extract import Extracted, extract
from .manifest import Manifest, SyncPlan, file_hash
from .query import ParsedQuery, where_from
from .scan import FileEntry, ScanReport, scan
from .snippets import make_snippet

MODES = ("bm25", "dense", "hybrid")
INDEX_FIELDS = ("roots", "exclude", "max_file_mb", "embedder", "store", "chunker", "ocr", "ocr_langs")


def restore_settings(settings: Settings, index_dir: Path) -> Settings:
    """Take the index-defining fields (roots, excludes, embedder...) from an existing index, so
    `pss search` uses the same embedder and `pss watch` the same folders as `pss index` did."""
    p = Path(index_dir).expanduser() / "settings.json"
    if p.exists():
        snap = json.loads(p.read_text(encoding="utf-8"))
        for k in INDEX_FIELDS:
            if k in snap:
                setattr(settings, k, snap[k])
    settings.index_dir = str(Path(index_dir).expanduser())
    return settings


@dataclass
class FileResult:
    id: str
    title: str
    format: str
    folder: str
    date: str
    rank: int
    score: float
    pages: list[int]
    best: Hit
    snippet: str                     # HTML: escaped text with <mark> around matched terms
    language: str = ""
    also: list[str] = field(default_factory=list)     # near-duplicates folded into this result
    scores: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "format": self.format, "folder": self.folder,
                "date": self.date, "rank": self.rank, "score": round(self.score, 5),
                "pages": self.pages, "page": self.best.chunk.meta.get("page"), "snippet": self.snippet,
                "language": self.language, "also": self.also,
                "scores": {k: round(v, 4) for k, v in self.best.scores.items()}}


@dataclass
class SearchResult:
    query: str
    parsed: ParsedQuery
    mode: str
    files: list[FileResult]
    hits: list[Hit]
    ms: float

    def to_dict(self) -> dict:
        return {"query": self.query, "text": self.parsed.text, "filters": self.parsed.filters,
                "warnings": self.parsed.warnings, "mode": self.mode, "ms": round(self.ms, 1),
                "results": [f.to_dict() for f in self.files]}


@dataclass
class SyncReport:
    plan: SyncPlan
    scan: ScanReport
    seconds: float
    chunks_added: int
    warnings: dict[str, list[str]]
    rebuilt: bool = False

    def summary(self) -> str:
        s = f"{self.plan.summary()}; {self.chunks_added} chunks embedded in {self.seconds:.2f}s"
        if self.rebuilt:
            s = "index settings changed: full rebuild. " + s
        return s


class PersonalIndex:
    def __init__(self, settings: Settings, *, embedder=None):
        self.s = settings
        self.dir = settings.index_path
        if embedder is None:
            cache = None if settings.embedder.startswith("fake") else Path(settings.embed_cache_dir).expanduser()
            embedder = make_embedder(settings.embedder, cache_dir=cache)
        self.embedder = embedder
        self.chunker = make_chunker(settings.chunker, tokenizer="approx")
        self.manifest = Manifest(signature=settings.index_signature())
        self.chunks: dict[str, Chunk] = {}
        self.vecs: dict[str, np.ndarray] = {}
        self.dups: list[list[str]] = []
        self._stale = False
        self._reset_retrievers()

    # ------------------------------------------------------------------ retrievers
    def _make_store(self):
        if self.s.store == "faiss":
            from ragkit.vectors.faiss_store import FaissVectorStore
            return FaissVectorStore(metric="cosine", index="HNSW32")
        return NumpyVectorStore(metric="cosine")

    def _reset_retrievers(self) -> None:
        self.bm25 = BM25Index()
        self.store = self._make_store()
        self.dense = DenseRetriever(self.embedder, self.store, name="dense")
        self.hybrid = HybridRetriever({"bm25": self.bm25, "dense": self.dense}, method="rrf",
                                      k_rrf=60, fetch_k=50, name="hybrid")

    def retriever(self, mode: str):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        return {"bm25": self.bm25, "dense": self.dense, "hybrid": self.hybrid}[mode]

    # ------------------------------------------------------------------ persistence
    @classmethod
    def open(cls, settings: Settings, **kw) -> "PersonalIndex":
        idx = cls(settings, **kw)
        idx.load()
        return idx

    def load(self) -> bool:
        mpath = self.dir / "manifest.json"
        if not mpath.exists():
            return False
        m = Manifest.load(mpath)
        if m.signature != self.s.index_signature():
            self._stale = True                 # built with other settings: the next sync rebuilds
            return False
        chunks = []
        cpath = self.dir / "chunks.jsonl"
        if cpath.exists():
            with open(cpath, encoding="utf-8") as f:
                chunks = [Chunk.from_dict(json.loads(line)) for line in f if line.strip()]
        mat = np.load(self.dir / "vectors.npy") if (self.dir / "vectors.npy").exists() else np.zeros((0, 0))
        if len(chunks) != len(mat):
            return False
        self.manifest = m
        self._reset_retrievers()
        self.chunks = {c.id: c for c in chunks}
        self.vecs = {c.id: mat[i] for i, c in enumerate(chunks)}
        if chunks:
            self.bm25.add(chunks)
            self.store.add(chunks, mat)
        dpath = self.dir / "dups.json"
        self.dups = json.loads(dpath.read_text(encoding="utf-8")) if dpath.exists() else []
        return True

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        ids = list(self.chunks)
        with open(self.dir / "chunks.jsonl.tmp", "w", encoding="utf-8") as f:
            for cid in ids:
                f.write(json.dumps(self.chunks[cid].to_dict(), ensure_ascii=False) + "\n")
        dim = next(iter(self.vecs.values())).shape[0] if self.vecs else 0
        mat = np.stack([self.vecs[c] for c in ids]).astype(np.float32) if ids else np.zeros((0, dim), np.float32)
        with open(self.dir / "vectors.npy.tmp", "wb") as f:
            np.save(f, mat)
        (self.dir / "chunks.jsonl.tmp").replace(self.dir / "chunks.jsonl")
        (self.dir / "vectors.npy.tmp").replace(self.dir / "vectors.npy")
        (self.dir / "dups.json").write_text(json.dumps(self.dups, ensure_ascii=False, indent=1), encoding="utf-8")
        snap = {k: getattr(self.s, k) for k in INDEX_FIELDS}
        (self.dir / "settings.json").write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        self.manifest.save(self.dir / "manifest.json")

    # ------------------------------------------------------------------ indexing
    def _scan_all(self) -> tuple[dict[str, FileEntry], ScanReport]:
        entries: dict[str, FileEntry] = {}
        total = ScanReport()
        roots = [Path(r).expanduser() for r in self.s.roots]
        for root in roots:
            rep = scan(root, self.s.exclude, max_file_mb=self.s.max_file_mb)
            prefix = (root.resolve().name + "/") if len(roots) > 1 else ""
            for e in rep.files:
                e.id = prefix + e.id
                entries[e.id] = e
            total.files += rep.files
            total.skipped += [(prefix + p, r) for p, r in rep.skipped]
        return entries, total

    def to_chunks(self, ex: Extracted, entry: FileEntry) -> list[Chunk]:
        out: list[Chunk] = []
        title = f"{ex.title} | {ex.id}"
        for u in ex.units:
            if not u.text.strip():
                continue
            doc = Document(id=ex.id, text=u.text, meta={"title": title, "language": ex.language,
                                                         "format": ex.format, "source_path": str(entry.path)})
            for c in self.chunker.split(doc):
                n = len(out)
                c.id = f"{ex.id}#p{u.page}.{c.index}" if u.page else f"{ex.id}#{c.index}"
                c.index = n
                c.meta.update({"file": ex.id, "folder": entry.folder, "date": ex.date, "page": u.page,
                               "format": ex.format, "language": ex.language})
                out.append(c)
        return out

    def _remove_file(self, fid: str) -> None:
        ids = [cid for cid, c in self.chunks.items() if c.doc_id == fid]
        for cid in ids:
            self.chunks.pop(cid, None)
            self.vecs.pop(cid, None)
        self.bm25.remove(fid)
        self.store.remove(fid)

    def sync(self, *, only: Optional[set[str]] = None, progress=None) -> SyncReport:
        """Bring the index in line with the folders. `only` (absolute paths) is a hint from the
        watcher; the plan is still computed from a full scan, which is a stat per file."""
        t0 = time.perf_counter()
        entries, rep = self._scan_all()
        rebuilt, self._stale = self._stale, False
        if self.manifest.signature != self.s.index_signature() or (self.manifest.files and not self.chunks):
            self.manifest = Manifest(signature=self.s.index_signature())
            self.chunks, self.vecs = {}, {}
            self._reset_retrievers()
            rebuilt = True
        current = {fid: e.stat_dict() for fid, e in entries.items()}
        plan = hooks.get("plan_sync")(self.manifest.files, current, lambda fid: file_hash(entries[fid].path))
        for fid in plan.removed + plan.changed:
            self._remove_file(fid)
            self.manifest.files.pop(fid, None)
        for fid in plan.touched:
            self.manifest.files[fid].update(entries[fid].stat_dict())
        new_chunks: list[Chunk] = []
        warnings: dict[str, list[str]] = {}
        for n, fid in enumerate(plan.to_index):
            e = entries[fid]
            if progress:
                progress(n + 1, len(plan.to_index), fid)
            try:
                ex = extract(e, ocr=self.s.ocr, ocr_langs=self.s.ocr_langs)
            except Exception as exc:          # one broken file must not stop the run
                warnings[fid] = [f"failed: {type(exc).__name__}: {exc}"]
                continue
            cs = self.to_chunks(ex, e)
            new_chunks += cs
            if ex.warnings:
                warnings[fid] = ex.warnings
            self.manifest.files[fid] = {
                "hash": plan.hashes.get(fid) or file_hash(e.path), **e.stat_dict(), "title": ex.title,
                "format": ex.format, "language": ex.language, "date": ex.date, "date_source": ex.date_source,
                "pages": ex.pages, "chunks": len(cs), "ocr": ex.ocr, "warnings": ex.warnings,
                "path": str(e.path)}
        if new_chunks:
            vecs = self.embedder.embed_documents([c.context_text() for c in new_chunks])
            for c, v in zip(new_chunks, vecs):
                self.chunks[c.id] = c
                self.vecs[c.id] = np.asarray(v, dtype=np.float32)
            self.bm25.add(new_chunks)
            self.store.add(new_chunks, vecs)
        if plan.to_index or plan.removed or rebuilt:
            self.dups = hooks.get("near_duplicate_groups")(self.doc_texts())
        self.save()
        return SyncReport(plan=plan, scan=rep, seconds=time.perf_counter() - t0,
                          chunks_added=len(new_chunks), warnings=warnings, rebuilt=rebuilt)

    # ------------------------------------------------------------------ views
    def doc_texts(self) -> dict[str, str]:
        out: dict[str, list[str]] = {}
        for c in self.chunks.values():
            out.setdefault(c.doc_id, []).append(c.text)
        return {k: "\n".join(v) for k, v in out.items()}

    def dup_of(self) -> dict[str, list[str]]:
        m: dict[str, list[str]] = {}
        for g in self.dups:
            for fid in g:
                m[fid] = [x for x in g if x != fid]
        return m

    def stats(self) -> dict:
        size = sum(p.stat().st_size for p in self.dir.glob("*") if p.is_file() and p.name != "egress.jsonl") \
            if self.dir.exists() else 0
        fmts: dict[str, int] = {}
        for f in self.manifest.files.values():
            fmts[f["format"]] = fmts.get(f["format"], 0) + 1
        cache = getattr(self.embedder, "stats", None)
        return {"files": len(self.manifest.files), "chunks": len(self.chunks), "formats": fmts,
                "index_bytes": size, "dup_groups": len(self.dups), "embedder": self.s.embedder,
                "dim": int(next(iter(self.vecs.values())).shape[0]) if self.vecs else 0,
                "embed_cache": cache() if callable(cache) else None, "index_dir": str(self.dir)}

    def file_path(self, fid: str) -> Optional[Path]:
        """Absolute path of an INDEXED file (the web UI may open only these)."""
        f = self.manifest.files.get(fid)
        return Path(f["path"]) if f and f.get("path") else None

    # ------------------------------------------------------------------ search
    def search_hits(self, query: str, *, mode: str = "hybrid", k: int = 10, filters: Optional[dict] = None
                    ) -> tuple[ParsedQuery, list[Hit], float]:
        pq = hooks.get("parse_query")(query)
        f = {**pq.filters, **(filters or {})}
        pq.filters = f
        where = where_from(f)
        t0 = time.perf_counter()
        if not pq.text.strip():
            hits = self._browse(where, k)
        else:
            hits = self.retriever(mode).search(pq.text, k=k, where=where)
        return pq, hits, (time.perf_counter() - t0) * 1000

    def _browse(self, where, k: int) -> list[Hit]:
        """Only filters, no words: the newest matching files."""
        seen, out = set(), []
        for c in sorted(self.chunks.values(), key=lambda c: (c.meta.get("date") or "", c.id), reverse=True):
            if c.doc_id in seen or (where and not where(c)):
                continue
            seen.add(c.doc_id)
            out.append(Hit(chunk=c, score=0.0, rank=len(out) + 1, scores={}, retriever="browse"))
            if len(out) >= k:
                break
        return out

    def rank_files(self, query: str, *, mode: str = "hybrid", depth: int = 10) -> list[tuple[str, Optional[int]]]:
        """File ids in rank order (no duplicate folding), with the page of each file's best chunk."""
        _, hits, _ = self.search_hits(query, mode=mode, k=depth * 6)
        out, seen = [], set()
        for h in hits:
            if h.chunk.doc_id not in seen:
                seen.add(h.chunk.doc_id)
                out.append((h.chunk.doc_id, h.chunk.meta.get("page")))
        return out[:depth]

    def search(self, query: str, *, mode: str = "hybrid", k: int = 10, filters: Optional[dict] = None,
               fold_duplicates: bool = True) -> SearchResult:
        pq, hits, ms = self.search_hits(query, mode=mode, k=max(30, k * 6), filters=filters)
        dup = self.dup_of() if fold_duplicates else {}
        files: dict[str, FileResult] = {}
        folded: dict[str, str] = {}
        terms_src = pq.text
        for h in hits:
            fid = h.chunk.doc_id
            if fid in folded:
                continue
            if fid in files:
                p = h.chunk.meta.get("page")
                if p and p not in files[fid].pages:
                    files[fid].pages.append(p)
                continue
            shown = next((x for x in dup.get(fid, []) if x in files), None)
            if shown:
                folded[fid] = shown
                files[shown].also.append(fid)
                continue
            m = self.manifest.files.get(fid, {})
            files[fid] = FileResult(
                id=fid, title=m.get("title") or fid, format=m.get("format", ""), folder=h.chunk.meta.get("folder", ""),
                date=m.get("date", ""), rank=len(files) + 1, score=h.score,
                pages=[h.chunk.meta["page"]] if h.chunk.meta.get("page") else [], best=h,
                snippet=make_snippet(h.chunk.text, terms_src), language=m.get("language", ""))
            if len(files) >= k:
                break
        return SearchResult(query=query, parsed=pq, mode=mode, files=list(files.values()), hits=hits, ms=ms)

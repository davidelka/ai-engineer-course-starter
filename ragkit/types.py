"""Core types: Document, Chunk, Hit.

Every later stage speaks only these three types, so a new loader, chunker, embedder, vector
store or reranker (lessons 10-13) plugs in without touching the others.

Offsets are the contract that makes citations trustworthy:
    doc.text[chunk.start:chunk.end] == chunk.text      (always; tests check it)
`doc.text` is the CLEANED text (after the loader and ragkit.clean.normalize), so a citation
can always be mapped back to the exact span the answer was based on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# Metadata copied from a Document onto each of its chunks, so filters and citations work on
# a chunk alone (a vector store row has no access to the parent document).
CHUNK_META_KEYS = ("title", "department", "doc_type", "version", "effective_date", "owner",
                   "classification", "language", "supersedes", "format", "source_path")


@dataclass
class Document:
    id: str
    text: str                                   # cleaned, markdown-ish text (headings as '#')
    meta: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""                      # hash of the raw source bytes + metadata
    extras: dict[str, Any] = field(default_factory=dict)  # loader diagnostics (raw text, removed lines)

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.id)

    @property
    def language(self) -> str:
        return str(self.meta.get("language") or "")

    @property
    def effective_date(self) -> str:
        return str(self.meta.get("effective_date") or "")

    @property
    def version(self) -> str:
        return str(self.meta.get("version") or "")

    @property
    def classification(self) -> str:
        return str(self.meta.get("classification") or "")

    @property
    def format(self) -> str:
        return str(self.meta.get("format") or "")


@dataclass
class Chunk:
    id: str                                     # "<doc_id>#<index>", stable for a given chunker
    doc_id: str
    text: str
    start: int                                  # char offset into Document.text (inclusive)
    end: int                                    # char offset into Document.text (exclusive)
    index: int = 0                              # position within the document
    section_path: tuple[str, ...] = ()          # e.g. ("Vacation Policy", "Carry-over")
    n_tokens: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    # -- convenient views of the copied metadata
    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.doc_id)

    @property
    def language(self) -> str:
        return str(self.meta.get("language") or "")

    @property
    def effective_date(self) -> str:
        return str(self.meta.get("effective_date") or "")

    @property
    def version(self) -> str:
        return str(self.meta.get("version") or "")

    @property
    def classification(self) -> str:
        return str(self.meta.get("classification") or "")

    @property
    def section(self) -> str:
        return " > ".join(self.section_path)

    def context_text(self) -> str:
        """What an index should see: the chunk prefixed with its title and section path.
        A chunk that says "Up to 5 days may be carried over" does not contain the word
        "vacation"; its title does. (Lesson 10 adds LLM-written context on top of this.)"""
        head = self.title + (f" > {self.section}" if self.section else "")
        return f"{head}\n{self.text}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["section_path"] = list(self.section_path)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        d = dict(d)
        d["section_path"] = tuple(d.get("section_path") or ())
        return cls(**d)


@dataclass
class Hit:
    """One retrieval result. `scores` keeps every stage's score (bm25, vector, rerank...)
    so a pipeline debugger can show why a chunk ranked where it did."""

    chunk: Chunk
    score: float
    rank: int = 0
    scores: dict[str, float] = field(default_factory=dict)
    retriever: Optional[str] = None

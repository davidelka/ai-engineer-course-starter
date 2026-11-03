"""The Chunker contract and the shared machinery.

A chunker only decides SPANS: (start, end) character ranges of doc.text, optionally with a
section path. Chunker.split() turns spans into Chunk objects the same way for every
strategy: trims whitespace at the edges, copies document metadata, attaches the section
path (from the headings, when the strategy did not give one), counts tokens, numbers them.
So the offset contract  doc.text[c.start:c.end] == c.text  holds for every strategy.

To add a strategy (lesson 10 adds semantic chunking): subclass Chunker, set `name`,
implement spans(doc), and register it in ragkit.chunking.CHUNKERS.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..structure import SectionIndex
from ..tokens import Tokenizer, get_tokenizer
from ..types import CHUNK_META_KEYS, Chunk, Document

Span = tuple  # (start, end) or (start, end, section_path)


class Chunker:
    name = "base"

    def __init__(self, tokenizer: Optional[Tokenizer] = None):
        self.tokenizer = tokenizer or get_tokenizer()

    # -- what subclasses implement
    def spans(self, doc: Document) -> Iterable[Span]:
        raise NotImplementedError

    def params(self) -> dict:
        return {}

    # -- shared
    @property
    def signature(self) -> str:
        """Identifies the chunking config; the ingestion manifest re-chunks everything when
        it changes (same file + different chunker = different chunks)."""
        p = ",".join(f"{k}={v}" for k, v in sorted(self.params().items()))
        return f"{self.name}({p})/{self.tokenizer.name}"

    def __repr__(self) -> str:
        return self.signature

    def split(self, doc: Document) -> list[Chunk]:
        text = doc.text
        sections = SectionIndex(text)
        meta = {k: doc.meta[k] for k in CHUNK_META_KEYS if k in doc.meta}
        chunks: list[Chunk] = []
        for sp in self.spans(doc):
            start, end = sp[0], sp[1]
            path = sp[2] if len(sp) > 2 else None
            while start < end and text[start].isspace():
                start += 1
            while end > start and text[end - 1].isspace():
                end -= 1
            if end <= start:
                continue
            body = text[start:end]
            if path is None:
                path = sections.section_path(start)
            i = len(chunks)
            chunks.append(Chunk(id=f"{doc.id}#{i}", doc_id=doc.id, text=body, start=start, end=end,
                                index=i, section_path=tuple(path), n_tokens=self.tokenizer.count(body),
                                meta=dict(meta)))
        return chunks

    def split_all(self, docs: Iterable[Document]) -> list[Chunk]:
        out: list[Chunk] = []
        for d in docs:
            out.extend(self.split(d))
        return out


# ------------------------------------------------------------------ helpers used by strategies

def count(tok: Tokenizer, text: str, a: int, b: int) -> int:
    return tok.count(text[a:b])


def split_keep(text: str, a: int, b: int, sep: str) -> list[tuple[int, int]]:
    """Split text[a:b] on sep, keeping the separator at the END of each piece, as offsets.
    sep == "" splits into single characters (the last resort)."""
    if sep == "":
        return [(i, i + 1) for i in range(a, b)]
    out, s = [], a
    while True:
        i = text.find(sep, s, b)
        if i == -1:
            if s < b:
                out.append((s, b))
            return out
        out.append((s, i + len(sep)))
        s = i + len(sep)


def pack(text: str, pieces: list[tuple[int, int]], max_tokens: int, overlap: int,
         tok: Tokenizer) -> list[tuple[int, int]]:
    """Greedily merge adjacent pieces into windows of <= max_tokens. With overlap > 0, a new
    window starts with the last pieces of the previous one, up to `overlap` tokens.
    Pieces must each fit in max_tokens already."""
    sizes = [count(tok, text, a, b) for a, b in pieces]
    out: list[tuple[int, int]] = []
    i, n = 0, len(pieces)
    while i < n:
        j, total = i, 0
        while j < n and (total + sizes[j] <= max_tokens or j == i):
            total += sizes[j]
            j += 1
        out.append((pieces[i][0], pieces[j - 1][1]))
        if j >= n:
            break
        # step back for overlap, but always make progress
        k, back = j, 0
        while overlap > 0 and k - 1 > i and back + sizes[k - 1] <= overlap:
            k -= 1
            back += sizes[k]
        i = k
    return out

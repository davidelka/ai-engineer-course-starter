"""Four chunking strategies, from structure-blind to structure-aware.

FixedTokenChunker      every `size` tokens, stepping size-overlap. Ignores sentences,
                       paragraphs, tables and headings; the baseline every other one beats.
RecursiveChunker       split on the biggest separator that exists (blank line, newline,
                       sentence end, space), merge the pieces back up to max_tokens. The
                       default of most frameworks (LangChain's RecursiveCharacterTextSplitter).
HeadingChunker         one chunk per markdown section (heading to next heading); a section
                       that is too long is split recursively INSIDE the section, and every
                       piece keeps the section path. A heading with no body of its own is
                       merged into the next section, so "# Title" never becomes a chunk alone.
SentenceChunker        sentences packed up to max_tokens, overlapping by whole sentences.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from ..structure import SectionIndex
from ..tokens import Tokenizer
from ..types import Document
from .base import Chunker, count, pack, split_keep

DEFAULT_SEPARATORS = ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", "")


class FixedTokenChunker(Chunker):
    name = "fixed"

    def __init__(self, size: int = 256, overlap: int = 32, tokenizer: Optional[Tokenizer] = None):
        super().__init__(tokenizer)
        if not 0 <= overlap < size:
            raise ValueError("need 0 <= overlap < size")
        self.size, self.overlap = size, overlap

    def params(self):
        return {"size": self.size, "overlap": self.overlap}

    def spans(self, doc: Document):
        toks = self.tokenizer.spans(doc.text)
        step = self.size - self.overlap
        for i in range(0, max(1, len(toks)), step):
            window = toks[i:i + self.size]
            if not window:
                break
            yield (window[0][0], window[-1][1])
            if i + self.size >= len(toks):
                break


def _atoms(text: str, a: int, b: int, max_tokens: int, tok: Tokenizer,
           separators: list[str]) -> list[tuple[int, int]]:
    """Split text[a:b] into pieces of <= max_tokens, using the biggest separator present and
    recursing with smaller separators only on the pieces that are still too big."""
    if count(tok, text, a, b) <= max_tokens:
        return [(a, b)]
    for idx, sep in enumerate(separators):
        if sep == "" or text.find(sep, a, b) != -1:
            break
    rest = separators[idx + 1:]
    out: list[tuple[int, int]] = []
    for pa, pb in split_keep(text, a, b, sep):
        if count(tok, text, pa, pb) <= max_tokens or not rest:
            out.append((pa, pb))
        else:
            out.extend(_atoms(text, pa, pb, max_tokens, tok, rest))
    return out


def recursive_spans(text: str, a: int, b: int, max_tokens: int, overlap: int, tok: Tokenizer,
                    separators: Iterable[str] = DEFAULT_SEPARATORS) -> list[tuple[int, int]]:
    """The recursive algorithm on offsets: split into pieces that fit (paragraphs, then lines,
    then sentences, then words), then pack neighbouring pieces back up to max_tokens, with
    `overlap` tokens of whole pieces repeated at the start of the next window."""
    if count(tok, text, a, b) <= max_tokens:
        return [(a, b)]
    return pack(text, _atoms(text, a, b, max_tokens, tok, list(separators)), max_tokens, overlap, tok)


class RecursiveChunker(Chunker):
    name = "recursive"

    def __init__(self, max_tokens: int = 256, overlap: int = 0,
                 separators: Iterable[str] = DEFAULT_SEPARATORS, tokenizer: Optional[Tokenizer] = None):
        super().__init__(tokenizer)
        self.max_tokens, self.overlap, self.separators = max_tokens, overlap, tuple(separators)

    def params(self):
        return {"max_tokens": self.max_tokens, "overlap": self.overlap}

    def spans(self, doc: Document):
        return recursive_spans(doc.text, 0, len(doc.text), self.max_tokens, self.overlap,
                               self.tokenizer, self.separators)


class HeadingChunker(Chunker):
    name = "heading"

    def __init__(self, max_tokens: int = 400, overlap: int = 40, min_tokens: int = 0,
                 tokenizer: Optional[Tokenizer] = None):
        super().__init__(tokenizer)
        self.max_tokens, self.overlap, self.min_tokens = max_tokens, overlap, min_tokens

    def params(self):
        p = {"max_tokens": self.max_tokens, "overlap": self.overlap}
        if self.min_tokens:
            p["min_tokens"] = self.min_tokens
        return p

    def merged(self, doc: Document) -> list[tuple[int, int, tuple[str, ...]]]:
        """With min_tokens > 0: a section smaller than min_tokens absorbs the following
        sections while the total stays <= max_tokens. The merged chunk keeps the path the
        sections share (their common prefix), so the path never claims too much."""
        secs = self.sections(doc)
        if not self.min_tokens:
            return secs
        text, out = doc.text, []
        for sec in secs:
            if out:
                a, b, p = out[-1]
                if count(self.tokenizer, text, a, b) < self.min_tokens and \
                        count(self.tokenizer, text, a, sec[1]) <= self.max_tokens:
                    common = []
                    for x, y in zip(p, sec[2]):
                        if x != y:
                            break
                        common.append(x)
                    out[-1] = (a, sec[1], tuple(common))
                    continue
            out.append(sec)
        return out

    def sections(self, doc: Document) -> list[tuple[int, int, tuple[str, ...]]]:
        """Sections with heading-only sections merged forward into the next one."""
        text = doc.text
        raw = SectionIndex(text).sections(len(text))
        out: list[tuple[int, int, tuple[str, ...]]] = []
        pending_start: Optional[int] = None
        for start, end, path in raw:
            nl = text.find("\n", start, end)
            body = text[nl + 1:end] if (path and nl != -1) else ("" if path else text[start:end])
            if path and not body.strip():
                pending_start = start if pending_start is None else pending_start
                continue
            out.append((pending_start if pending_start is not None else start, end, path))
            pending_start = None
        if pending_start is not None:
            if out:
                s, _, p = out[-1]
                out[-1] = (s, len(text), p)
            else:
                out.append((pending_start, len(text), raw[-1][2] if raw else ()))
        return out

    def spans(self, doc: Document):
        text = doc.text
        for start, end, path in self.merged(doc):
            for a, b in recursive_spans(text, start, end, self.max_tokens, self.overlap, self.tokenizer):
                yield (a, b, path)


SENT_END_RE = re.compile(r"(?<=[.!?])[\"')\]]*\s+|\n+")
ABBREV = ("e.g.", "i.e.", "etc.", "vs.", "Mr.", "Ms.", "Dr.", "No.", "approx.", "Inc.", "Ltd.")


def sentence_spans(text: str, a: int = 0, b: Optional[int] = None) -> list[tuple[int, int]]:
    """Sentence boundaries: after . ! ? followed by whitespace (not after a known abbreviation),
    and at every newline (headings, list items and table rows are their own "sentences").
    Works for Hebrew too: it ends sentences with the same punctuation."""
    b = len(text) if b is None else b
    out, s = [], a
    for m in SENT_END_RE.finditer(text, a, b):
        if m.group(0).strip() == "" and "\n" not in m.group(0):
            tail = text[max(s, m.start() - 8):m.start()]
            if any(tail.endswith(x) for x in ABBREV):
                continue
        e = m.start()
        if e > s and text[s:e].strip():
            out.append((s, e))
        s = m.end()
    if s < b and text[s:b].strip():
        out.append((s, b))
    return out


class SentenceChunker(Chunker):
    name = "sentence"

    def __init__(self, max_tokens: int = 200, overlap_sentences: int = 1,
                 tokenizer: Optional[Tokenizer] = None):
        super().__init__(tokenizer)
        self.max_tokens, self.overlap_sentences = max_tokens, overlap_sentences

    def params(self):
        return {"max_tokens": self.max_tokens, "overlap_sentences": self.overlap_sentences}

    def spans(self, doc: Document):
        text, tok = doc.text, self.tokenizer
        sents: list[tuple[int, int]] = []
        for a, b in sentence_spans(text):
            if count(tok, text, a, b) > self.max_tokens:      # a monster "sentence" (a table?)
                sents.extend(recursive_spans(text, a, b, self.max_tokens, 0, tok))
            else:
                sents.append((a, b))
        sizes = [count(tok, text, a, b) for a, b in sents]
        i, n = 0, len(sents)
        while i < n:
            j, total = i, 0
            while j < n and (total + sizes[j] <= self.max_tokens or j == i):
                total += sizes[j]
                j += 1
            yield (sents[i][0], sents[j - 1][1])
            if j >= n:
                break
            i = max(i + 1, j - self.overlap_sentences)

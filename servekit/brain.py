"""Company Brain v0: the "answer a question about Acme" logic behind the API.

Deliberately small. Retrieval here is plain keyword overlap over Markdown
sections of the Acme documents (data/acme/*.md and data/acme/corpus/docs/*.md),
so the service runs anywhere with no index to build. Phase 2 (lessons 9-13)
replaces `retrieve` with ragkit; the API contract below does not change, and
that is the point of having a contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from llmkit import ChatRequest

DATA = Path(__file__).resolve().parent.parent / "data" / "acme"
WORD = re.compile(r"[\w֐-׿]+", re.UNICODE)
STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "do", "does", "i", "my",
        "can", "how", "what", "when", "many", "much", "with", "at", "by", "be", "it", "we", "our", "you"}

SYSTEM = (
    "You are Company Brain, Acme Ltd.'s internal assistant. Answer ONLY from the <source> "
    "blocks. Cite sources inline as [1], [2]. If the sources do not contain the answer, say "
    "you could not find it in Acme's documents. Be concise: at most 5 sentences."
)


@dataclass(frozen=True)
class Section:
    doc: str
    heading: str
    text: str


def _terms(s: str) -> set[str]:
    return {w.lower() for w in WORD.findall(s) if w.lower() not in STOP and len(w) > 1}


def _split(doc: str, text: str) -> list[Section]:
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)  # YAML front matter
    out, heading, buf = [], doc, []
    for line in text.splitlines():
        if line.startswith("#"):
            if "".join(buf).strip():
                out.append(Section(doc, heading, "\n".join(buf).strip()))
            heading, buf = line.lstrip("# ").strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append(Section(doc, heading, "\n".join(buf).strip()))
    return out


@lru_cache(maxsize=1)
def sections() -> tuple[Section, ...]:
    files = sorted(DATA.glob("*.md")) + sorted((DATA / "corpus" / "docs").glob("*.md"))
    out: list[Section] = []
    for f in files:
        try:
            out.extend(_split(f.stem, f.read_text(encoding="utf-8")))
        except OSError:
            continue
    return tuple(out)


def retrieve(question: str, k: int = 3) -> list[Section]:
    q = _terms(question)
    if not q:
        return []
    scored = []
    for s in sections():
        overlap = len(q & _terms(s.heading + " " + s.text))
        if overlap:
            scored.append((overlap, len(s.text) < 1500, s))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [s for _, _, s in scored[:k]]


def build_request(question: str, max_tokens: int, hits: list[Section]) -> ChatRequest:
    blocks = "\n".join(
        f'<source id="{i}" doc="{s.doc}" section="{s.heading}">\n{s.text[:1500]}\n</source>'
        for i, s in enumerate(hits, 1))
    prompt = f"{blocks}\n\n<question>{question}</question>"
    return ChatRequest.from_prompt(prompt, system=SYSTEM, max_tokens=max_tokens)


def citations(hits: list[Section]) -> list[dict]:
    return [{"n": i, "doc": s.doc, "section": s.heading} for i, s in enumerate(hits, 1)]

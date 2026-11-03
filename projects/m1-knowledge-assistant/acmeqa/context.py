"""Context packing: from 30 ranked candidates to the few chunks the model actually reads.

Retrieval returns candidates; the prompt needs a SELECTION. Three things go wrong if you just
take the first k:

- near-duplicates: it-laptop-policy and it-laptop-faq repeat the same paragraphs, and
  hr-vacation-2026 / hr-vacation-2026-he say the same thing twice. Two copies of one paragraph
  waste the budget and push out the second source a multi-hop question needs.
- one document hogs the prompt: the five best chunks of eng-service-catalog leave no room for
  the postmortem the question also needs.
- size: chunks vary from 30 to 450 tokens. A token budget, not a count, controls cost and
  keeps the evidence out of the "middle of a long context" (lesson 13, lost_in_middle).

pack_context is milestone 4 of the project (mine.py). This is the reference.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Optional, Sequence

from ragkit.clean import collapse_ws, normalize
from ragkit.tokens import get_tokenizer
from ragkit.types import Hit


def _key(text: str) -> str:
    return collapse_ws(normalize(text)).lower()


def pack_context(hits: Sequence[Hit], *, max_chunks: int = 6, max_tokens: int = 1800, max_per_doc: int = 2,
                 count: Optional[Callable[[str], int]] = None) -> list[Hit]:
    count = count or get_tokenizer("approx").count
    chosen: list[Hit] = []
    seen: set[str] = set()
    per_doc: dict[str, int] = {}
    used = 0
    for h in hits:
        if len(chosen) >= max_chunks:
            break
        key = _key(h.chunk.text)
        if key in seen:
            continue
        if per_doc.get(h.chunk.doc_id, 0) >= max_per_doc:
            continue
        n = count(h.chunk.text)
        if chosen and used + n > max_tokens:
            continue
        chosen.append(h)
        seen.add(key)
        per_doc[h.chunk.doc_id] = per_doc.get(h.chunk.doc_id, 0) + 1
        used += n
    return [replace(h, rank=i, scores=dict(h.scores)) for i, h in enumerate(chosen, start=1)]

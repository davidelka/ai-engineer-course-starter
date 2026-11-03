"""Tokenizers for chunking: count tokens AND know where each token starts and ends.

Chunk sizes are measured in tokens, but chunks are cut on character offsets, so a chunker
needs spans, not just a count.

- TiktokenTokenizer: o200k_base (OpenAI's current encoding). A proxy for "model tokens";
  Claude's tokenizer differs (Claude Haiku 5.5 counts roughly 30% more on English, and
  Hebrew differs more), and so does every embedding model (lesson 10).
- ApproxTokenizer: no download, deterministic: word pieces of at most 5 characters plus one
  token per punctuation mark. Within ~15% of o200k on English prose. Tests use it, so they
  give the same result on every machine.

get_tokenizer("auto") returns tiktoken when its encoding file can be loaded (it is
downloaded once and cached), otherwise the approximation. RAGKIT_TOKENIZER=approx forces it.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Protocol


class Tokenizer(Protocol):
    name: str

    def count(self, text: str) -> int: ...

    def spans(self, text: str) -> list[tuple[int, int]]: ...


class ApproxTokenizer:
    name = "approx"
    _re = re.compile(r"\w{1,5}|[^\w\s]")

    def spans(self, text: str) -> list[tuple[int, int]]:
        return [m.span() for m in self._re.finditer(text)]

    def count(self, text: str) -> int:
        return sum(1 for _ in self._re.finditer(text))


class TiktokenTokenizer:
    def __init__(self, encoding: str = "o200k_base"):
        import tiktoken

        self.enc = tiktoken.get_encoding(encoding)
        self.name = f"tiktoken:{encoding}"

    def count(self, text: str) -> int:
        return len(self.enc.encode(text, disallowed_special=())) if text else 0

    def spans(self, text: str) -> list[tuple[int, int]]:
        if not text:
            return []
        toks = self.enc.encode(text, disallowed_special=())
        _, offsets = self.enc.decode_with_offsets(toks)
        out = []
        for i, s in enumerate(offsets):
            e = offsets[i + 1] if i + 1 < len(offsets) else len(text)
            if e > s:  # a multi-byte character split over tokens: keep the first token only
                out.append((s, e))
        return out


@lru_cache(maxsize=4)
def get_tokenizer(name: str = "auto") -> Tokenizer:
    name = os.environ.get("RAGKIT_TOKENIZER", name) if name == "auto" else name
    if name == "approx":
        return ApproxTokenizer()
    if name in ("auto", "tiktoken"):
        try:
            return TiktokenTokenizer()
        except Exception:
            if name == "tiktoken":
                raise
            return ApproxTokenizer()
    if name.startswith("tiktoken:"):
        return TiktokenTokenizer(name.split(":", 1)[1])
    raise ValueError(f"unknown tokenizer {name!r} (auto, approx, tiktoken, tiktoken:<encoding>)")

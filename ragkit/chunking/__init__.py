"""Chunking strategies and a registry.

    from ragkit.chunking import make_chunker
    ch = make_chunker("heading:400:40")          # strategy:size:overlap
    chunks = ch.split(doc)

Spec strings (used by the lab scripts):
    fixed:<size>:<overlap>          FixedTokenChunker
    recursive:<max>:<overlap>       RecursiveChunker
    heading:<max>:<overlap>         HeadingChunker
    sentence:<max>:<overlap_sents>  SentenceChunker
"""

from __future__ import annotations

from typing import Optional, Union

from ..tokens import Tokenizer, get_tokenizer
from .base import Chunker, pack, split_keep
from .strategies import (FixedTokenChunker, HeadingChunker, RecursiveChunker, SentenceChunker,
                         recursive_spans, sentence_spans)

CHUNKERS: dict[str, type] = {
    "fixed": FixedTokenChunker,
    "recursive": RecursiveChunker,
    "heading": HeadingChunker,
    "sentence": SentenceChunker,
}


def make_chunker(spec: Union[str, Chunker], tokenizer: Optional[Union[str, Tokenizer]] = None) -> Chunker:
    if isinstance(spec, Chunker):
        return spec
    tok = get_tokenizer(tokenizer or "auto") if isinstance(tokenizer, (str, type(None))) else tokenizer
    name, *nums = spec.split(":")
    if name not in CHUNKERS:
        raise ValueError(f"unknown chunker {name!r}; choose from {', '.join(CHUNKERS)}")
    args = [int(x) for x in nums]
    return CHUNKERS[name](*args, tokenizer=tok)


__all__ = ["Chunker", "CHUNKERS", "make_chunker", "FixedTokenChunker", "RecursiveChunker",
           "HeadingChunker", "SentenceChunker", "recursive_spans", "sentence_spans", "pack",
           "split_keep"]

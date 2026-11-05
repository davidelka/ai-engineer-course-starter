"""Your code for lesson 9. Each part is checked by tests in ./tests.

ragkit has reference versions (ragkit/chunking/strategies.py HeadingChunker,
ragkit/evaluate.py quote_status, ragkit/manifest.py content_hash and plan_ingest).
Try not to peek before your tests pass.

    python -m pytest -q labs/09-rag-ingestion/tests
"""

from __future__ import annotations

import hashlib  # noqa: F401  (you will likely need it)
import json  # noqa: F401
from typing import Iterable, Optional

from ragkit.chunking import recursive_spans  # noqa: F401  (allowed helper, see exercise 3)
from ragkit.clean import collapse_ws  # noqa: F401  (exercise 4)
from ragkit.manifest import IngestPlan  # noqa: F401  (exercise 5)
from ragkit.structure import headings  # noqa: F401  (allowed helper, see exercise 3)
from ragkit.tokens import Tokenizer, get_tokenizer  # noqa: F401
from ragkit.types import CHUNK_META_KEYS, Chunk, Document  # noqa: F401


# ------------------------------------------------------------------ exercise 3
def heading_chunks(doc: Document, max_tokens: int = 400, overlap: int = 40,
                   tokenizer: Optional[Tokenizer] = None) -> list[Chunk]:
    """Split a document into chunks along its markdown headings.

    doc.text is cleaned, markdown-ish text: headings are lines starting with '#'..'######'
    (every ragkit loader emits them, also for HTML, PDF and DOCX). Example:

        # Vacation Policy            <- level 1
        intro paragraph
        ## Carry-over                <- level 2
        - Up to 5 unused days ...

    Returns list[Chunk]. Rules the result must satisfy:
      - A SECTION runs from a heading line to the next heading of ANY level. Text before the
        first heading is a section with section_path ().
      - section_path: titles of the heading and its enclosing headings, outermost first,
        e.g. ("Vacation Policy", "Carry-over").
      - A section with an empty body is not a chunk of its own: its heading line joins the next
        section's chunk, which keeps the next section's path.
      - No chunk exceeds max_tokens (tokenizer.count). A longer section is split inside itself,
        consecutive pieces overlapping by about `overlap` tokens, all keeping the section path.
      - Chunk fields: id f"{doc.id}#{i}" (i = 0, 1, ... in document order), doc_id, text (trimmed),
        start/end with doc.text[c.start:c.end] == c.text ALWAYS, index i, section_path (tuple of
        str), n_tokens = tokenizer.count(text), meta = the doc.meta keys listed in CHUNK_META_KEYS.
        No empty chunks.
    tokenizer defaults to get_tokenizer() (tests pass the approx tokenizer).
    Do NOT use ragkit.chunking.HeadingChunker: that is the reference you are rewriting.
    Stuck? HINTS.md -> heading_chunks
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement heading_chunks")


# ------------------------------------------------------------------ exercise 4
def quote_status(quote: str, doc_text: str, chunk_texts: Iterable[str]) -> str:
    """Where did a golden quote end up after ingestion?

    Receives the quote, the document text and the chunk texts. Returns one of:
      "missing"  the quote is not in the document text at all (extraction/cleaning lost it)
      "covered"  the quote is fully inside at least one chunk
      "split"    the quote is in the document, but no single chunk contains all of it
    Whitespace differences (PDF line breaks, double spaces) must not decide the answer.
    Example: quote "carried over to the next calendar year", chunks
      ["... may be carried", "over to the next calendar year ..."] -> "split".
    Stuck? HINTS.md -> quote_status
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement quote_status")


# ------------------------------------------------------------------ exercise 5
def content_hash(data: bytes, meta: Optional[dict] = None) -> str:
    """A stable fingerprint of one source: its raw bytes AND its metadata.

    Returns 16 lowercase hex characters. A test checks the exact recipe (the manifest must
    match ragkit's), so it is an interface:
        sha256( data + b"\\0" + json.dumps(meta or {}, sort_keys=True, ensure_ascii=False,
                default=str).encode("utf-8") ), first 16 hex characters of the digest.
    The same bytes and the same metadata (in any key order) -> the same hash.
    A changed byte OR a changed metadata value (e.g. classification) -> a different hash.
    Stuck? HINTS.md -> content_hash
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement content_hash")


def plan_ingest(previous: dict[str, str], current: dict[str, str], *,
                pipeline_changed: bool = False) -> IngestPlan:
    """Decide what an incremental ingestion run must do.

    previous: doc_id -> hash from the manifest of the last run ({} on the first run)
    current:  doc_id -> hash of every source file now
    Returns IngestPlan(added, changed, unchanged, removed), each a SORTED list of doc ids:
      added      in current, not in previous
      changed    in both, and the hash differs
      unchanged  in both, same hash
      removed    in previous, not in current
    pipeline_changed=True (another chunker or loader options): every document in both maps
    is "changed", even with the same hash: its old chunks were made by a different recipe.
    Stuck? HINTS.md -> plan_ingest
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement plan_ingest")

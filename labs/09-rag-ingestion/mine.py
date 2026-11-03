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

    Rules:
      1. A SECTION runs from a heading line to the next heading of ANY level. Text before the
         first heading (if any) is a section with section_path ().
      2. section_path = the titles of the heading and all its enclosing headings, outermost
         first, e.g. ("Vacation Policy", "Carry-over"). ragkit.structure.headings(text)
         returns Heading(start, line_end, level, title, path) objects that already carry it.
      3. A section whose body is empty (a heading immediately followed by another heading)
         is NOT a chunk of its own: its heading line joins the next section's chunk (so the
         chunk starts at that earlier heading), and the chunk keeps the next section's path.
      4. A section with more than max_tokens tokens (tokenizer.count) is split INSIDE the
         section into pieces of at most max_tokens, consecutive pieces overlapping by about
         `overlap` tokens. Every piece keeps the section's path. You may use
         ragkit.chunking.recursive_spans(doc.text, start, end, max_tokens, overlap, tokenizer),
         which returns [(start, end), ...] offsets for one range.
      5. Each Chunk:
           id         f"{doc.id}#{i}"  (i = 0, 1, 2... in document order)
           doc_id     doc.id
           text       doc.text[start:end]  with whitespace trimmed at both ends, and start/end
                      adjusted to match, so that doc.text[c.start:c.end] == c.text ALWAYS
           index      i
           section_path   a tuple of strings
           n_tokens   tokenizer.count(text)
           meta       {k: doc.meta[k] for k in CHUNK_META_KEYS if k in doc.meta}
         Skip empty pieces.
    tokenizer defaults to get_tokenizer() (tests pass the approx tokenizer).
    Do NOT use ragkit.chunking.HeadingChunker: that is the reference you are rewriting.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement heading_chunks")


# ------------------------------------------------------------------ exercise 4
def quote_status(quote: str, doc_text: str, chunk_texts: Iterable[str]) -> str:
    """Where did a golden quote end up after ingestion?

    Compare on WHITESPACE-NORMALIZED text: apply ragkit.clean.collapse_ws to the quote, the
    document text and every chunk text (PDF line breaks and double spaces must not decide
    whether a quote "exists").
    Return:
      "missing"  the quote is not in the document text at all (extraction/cleaning lost it)
      "covered"  the quote is fully inside at least one chunk
      "split"    the quote is in the document, but no single chunk contains all of it
    Example: quote "carried over to the next calendar year", chunks
      ["... may be carried", "over to the next calendar year ..."] -> "split".
    """
    # TODO(ex4)
    raise NotImplementedError("exercise 4: implement quote_status")


# ------------------------------------------------------------------ exercise 5
def content_hash(data: bytes, meta: Optional[dict] = None) -> str:
    """A stable fingerprint of one source: its raw bytes AND its metadata.

    - Feed hashlib.sha256 the bytes, then the separator b"\\0", then the metadata serialized
      canonically and encoded as UTF-8:
          json.dumps(meta or {}, sort_keys=True, ensure_ascii=False, default=str)
    - Return the first 16 hex characters.
    The same bytes and the same metadata (in any key order) -> the same hash.
    A changed byte OR a changed metadata value (e.g. classification) -> a different hash.
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement content_hash")


def plan_ingest(previous: dict[str, str], current: dict[str, str], *,
                pipeline_changed: bool = False) -> IngestPlan:
    """Decide what an incremental ingestion run must do.

    previous: doc_id -> hash from the manifest of the last run ({} on the first run)
    current:  doc_id -> hash of every source file now
    Return IngestPlan(added, changed, unchanged, removed), each a SORTED list of doc ids:
      added      in current, not in previous
      changed    in both, and the hash differs
      unchanged  in both, same hash
      removed    in previous, not in current
    If pipeline_changed is True (another chunker or loader options), every document that is
    in both maps is "changed", even when its hash is the same: its old chunks were made by
    a different recipe.
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement plan_ingest")

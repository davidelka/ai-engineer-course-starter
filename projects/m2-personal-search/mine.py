"""Your code for midterm project M2 (Personal Smart Search).

You build the parts of the tool that the course taught: what may be read, incremental indexing,
chunking, filters, duplicates, the prompt and its citations, what may leave the machine, and the
retrieval metrics. The course gives you the rest ready (reading PDF/DOCX/HTML/images, the web UI,
the file watcher, the command line, the on-disk index). Ten functions, in seven milestones:

    M2   is_excluded             which files may never be indexed (the first privacy boundary)
    M3   plan_sync               incremental re-indexing: stat first, hash only what moved
    M3   file_to_chunks          one extracted file -> chunks that remember their file and page
    M4   retrieval_row           the per-question numbers of the retrieval evaluation
    M5   parse_query             filters inside the query: type:pdf folder:kids after:2026-06
    M6   near_duplicate_groups   the same document twice (a download, a -copy, a v2)
    M7   build_request           the prompt: numbered sources with file and page, then the question
    M7   resolve_citations       "[2]" in the answer -> the file and page it points to
    M8   redact_for_cloud        what is masked before a single byte goes to a cloud model
    M8   select_for_cloud        which sources may be sent at all, and which are withheld

Each is checked by tests in ./tests (python -m pytest -q tests from the project folder).
Every command (`python -m pss ...`) uses YOUR functions; a command that needs one you have not
written yet stops and names the milestone. The reference implementations are on the repo's
`solutions` branch, for comparing AFTER your tests pass. Stuck? HINTS.md has three graded hints
per function.

Data you will meet:
    file ids    paths relative to the indexed folder, posix style: "home/lease-2026.pdf",
                "kids/school-trip-permission-2026-11.docx". Folders: home, receipts, kids,
                health, finance, courses, recipes, travel, scans (see data/sample/).
    manifest    {file_id: {"hash": "ab12...", "size": 1234, "mtime": 1793350800.0, ...}}
"""

from __future__ import annotations

import re  # noqa: F401  (you will likely need it)
from fnmatch import fnmatchcase  # noqa: F401
from typing import Any, Callable, Optional

from xml.sax.saxutils import escape  # noqa: F401  (escapes & < >, leaves quotes alone)
from xml.sax.saxutils import quoteattr  # noqa: F401

from guardkit.redact import redact_pii  # noqa: F401  (Israeli ID with check digit, email, phone)
from llmkit import ChatRequest, Message  # noqa: F401
from pss.answer import SYSTEM, Citation  # noqa: F401
from pss.dedup import jaccard, shingles  # noqa: F401
from pss.manifest import SyncPlan  # noqa: F401
from pss.privacy import luhn_ok  # noqa: F401
from pss.query import KEYS, LANGS, TYPES, ParsedQuery, norm_date  # noqa: F401
from ragkit.rag import parse_citations  # noqa: F401  ("[1][3]", "[1, 3]" -> [1, 3], first appearance order)
from ragkit.types import Chunk, Document, Hit  # noqa: F401


# ------------------------------------------------------------------ M2: excludes
def is_excluded(rel_path: str, patterns: list[str]) -> Optional[str]:
    """Return the FIRST pattern (in list order) that excludes rel_path, or None.

    rel_path: relative, "/"-separated ("kids/2026/report.pdf"); a leading "./" is ignored.
    Matching is case-insensitive. Empty patterns and "#comments" are skipped.
    Three kinds of pattern ("*" and "?" are globs):
      "*.key", ".*", "*password*"   no "/": excludes when ANY component of the path, folders or
                                    file name, matches. ".*" excludes ".env" and anything under ".git/".
      "private/"                    trailing "/": a folder name. Excludes when a folder component
                                    (not the file name) matches: "a/private/x.txt" yes,
                                    "notes/private.txt" no.
      "finance/*.pdf", "kids/**/report*"
                                    "/" inside: matched against the WHOLE path. "*" and "?" never
                                    cross a "/"; "**/" matches zero or more folders ("kids/**/report*"
                                    matches "kids/report.pdf" and "kids/2026/t1/report.pdf").
                                    A leading "/" is ignored.
    The scanner also calls you with a folder followed by "/x" (e.g. "node_modules/x") to decide
    whether to skip a whole folder without walking into it.

    Stuck? HINTS.md -> is_excluded
    """
    # TODO(M2)
    raise NotImplementedError("M2: implement is_excluded")


# ------------------------------------------------------------------ M3: incremental sync
def plan_sync(manifest: dict[str, dict], current: dict[str, dict], hash_fn: Callable[[str], str]) -> SyncPlan:
    """Decide what to re-index. Return a SyncPlan (pss/manifest.py) with SORTED lists.

    manifest: what the index holds  {id: {"hash", "size", "mtime", ...}}
    current:  what the scan found   {id: {"size", "mtime"}}  (a stat call, the file was NOT read)
    hash_fn(id) reads the file and returns its content hash. It is SLOW: call it only when the
    answer depends on the content, and at most once per id.
      added      in current, not in manifest
      unchanged  in both, same size and same mtime (never hashed)
      touched    in both, size or mtime differs, but the content hash equals the manifest's
      changed    in both, size or mtime differs, and the hash differs
      removed    in manifest, not in current
    plan.hashes = {id: hash} for every id that was hashed (the indexer stores them).

    Stuck? HINTS.md -> plan_sync
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement plan_sync")


# ------------------------------------------------------------------ M3: a file becomes chunks
def file_to_chunks(ex, entry, chunker) -> list[Chunk]:
    """Split one extracted file into chunks that remember where they came from.

    `ex` is an Extracted (pss/extract.py): ex.id (the file id), ex.title, ex.format, ex.language,
    ex.date and ex.units, one Unit per PDF page (u.page is 1-based) or a single Unit with
    u.page = None for formats without pages. `entry` is the FileEntry from the scan: entry.path
    and entry.folder. `chunker.split(doc)` is ragkit's chunker: Document in, Chunks out.

    - Units whose text is only whitespace are skipped. Each other unit becomes a ragkit
      Document(id=ex.id, text=u.text, meta={"title": f"{ex.title} | {ex.id}", "language": ...,
      "format": ..., "source_path": str(entry.path)}) and is split with chunker.split.
    - Chunk ids: f"{ex.id}#p{page}.{c.index}" for a unit with a page, f"{ex.id}#{c.index}" without
      (c.index is the index the chunker gave inside that unit).
    - Then c.index is renumbered 0..n-1 across the whole file, in order.
    - Every chunk's meta gains: "file" (ex.id), "folder", "date", "page" (the unit's page or None),
      "format", "language".
    The page in the meta is what lets an answer cite "lease-2026.pdf, page 2", and the search UI
    open the PDF on that page.

    Stuck? HINTS.md -> file_to_chunks
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement file_to_chunks")


# ------------------------------------------------------------------ M4: retrieval metrics per question
def retrieval_row(q: dict, ranked: list[tuple[str, Optional[int]]]) -> dict:
    """The retrieval numbers for one golden question (data/golden.jsonl).

    `q["relevant"]` lists the files that answer it (empty for a "negative" question),
    `q.get("pages")` maps some relevant files to the pages that hold the answer
    ({"home/lease-2026.pdf": [2]}), and `q.get("must_not")` lists files that must never be returned
    (private/passwords-DO-NOT-INDEX.txt). `ranked` is the search result: (file_id, page of that
    file's best chunk) in rank order, one entry per file.

    Returns a dict with exactly these keys:
    - "r1", "r5", "r10": the share of the relevant files found in the first 1, 5 and 10 (0.0 when
      there are no relevant files);
    - "rr": the reciprocal rank, 1 / (position of the first relevant file, counting from 1), or
      0.0 when none was found;
    - "page_ok": None when the question has no "pages"; otherwise True when the FIRST file in
      `ranked` that appears in q["pages"] came with one of its listed pages, else False (also
      False when no such file was returned);
    - "must_not_hit": the must_not files that appear in `ranked`, sorted.

    Stuck? HINTS.md -> retrieval_row
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement retrieval_row")


# ------------------------------------------------------------------ M5: query filters
def parse_query(q: str) -> ParsedQuery:
    """Split filters out of a query. Return ParsedQuery(text, filters, warnings).

    A filter token is key:value or key:"value with spaces", at the start or after whitespace.
    KEYS maps English and Hebrew key names to the canonical key:
      type   / סוג      comma list, each value through TYPES ("doc"->"docx", "scan"->"image");
                       filters["type"] = list in order, no duplicates. Unknown value -> warning.
      folder / תיקייה  comma list, "/" stripped, lower-cased. filters["folder"] = list.
      after  / אחרי    norm_date(value) -> "YYYY-MM-DD" (start of the period: "2026-06" -> "2026-06-01").
      before / לפני    same. A bad date -> warning, and the token STAYS in the text.
      lang   / שפה     through LANGS ("עברית" -> "he"). Unknown -> warning.
    A token with an unknown key ("10:40", "http://x") is not a filter: it stays in the text.
    text = everything that is not a filter, whitespace collapsed to single spaces.

    Example: parse_query('type:pdf,doc folder:"kids/" after:2026-06 טיול שנתי')
      -> text "טיול שנתי", filters {"type": ["pdf", "docx"], "folder": ["kids"], "after": "2026-06-01"}

    Stuck? HINTS.md -> parse_query
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement parse_query")


# ------------------------------------------------------------------ M6: near-duplicates
def near_duplicate_groups(docs: dict[str, str], threshold: float = 0.8, k: int = 3) -> list[list[str]]:
    """Group documents that are (nearly) the same text.

    docs: {file_id: text}. Two documents are similar when jaccard(shingles(a, k), shingles(b, k))
    >= threshold (k-word shingles, lower-cased). A document with no shingles (empty text) is
    never similar to anything.
    Groups are TRANSITIVE: if A~B and B~C then A, B and C are one group, even when A and C are not
    similar enough on their own.
    Return only groups with 2+ members; each group sorted; the list sorted by each group's first id.

    Stuck? HINTS.md -> near_duplicate_groups
    """
    # TODO(M6)
    raise NotImplementedError("M6: implement near_duplicate_groups")


# ------------------------------------------------------------------ M7: the prompt and its citations
def build_request(question: str, hits: list[Hit], *, max_chars: Optional[int] = None,
                  max_tokens: int = 400) -> ChatRequest:
    """Build the ChatRequest that asks a model to answer `question` from `hits` (best first).

    - system: SYSTEM (pss/answer.py), as a plain string.
    - one user message, exactly:
          "<sources>\n" + <the sources joined by "\n"> + "\n</sources>\n\n<question>" + q + "</question>"
      where q = escape(question) (xml.sax.saxutils, imported above), and an empty `hits` is
      "(no sources found)" in place of the sources.
    - source n (1-based, in order) is:
          '<source id="n" file=... page=... date=... title=...>\n' + escape(body) + "\n</source>"
      file is chunk.doc_id, page is str(chunk.meta["page"]) (left out when the page is None),
      date is chunk.meta["date"], and title is the part of chunk.title before " | ". Each value is
      quoted with xml.sax.saxutils.quoteattr, and an attribute whose value is empty is left out.
    - body is the chunk text; when max_chars is set and the text is longer, it is the first
      max_chars characters followed by " …" (a space and an ellipsis).
    - max_tokens as given.
    The cloud path calls this with max_chars, so a long chunk does not send more of a private file
    than it needs to.

    Stuck? HINTS.md -> build_request
    """
    # TODO(M7)
    raise NotImplementedError("M7: implement build_request")


def resolve_citations(text: str, hits: list[Hit]) -> tuple[list[Citation], list[int]]:
    """Turn the [n] markers of an answer into Citations, checked against the sources that were sent.

    Returns (good, bad). Numbers come from parse_citations(text) (ragkit.rag: every [n], [1, 3],
    [1;3], in order of first appearance, without repeats).
    - good: for each number with 1 <= n <= len(hits), Citation(n, file=chunk.doc_id,
      page=chunk.meta.get("page"), title=<chunk.title before " | ">, text=chunk.text), where
      chunk = hits[n-1].chunk; in the order of the numbers.
    - bad: the numbers outside that range, in the same order. The model invented a source.

    Stuck? HINTS.md -> resolve_citations
    """
    # TODO(M7)
    raise NotImplementedError("M7: implement resolve_citations")


# ------------------------------------------------------------------ M8: redaction before the cloud
def redact_for_cloud(text: str) -> tuple[str, dict[str, int]]:
    """Mask personal identifiers. Return (redacted text, {label: count}), only labels with count > 0.
    Applied IN THIS ORDER (the more specific pattern must win):
      IBAN          Israeli IBAN: "IL" + 2 digits + 19 digits, optionally in groups of 4 separated by
                    spaces or "-" ("IL62 0108 0000 0009 9999 999")                 -> "[IBAN]"
      CARD          13-19 digits, single spaces or "-" allowed between digits, not touching another
                    digit or "-", that pass luhn_ok                                -> "[CARD]"
                    (a 16-digit number that fails Luhn is an order number: leave it)
      IL_ID, EMAIL, PHONE   as guardkit's redact_pii(text) finds and writes them:
                    "[IL_ID]", "[EMAIL]", "[PHONE]". Count only the placeholders this call
                    created, not ones already present in the input.
      BANK_ACCOUNT  bank-branch-account dd-ddd-dddd..ddddddddd (2, 3, then 4-9 digits), not
                    touching another digit or "-"                                  -> "[BANK_ACCOUNT]"

    Stuck? HINTS.md -> redact_for_cloud
    """
    # TODO(M8)
    raise NotImplementedError("M8: implement redact_for_cloud")


# ------------------------------------------------------------------ M8: what may go to the cloud
def select_for_cloud(hits: list[Hit], never_send: list[str], max_sources: int) -> tuple[list[Hit], list[str]]:
    """Decide which retrieved sources may be sent to a cloud model.

    `never_send` is the list of patterns from the config (cloud.never_send, for example "health/",
    "finance/"), with the same semantics as the excludes: a file is protected when
    is_excluded(file_id, never_send) is not None (use your is_excluded from milestone 2).

    Returns (send, withheld):
    - send: the hits whose file is not protected, in their original order, at most max_sources;
    - withheld: the ids of the protected files among the hits, sorted, each once.
    A withheld file is not sent in any form, not even a part of it; the answer says that sources
    were withheld, and the dry run lists them.

    Stuck? HINTS.md -> select_for_cloud
    """
    # TODO(M8)
    raise NotImplementedError("M8: implement select_for_cloud")

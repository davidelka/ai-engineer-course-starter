"""Your code for midterm project M2 (Personal Smart Search). Five functions, five milestones:

    M2  is_excluded             which files may never be indexed (the first privacy boundary)
    M3  plan_sync               incremental re-indexing: stat first, hash only what moved
    M5  parse_query             filters inside the query: type:pdf folder:kids after:2026-06
    M6  near_duplicate_groups   the same document twice (a download, a -copy, a v2)
    M8  redact_for_cloud        what is masked before a single byte goes to a cloud model

Each is checked by tests in ./tests (python -m pytest -q tests from the project folder).
Every command (`python -m pss ...`) uses YOUR function as soon as it stops raising
NotImplementedError, and the reference until then (it prints a [note] saying so).
`python -m pss --reference ...` forces the references. They live in pss/ (scan.py,
manifest.py, query.py, dedup.py, privacy.py): try not to read them before your tests pass.

Data you will meet:
    file ids    paths relative to the indexed folder, posix style: "home/lease-2026.pdf",
                "kids/school-trip-permission-2026-11.docx". Folders: home, receipts, kids,
                health, finance, courses, recipes, travel, scans (see data/sample/).
    manifest    {file_id: {"hash": "ab12...", "size": 1234, "mtime": 1793350800.0, ...}}
"""

from __future__ import annotations

import re  # noqa: F401  (you will likely need it)
from fnmatch import fnmatchcase  # noqa: F401
from typing import Callable, Optional

from guardkit.redact import redact_pii  # noqa: F401  (Israeli ID with check digit, email, phone)
from pss.dedup import jaccard, shingles  # noqa: F401
from pss.manifest import SyncPlan  # noqa: F401
from pss.privacy import luhn_ok  # noqa: F401
from pss.query import KEYS, LANGS, TYPES, ParsedQuery, norm_date  # noqa: F401


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

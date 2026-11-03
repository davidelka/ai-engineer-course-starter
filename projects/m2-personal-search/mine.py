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

    rel_path: relative, "/"-separated ("kids/2026/report.pdf"); strip a leading "./".
    Matching is case-insensitive (lower-case both sides). Empty patterns and "#comments" are skipped.

    Three kinds of pattern:
      "*.key", ".*", "*password*"   no "/": fnmatch against EVERY component of the path, folders
                                    AND file name. So ".*" excludes ".env" and also anything under
                                    ".git/" or ".cache/".
      "private/"                    trailing "/": a FOLDER name pattern. Excluded when any folder
                                    component (not the file name) matches it: "a/private/x.txt" yes,
                                    "notes/private.txt" no.
      "finance/*.pdf", "kids/**/report*"
                                    "/" inside: matched against the WHOLE path. "*" and "?" never
                                    cross a "/", "**/" matches zero or more folders ("kids/**/report*"
                                    matches "kids/report.pdf" and "kids/2026/t1/report.pdf").
                                    A leading "/" is ignored.
    The scanner also calls you with a folder followed by "/x" (e.g. "node_modules/x") to decide
    whether to skip a whole folder without walking into it.
    """
    # TODO(M2)
    raise NotImplementedError("M2: implement is_excluded")


# ------------------------------------------------------------------ M3: incremental sync
def plan_sync(manifest: dict[str, dict], current: dict[str, dict], hash_fn: Callable[[str], str]) -> SyncPlan:
    """Decide what to re-index. Return a SyncPlan (pss/manifest.py) with SORTED lists:

    manifest: what the index holds  {id: {"hash", "size", "mtime", ...}}
    current:  what the scan found   {id: {"size", "mtime"}}  (a stat call, the file was NOT read)
    hash_fn(id) reads the file and returns its content hash. It is SLOW on a big folder:
    call it only when needed, and at most once per id.

      id in current, not in manifest                    -> added    (hash it)
      in both, same size AND same mtime                 -> unchanged (do NOT hash)
      in both, size or mtime differs, hash == manifest  -> touched  (only metadata moved)
      in both, size or mtime differs, hash != manifest  -> changed
      id in manifest, not in current                    -> removed
    plan.hashes = {id: hash} for every id you hashed (the indexer stores them).
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement plan_sync")


# ------------------------------------------------------------------ M5: query filters
def parse_query(q: str) -> ParsedQuery:
    """Split filters out of a query. Return ParsedQuery(text, filters, warnings).

    A filter token is key:value or key:"value with spaces", preceded by start or whitespace.
    Keys (KEYS maps both English and Hebrew names to the canonical key):
      type   / סוג      comma list; each value through TYPES ("doc"->"docx", "scan"->"image").
                       filters["type"] = list in order, no duplicates. Unknown value -> warning.
      folder / תיקייה  comma list; strip "/" and lower-case. filters["folder"] = list.
      after  / אחרי    norm_date(value) -> "YYYY-MM-DD" (start of the period: "2026-06" -> "2026-06-01").
      before / לפני    same. A bad date -> warning, and the token STAYS in the text.
      lang   / שפה     through LANGS ("עברית" -> "he"). Unknown -> warning.
    A token with an unknown key ("10:40", "http://x") is not a filter: it stays in the text.
    text = everything that is not a filter, with whitespace collapsed to single spaces.

    Example: parse_query('type:pdf,doc folder:"kids/" after:2026-06 טיול שנתי')
      -> text "טיול שנתי", filters {"type": ["pdf", "docx"], "folder": ["kids"], "after": "2026-06-01"}
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement parse_query")


# ------------------------------------------------------------------ M6: near-duplicates
def near_duplicate_groups(docs: dict[str, str], threshold: float = 0.8, k: int = 3) -> list[list[str]]:
    """Group documents that are (nearly) the same text.

    docs: {file_id: text}. Two documents are similar when jaccard(shingles(a, k), shingles(b, k))
    >= threshold (shingles and jaccard are imported above: k-word shingles, lower-cased).
    Documents with no shingles (empty text) are never similar to anything.
    Groups are TRANSITIVE: if A~B and B~C then A, B and C are one group even when A and C are not
    similar enough on their own (use union-find, or a BFS over the similarity graph).
    Return only groups with 2+ members; each group sorted; the list sorted by each group's first id.
    """
    # TODO(M6)
    raise NotImplementedError("M6: implement near_duplicate_groups")


# ------------------------------------------------------------------ M8: redaction before the cloud
def redact_for_cloud(text: str) -> tuple[str, dict[str, int]]:
    """Mask personal identifiers. Return (redacted text, {label: count}) with only labels whose
    count > 0. Apply, IN THIS ORDER:

      IBAN          Israeli IBAN: "IL" + 2 digits + 19 digits, optionally in groups of 4 separated by
                    spaces or "-" (e.g. "IL62 0108 0000 0009 9999 999")         -> "[IBAN]"
      CARD          a run of 13-19 digits, single spaces or "-" allowed between digits, not touching
                    another digit or "-", that passes luhn_ok (imported above)   -> "[CARD]"
                    (a 16-digit number that fails Luhn is an order number: leave it)
      IL_ID, EMAIL, PHONE   guardkit's redact_pii(text) (imported above) does these three and writes
                    "[IL_ID]", "[EMAIL]", "[PHONE]". Count them by comparing how many of each
                    placeholder the text had before and after the call.
      BANK_ACCOUNT  bank-branch-account written as dd-ddd-dddd..ddddddddd (2, 3, then 4-9 digits),
                    not touching another digit or "-"                            -> "[BANK_ACCOUNT]"
    Why this order: an IBAN contains a card-like digit run, and a card number contains digits that
    could look like a phone number; the more specific pattern must win.
    """
    # TODO(M8)
    raise NotImplementedError("M8: implement redact_for_cloud")

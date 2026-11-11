"""Near-duplicate documents: the same file downloaded twice, a "-copy", a v2 with one line changed.

In a personal folder duplicates are everywhere, and they hurt search twice: they push other
files out of the top results, and an answer may cite an older copy. The index finds groups of
near-duplicates once (at index time), and search shows one member with "also in: ...".

Method: word shingles (every run of k consecutive words), Jaccard similarity of the shingle
sets, and union-find so that A~B and B~C put A, B and C in one group. For a few thousand files
the all-pairs loop is fine (n^2/2 set comparisons of small sets); past that, MinHash + LSH
(datasketch) finds candidate pairs without comparing everything.
"""

from __future__ import annotations

import re

WORD = re.compile(r"\w+", re.U)


def shingles(text: str, k: int = 3) -> set[tuple[str, ...]]:
    words = WORD.findall(text.lower())
    if len(words) < k:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def near_duplicate_groups(*args, **kwargs):
    """Milestone 6: runs your mine.near_duplicate_groups (see pss/hooks.py)."""
    from . import hooks
    return hooks.get("near_duplicate_groups")(*args, **kwargs)

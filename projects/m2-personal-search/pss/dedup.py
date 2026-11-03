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


def near_duplicate_groups(docs: dict[str, str], threshold: float = 0.8, k: int = 3) -> list[list[str]]:
    """Reference implementation (see mine.near_duplicate_groups for the contract)."""
    ids = sorted(docs)
    sh = {i: shingles(docs[i], k) for i in ids}
    parent = {i: i for i in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for n, a in enumerate(ids):
        if not sh[a]:
            continue
        for b in ids[n + 1:]:
            if sh[b] and jaccard(sh[a], sh[b]) >= threshold:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return sorted((sorted(g) for g in groups.values() if len(g) > 1), key=lambda g: g[0])

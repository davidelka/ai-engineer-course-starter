"""A tiny BM25 index, self-contained (the real one lives in ragkit, lesson 9-11).

Enough for a lab with ~50 chunks: Unicode word tokens, lower-case, a short English
stopword list, and for Hebrew words one extra token with a single leading prefix letter
(ו ה ב ל מ ש כ) removed, so "בחופשה" also matches "חופשה".
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Sequence

from .types import Chunk

_TOKEN = re.compile(r"[\w][\w'-]*", re.UNICODE)
_HEB = re.compile(r"^[֐-׿]+$")
STOP = frozenset("""a an and are as at be by can do does for from has have how i if in is it its
me my of on or our so that the their them then there these this to us was we what when where which
who why will with you your""".split())


def analyze(text: str) -> list[str]:
    out: list[str] = []
    for tok in _TOKEN.findall(text.lower()):
        if tok in STOP:
            continue
        out.append(tok)
        if _HEB.match(tok) and len(tok) > 3 and tok[0] in "והבלמשכ":
            out.append(tok[1:])
    return out


class BM25:
    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.4, b: float = 0.75):
        self.chunks = list(chunks)
        self.k1, self.b = k1, b
        self.docs = [Counter(analyze(c.meta.get("title", "") + " " + c.text)) for c in self.chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 1.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = analyze(query)
        out = []
        for d, ln in zip(self.docs, self.lens):
            s = 0.0
            for t in q:
                f = d.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * ln / self.avg))
            out.append(s)
        return out

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        sc = self.scores(query)
        order = sorted(range(len(sc)), key=lambda i: (-sc[i], i))
        return [self.chunks[i] for i in order[:k] if sc[i] > 0]

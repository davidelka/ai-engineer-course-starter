"""Deterministic metrics: cheap, exact, reproducible. Run them on every example, every time.

String checks     exact_match, contains, regex_match (after the same normalization)
Structured        per_field_accuracy (lesson 3's extraction eval, generalized)
Retrieval         hit_at_k, recall_at_k, mrr: computed from the ranked doc ids of ragkit Hits
Answers           fact_coverage: share of the golden answer_facts the answer states
                  citation_scores: precision/recall of cited documents vs golden sources,
                  and whether a superseded ("stale") version was cited

fact_coverage is LEXICAL on purpose: a fact counts as covered when every number in it appears
in the answer and at least half of its content words do. It is fast and free and it catches
the common failures (wrong number, missing fact, abstained). Its blind spots are known and
are exactly what the LLM judge (evalkit.judge) is for: paraphrase ("two weeks" vs "14 days"),
an answer in Hebrew for English facts, and negation ("no forced rotation" vs "forced
rotation" share all their words). Lab exercise 2 asks you to write both functions yourself;
these are the reference versions.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, Optional, Sequence

# ------------------------------------------------------------------ normalization
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
_NUM = re.compile(r"\d+(?:[.:]\d+)*")
_WORD = re.compile(r"[^\W\d_]+", re.U)
_HEB = re.compile(r"^[א-ת]+$")
HEB_PREFIX = set("והבלמשכ")

STOPWORDS = frozenset("""a an and are as at be but by can do does for from has have how i if in is it its
of on or so than that the their them then there these they this to was we were what when where which who
will with you your per up not
של את על עם זה זו זאת הוא היא הם הן גם או אם כי כן יש מה מי איך כמה למה מתי איפה כל עד אל בין רק עוד""".split())


def normalize_text(s: str) -> str:
    """NFKC, lowercase, typographic quotes/dashes unified, thousands separators removed
    ("3,000" -> "3000"), whitespace collapsed."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                                   "–": "-", "—": "-", "״": '"', "׳": "'"}))
    s = _THOUSANDS.sub("", s)
    return " ".join(s.split())


def numbers_in(s: str) -> set[str]:
    """{"85", "99.89", "10:00"} from "$85 ... 99.89% ... at 10:00"."""
    return set(_NUM.findall(normalize_text(s)))


def word_variants(w: str) -> set[str]:
    """The word plus crude stems: Hebrew without 1-2 attached prefix letters (בחניון -> חניון),
    English without a plural s (days -> day)."""
    out = {w}
    if _HEB.match(w) and len(w) >= 4 and w[0] in HEB_PREFIX:
        out.add(w[1:])
        if len(w) >= 5 and w[1] in HEB_PREFIX:
            out.add(w[2:])
    if w.isascii() and len(w) > 3 and w.endswith("s"):
        out.add(w[:-1])
    return out


def content_words(s: str) -> list[str]:
    """Words (letters only), lowercased, without stopwords and one-letter words, in order."""
    return [w for w in _WORD.findall(normalize_text(s)) if len(w) > 1 and w not in STOPWORDS]


# ------------------------------------------------------------------ string checks
def exact_match(output: str, expected: str) -> bool:
    return normalize_text(output) == normalize_text(expected)


def contains(output: str, expected: str) -> bool:
    return normalize_text(expected) in normalize_text(output)


def contains_all(output: str, needles: Iterable[str]) -> bool:
    return all(contains(output, n) for n in needles)


def regex_match(output: str, pattern: str) -> bool:
    return re.search(pattern, output or "", re.I | re.S) is not None


def per_field_accuracy(pred: dict, gold: dict, fields: Optional[Sequence[str]] = None) -> dict[str, bool]:
    """{field: pred == gold} for every field of gold (or `fields`). A gold value that is a
    list means "any of these is acceptable" (lesson 3's ambiguous fields)."""
    out = {}
    for f in fields or list(gold):
        g, p = gold.get(f), pred.get(f)
        if isinstance(g, list) and not isinstance(p, list):
            out[f] = p in g
        elif isinstance(g, str) and isinstance(p, str):
            out[f] = normalize_text(g) == normalize_text(p)
        else:
            out[f] = p == g
    return out


# ------------------------------------------------------------------ retrieval
def hit_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> Optional[float]:
    rel = set(relevant)
    if not rel:
        return None
    return float(bool(rel & set(retrieved[:k])))


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> Optional[float]:
    """Share of the relevant documents that appear in the top-k (duplicates in `retrieved`
    count once). None when there is nothing relevant (an unanswerable question)."""
    rel = set(relevant)
    if not rel:
        return None
    return len(rel & set(retrieved[:k])) / len(rel)


def mrr(retrieved: Sequence[str], relevant: Iterable[str]) -> Optional[float]:
    """1 / rank of the first relevant document (ranks start at 1); 0 if none is retrieved."""
    rel = set(relevant)
    if not rel:
        return None
    for i, d in enumerate(retrieved, 1):
        if d in rel:
            return 1.0 / i
    return 0.0


def doc_ids_from_hits(hits: Iterable[Any]) -> list[str]:
    """Ranked doc ids from ragkit Hits (several chunks of one doc keep the first rank)."""
    return list(dict.fromkeys(h.chunk.doc_id for h in hits))


# ------------------------------------------------------------------ answers
def fact_covered(answer: str, fact: str, min_word_recall: float = 0.5) -> bool:
    """Every number of the fact appears in the answer, and at least `min_word_recall` of the
    fact's content words appear (any variant of a fact word may match any variant of an
    answer word). A fact with no content words is decided by its numbers alone, or, with no
    numbers either, by a normalized substring test."""
    nums = numbers_in(fact)
    if nums - numbers_in(answer):
        return False
    fwords = content_words(fact)
    if not fwords:
        return bool(nums) or normalize_text(fact) in normalize_text(answer)
    avail: set[str] = set()
    for w in content_words(answer):
        avail |= word_variants(w)
    matched = sum(1 for w in fwords if word_variants(w) & avail)
    return matched / len(fwords) >= min_word_recall


def fact_coverage(answer: str, facts: Sequence[str], min_word_recall: float = 0.5) -> Optional[float]:
    """Share of facts covered, or None when there are no facts (unanswerable questions)."""
    if not facts:
        return None
    return sum(fact_covered(answer, f, min_word_recall) for f in facts) / len(facts)


def citation_scores(cited: Sequence[str], source_ids: Sequence[str],
                    stale_ids: Sequence[str] = ()) -> dict[str, Any]:
    """Document-level citation quality.

    Answerable (source_ids not empty):
        precision = |cited ∩ sources| / |cited|   (0.0 when nothing is cited)
        recall    = |cited ∩ sources| / |sources|
    Unanswerable: precision = recall = 1.0 when nothing is cited, else 0.0.
    stale = True when any cited doc is a superseded version (stale_ids).
    Duplicates in `cited` count once."""
    c, s = set(cited), set(source_ids)
    stale = bool(c & set(stale_ids))
    if not s:
        ok = 0.0 if c else 1.0
        return {"precision": ok, "recall": ok, "stale": stale}
    inter = len(c & s)
    return {"precision": inter / len(c) if c else 0.0, "recall": inter / len(s), "stale": stale}


def abstained(answer: str, marker: str = "not in the documents") -> bool:
    return marker in normalize_text(answer)

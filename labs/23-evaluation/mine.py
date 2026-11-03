"""Your code for lesson 23. Each part is checked by tests in ./tests.

Reference versions live in evalkit/metrics.py, evalkit/stats.py and evalkit/calibration.py.
Try not to peek before your tests pass.

    python -m pytest -q labs/23-evaluation/tests

Only the standard library is needed (re, unicodedata, random, collections, math).
"""

from __future__ import annotations

import math  # noqa: F401
import random  # noqa: F401
import re  # noqa: F401
import unicodedata  # noqa: F401
from collections import Counter  # noqa: F401
from typing import Optional, Sequence

# ============================================================ exercise 2: answer metrics
#
# The data these functions score (data/acme/corpus/golden/qa.jsonl), one golden question:
#   {"id": "q001", "type": "version_conflict",
#    "question": "How many unused vacation days can I carry over to next year, and when do they expire?",
#    "answer_facts": ["up to 5 days can be carried over", "carried-over days expire on March 31"],
#    "source_ids": ["hr-vacation-2026"], "tags": ["stale:hr-vacation-2024"], ...}
# and one system output (from run_eval.py):
#   {"answer": "Up to 5 unused days may be carried over ... expire on March 31. [1]",
#    "cited_docs": ["hr-vacation-2026"], ...}

STOPWORDS = frozenset("""a an and are as at be but by can do does for from has have how i if in is it its
of on or so than that the their them then there these they this to was we were what when where which who
will with you your per up not
של את על עם זה זו זאת הוא היא הם הן גם או אם כי כן יש מה מי איך כמה למה מתי איפה כל עד אל בין רק עוד""".split())
HEB_PREFIX = set("והבלמשכ")


def fact_covered(answer: str, fact: str, min_word_recall: float = 0.5) -> bool:
    """Does `answer` state `fact`? A lexical rule, specified exactly so the tests can check it.

    1. Normalize both texts: unicodedata.normalize("NFKC", s).lower(), and remove a comma that
       sits between digits when exactly three digits follow it ("3,000" -> "3000").
    2. Numbers: every match of  \\d+(?:[.:]\\d+)*  in the fact must also be a match in the
       answer ("85", "99.89", "10:00"). If any is missing, return False.
    3. Content words of a text: matches of  [^\\W\\d_]+  that are longer than one character and
       not in STOPWORDS (above).
    4. Variants of a word w: {w}, plus for a Hebrew word (only letters א-ת) of 4+ letters that
       starts with a letter in HEB_PREFIX: w without its first letter, and if it has 5+
       letters and its second letter is also in HEB_PREFIX, w without its first two letters;
       plus for an ASCII word longer than 3 letters ending in "s": w without the final "s".
    5. A fact word is matched when any of its variants is among the variants of any answer word.
    6. If the fact has no content words: return True if it had numbers (they all matched),
       otherwise return whether the normalized fact is a substring of the normalized answer.
    7. Otherwise return matched_words / fact_words >= min_word_recall.

    Examples:
      fact_covered("Up to 5 days carry over [1].", "up to 5 days can be carried over")  -> True
      fact_covered("Up to 3 days carry over.",     "up to 5 days can be carried over")  -> False (5 missing)
      fact_covered("מקבלים 14 ימים של חופשה", "14 ימים")                               -> True
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement fact_covered")


def fact_coverage(answer: str, facts: Sequence[str], min_word_recall: float = 0.5) -> Optional[float]:
    """Share of `facts` that fact_covered() finds in `answer`; None when `facts` is empty
    (an unanswerable question has no facts, and "not applicable" must not count as 0)."""
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement fact_coverage")


def citation_scores(cited: Sequence[str], source_ids: Sequence[str], stale_ids: Sequence[str] = ()) -> dict:
    """Document-level citation quality. Returns {"precision": float, "recall": float, "stale": bool}.

    Treat each argument as a SET (a doc cited twice counts once).
    Answerable question (source_ids not empty):
        precision = |cited ∩ sources| / |cited|, or 0.0 when nothing is cited
        recall    = |cited ∩ sources| / |sources|
    Unanswerable question (source_ids empty): precision = recall = 1.0 if nothing is cited,
        else 0.0 for both (citing anything means the system pretended to know).
    stale = True when any cited doc is in stale_ids (a superseded policy version).

    Examples:
      citation_scores(["hr-vacation-2026"], ["hr-vacation-2026"], ["hr-vacation-2024"])
          -> {"precision": 1.0, "recall": 1.0, "stale": False}
      citation_scores(["hr-vacation-2024", "hr-vacation-2026"], ["hr-vacation-2026"], ["hr-vacation-2024"])
          -> {"precision": 0.5, "recall": 1.0, "stale": True}
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement citation_scores")


# ============================================================ exercise 3: statistics
def percentile(sorted_xs: Sequence[float], q: float) -> float:
    """Given (already sorted) values and q in [0, 1]: linear interpolation between the closest
    ranks, like numpy's default. Provided, so your CI matches the reference exactly."""
    pos = q * (len(sorted_xs) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)


def bootstrap_ci(values: Sequence[float], n_resamples: int = 2000, level: float = 0.95,
                 seed: int = 0) -> tuple[float, float, float]:
    """Percentile bootstrap CI of the MEAN. Returns (mean, low, high).

    rng = random.Random(seed). Repeat n_resamples times: build a resample of len(values) items,
    each item values[rng.randrange(n)] (draw in that order: this exact sequence of rng calls
    makes your numbers equal the reference's), and record its mean. Sort the recorded means.
    low = percentile(sorted_means, (1 - level) / 2), high = percentile(sorted_means, 1 - (1 - level) / 2).
    Raise ValueError for an empty list.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement bootstrap_ci")


def paired_compare(a: Sequence[float], b: Sequence[float], n_resamples: int = 2000, level: float = 0.95,
                   seed: int = 0) -> dict:
    """Compare version B against version A on the SAME examples (a[i] and b[i] are the scores
    of example i). Returns
        {"diff": mean of d, "low": ..., "high": ..., "p_value": ..., "wins": int, "losses": int, "ties": int}
    where d[i] = b[i] - a[i].

    - Raise ValueError if the lengths differ or the lists are empty.
    - Bootstrap the mean of d exactly like bootstrap_ci (same rng, same draw order, sorted means).
    - low/high: the percentile interval of the resampled means.
    - p_value: let le = share of resampled means <= 0 and ge = share >= 0;
      p_value = min(1.0, 2 * min(le, ge)).
    - wins = count of d[i] > 0, losses = count of d[i] < 0, ties = count of d[i] == 0.

    Why paired: question q041 is hard for every version. Comparing two separate CIs carries that
    difficulty in both; per-example differences cancel it, so smaller real changes show up.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement paired_compare")


# ============================================================ exercise 5: judge calibration
def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """Cohen's kappa between two label lists of the same, non-zero length (else ValueError).

    p_o = share of positions where human[i] == judge[i]
    p_e = sum over every label L that appears in either list of
          (count of L in human / n) * (count of L in judge / n)
    kappa = (p_o - p_e) / (1 - p_e)
    Special case p_e == 1 (both lists use one and the same label everywhere): return 1.0.

    Example: human = [g, g, g, n], judge = [g, g, n, n]
             p_o = 3/4, p_e = (3/4)(2/4) + (1/4)(2/4) = 0.5, kappa = 0.5
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement cohen_kappa")

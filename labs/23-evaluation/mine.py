"""Your code for lesson 23. Each part is checked by tests in ./tests.

Reference versions live in evalkit/metrics.py, evalkit/stats.py and evalkit/calibration.py.
Try not to peek before your tests pass. Stuck? HINTS.md in this folder has graded hints.

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
    """Does `answer` state `fact`? A lexical rule; it must agree with the reference
    (evalkit.metrics) on every golden question, so these definitions are the interface:

    - Both texts are compared case-insensitively after NFKC normalization, and a thousands
      comma between digits does not matter ("3,000" == "3000").
    - Numbers ("85", "99.89", "10:00"): every number in the fact must appear in the answer,
      otherwise False.
    - Content words: runs of letters, longer than one character, not in STOPWORDS. A fact
      word may match an answer word through a Hebrew one- or two-letter prefix from
      HEB_PREFIX ("בחניון" ~ "חניון") or an English plural "s" ("days" ~ "day").
    - True when matched fact words / fact words >= min_word_recall. A fact with no content
      words: True if it had numbers (all found), else whether it is a substring of the answer.

    Examples:
      fact_covered("Up to 5 days carry over [1].", "up to 5 days can be carried over")  -> True
      fact_covered("Up to 3 days carry over.",     "up to 5 days can be carried over")  -> False (5 missing)
      fact_covered("מקבלים 14 ימים של חופשה", "14 ימים")                               -> True

    Stuck? HINTS.md -> fact_covered
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement fact_covered")


def fact_coverage(answer: str, facts: Sequence[str], min_word_recall: float = 0.5) -> Optional[float]:
    """Share of `facts` that fact_covered() finds in `answer`; None when `facts` is empty
    (an unanswerable question has no facts, and "not applicable" must not count as 0).

    Stuck? HINTS.md -> fact_coverage
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement fact_coverage")


def citation_scores(cited: Sequence[str], source_ids: Sequence[str], stale_ids: Sequence[str] = ()) -> dict:
    """Document-level citation quality. Returns {"precision": float, "recall": float, "stale": bool}.

    - Each argument is a SET: a doc cited twice counts once.
    - Answerable question (source_ids not empty): the usual precision and recall of the cited
      docs against the sources; precision is 0.0 when nothing is cited.
    - Unanswerable question (source_ids empty): both 1.0 if nothing is cited, else both 0.0
      (citing anything means the system pretended to know).
    - stale: True when any cited doc is a superseded version listed in stale_ids.

    Examples:
      citation_scores(["hr-vacation-2026"], ["hr-vacation-2026"], ["hr-vacation-2024"])
          -> {"precision": 1.0, "recall": 1.0, "stale": False}
      citation_scores(["hr-vacation-2024", "hr-vacation-2026"], ["hr-vacation-2026"], ["hr-vacation-2024"])
          -> {"precision": 0.5, "recall": 1.0, "stale": True}

    Stuck? HINTS.md -> citation_scores
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
    """Percentile bootstrap confidence interval of the MEAN. Returns (mean, low, high).

    - mean is the plain mean of `values`; low/high bound the central `level` share of the
      resampled means, read with percentile() above.
    - Reproducibility contract (the test compares with the reference to many decimals):
      use one rng = random.Random(seed), and draw every resampled item as
      values[rng.randrange(len(values))], resample after resample, item after item.
    - Empty list -> ValueError.

    Stuck? HINTS.md -> bootstrap_ci
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement bootstrap_ci")


def paired_compare(a: Sequence[float], b: Sequence[float], n_resamples: int = 2000, level: float = 0.95,
                   seed: int = 0) -> dict:
    """Compare version B against version A on the SAME examples (a[i] and b[i] are the scores
    of example i). Returns
        {"diff": mean of d, "low": ..., "high": ..., "p_value": ..., "wins": int, "losses": int, "ties": int}
    where d[i] = b[i] - a[i].

    - ValueError if the lengths differ or the lists are empty.
    - diff/low/high: the bootstrap of the mean of d, with the same reproducibility contract
      as bootstrap_ci (so the numbers equal the reference's).
    - p_value: a two-sided bootstrap p-value for "the mean difference is 0", read from the
      same resampled means, capped at 1.0.
    - wins / losses / ties: how many examples got better / worse / stayed equal under B.

    Why paired: question q041 is hard for every version. Comparing two separate CIs carries that
    difficulty in both; per-example differences cancel it, so smaller real changes show up.

    Stuck? HINTS.md -> paired_compare
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement paired_compare")


# ============================================================ exercise 5: judge calibration
def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """Cohen's kappa between two label lists of the same, non-zero length (else ValueError).

    Agreement corrected for chance: 1.0 is perfect agreement, 0.0 is what two raters who
    only share their label frequencies would reach, below 0 is worse than chance. Labels
    are arbitrary strings, any number of them. Special case: when chance agreement is
    already 1 (both lists use one and the same label everywhere), return 1.0.

    Examples: human = [g, g, g, n], judge = [g, g, n, n] -> 0.5
              human = [g, g, g, n], judge = [g, g, g, g] -> 0.0 (75% agreement, no information)

    Stuck? HINTS.md -> cohen_kappa
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement cohen_kappa")

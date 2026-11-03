"""Your code for lesson 28. Each part is checked by tests in ./tests.

interviewkit/ (rubric.py, srs.py, aicoding.py) has reference versions.
Try not to peek before your tests pass.

    python -m pytest -q labs/28-interview-prep/tests
"""

from __future__ import annotations

import math  # noqa: F401
import re  # noqa: F401
from datetime import date, timedelta  # noqa: F401
from typing import Callable, Iterable, Optional

import numpy as np  # noqa: F401

from interviewkit.aicoding import MESSAGE_OVERHEAD, approx_tokens  # noqa: F401
from interviewkit.rubric import CONCRETE_TERMS, MEASURE_TERMS, TRADEOFF_TERMS, normalize  # noqa: F401


# ------------------------------------------------------------------ exercise 2
def term_in(text: str, term: str) -> bool:
    """True if `term` appears in `text` under these rules (both sides go through normalize()):

      - case-insensitive; "-", "_" and "/" count as spaces; whitespace runs collapse
        (normalize() from interviewkit.rubric already does exactly this)
      - a term that starts with a Latin letter or digit must not be glued to a Latin
        letter/digit on its left:  "rag" is in "RAG pipeline", not in "drag"
      - Hebrew prefixes are fine:  "אמבדינג" is in "והאמבדינג"  (only [a-z0-9] block)
      - a term that ends with a Latin letter may take an English plural "s" or "es",
        and must not be glued to a Latin letter/digit on its right:
            "embedding" is in "embeddings", "eval" is not in "evaluate"
      - a term that ends with "*" is a prefix: "calibrat*" is in "calibration"
      - a term whose edge is not alphanumeric has no boundary on that side:
            "%" is in "20%"
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement term_in")


def score_answer(answer: str, question: dict, min_words: int = 40, max_words: int = 400) -> dict:
    """Score an interview answer against question["rubric"], without an LLM.

    A rubric is a list of points:
        {"id": "r1", "point": "...", "weight": 2,
         "concepts": [["recall", "recall@k"], ["golden set"]],   # groups of synonyms
         "need": 1}                                              # optional, default 1
    A concept group matches if ANY of its terms is in the answer (use term_in).
    A group given as a plain string counts as a one-term group.
    A point is covered when at least min(need, number of groups) groups match.

    Structure checks (all booleans):
        length_ok:   min_words <= len(answer.split()) <= max_words
        tradeoff:    any term of TRADEOFF_TERMS is in the answer
        concrete:    the answer contains a digit, or any term of CONCRETE_TERMS
        measurement: the answer contains "%", or any term of MEASURE_TERMS

    Return:
        {"score": int,            # round(100 * (0.75 * coverage + 0.25 * checks_passed / 4))
         "coverage": float,       # covered weight / total weight, rounded to 3 places
         "covered": [ids],        # in rubric order
         "missing": [ids],        # in rubric order
         "hits": {id: [the first matching term of each matched group]},
         "checks": {"length_ok": .., "tradeoff": .., "concrete": .., "measurement": ..},
         "words": int}
    Raise ValueError if the rubric is empty or its total weight is 0.
    A point without "weight" has weight 1.
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement score_answer")


# ------------------------------------------------------------------ exercise 3
def sm2_review(state: Optional[dict], grade: int, today: date) -> dict:
    """One SM-2 review. Return a NEW state dict; never mutate `state`.

    state is None for a new card, else a dict with (at least) these keys:
        ef (float, starts 2.5), reps (int, starts 0), interval (int days, starts 0),
        lapses (int, starts 0), due ("YYYY-MM-DD"), last ("YYYY-MM-DD")
    Keep any other keys of `state` as they are.

    grade: int 0..5 (5 perfect, 3 correct with effort, 0-2 failed). Anything else
    (including bool, float, 6, -1) raises ValueError.

    If grade >= 3:  interval = 1 if reps == 0, 6 if reps == 1, else round(interval * ef)
                    (Python's round(), using the OLD ef); then reps += 1
    If grade < 3:   reps = 0, interval = 1, lapses += 1
    Always, after the interval: ef = ef + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
                    then ef = max(1.3, ef), rounded to 4 places.
    due = today + interval days (ISO string), last = today (ISO string).
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement sm2_review")


def grade_from_score(score: float) -> int:
    """Map a 0-100 answer score to an SM-2 grade:
    >= 90 -> 5, >= 75 -> 4, >= 60 -> 3, >= 40 -> 2, >= 20 -> 1, else 0."""
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement grade_from_score")


def pick_session(bank_ids: Iterable[str], states: dict[str, dict], today: date,
                 new_per_day: int = 5, limit: int = 15) -> list[str]:
    """Which questions to practise today, in order.

    1. Due reviews: ids from bank_ids that have a state with due <= today, sorted by
       (due, ef, id): the most overdue first, and among equals the harder card (lower ef).
       States of ids that are not in bank_ids are ignored.
    2. Then new cards: ids from bank_ids without a state, in bank order, at most new_per_day.
    3. The whole list is cut to `limit`.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement pick_session")


# ------------------------------------------------------------------ exercise 6
def top_k_cosine(query: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    """The k rows of `matrix` (shape (n, d)) most similar to `query` (shape (d,)).

    Return [(row_index, cosine_similarity), ...] sorted by similarity, highest first;
    equal similarities keep the lower index first. Indexes are Python ints, scores floats.
    - a zero vector (query or row) has similarity 0.0 with everything (no NaN, no warning)
    - k <= 0 or an empty matrix -> []
    - k > n -> all n rows
    - query not 1-D, matrix not 2-D, or d mismatch -> ValueError
    Vectorize with numpy: no Python loop over the rows.
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement top_k_cosine")


def fit_to_budget(messages: list[dict], budget: int,
                  count: Callable[[str], int] = approx_tokens) -> list[dict]:
    """Trim a chat history to fit a token budget. messages: [{"role": ..., "content": ...}]
    with role in system / user / assistant. A message costs count(content) + MESSAGE_OVERHEAD.

    Rules:
      1. Every system message is kept, and they come first in the result.
      2. The last non-system message (the current turn) is always kept. If the system
         messages plus that message exceed the budget, raise ValueError.
         No non-system messages at all -> ValueError.
      3. Walk back from the newest older message and keep messages while the total
         still fits. Stop at the first one that does not fit (never skip it to keep an
         even older one: the kept history must be contiguous).
      4. If more than one non-system message is kept and the oldest kept one is from
         the assistant, drop it, so the conversation starts with the user.
      5. Return new dicts (copies), in the original order. Do not mutate the input.
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement fit_to_budget")

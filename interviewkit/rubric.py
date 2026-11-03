"""Rubric scoring without an LLM (lesson 28, reference for exercise 2).

A question in the bank carries a rubric: a list of points an interviewer expects
to hear. Each point lists *concept groups*; a group is a set of synonyms (Hebrew
and English), and it matches when any synonym appears in the answer.

This is deliberately simple and transparent: it measures *coverage of concepts*,
not understanding. It is a fast, free first signal and a sanity check for the
LLM grader, never a replacement for it. A candidate who lists buzzwords scores
well here; the LLM grader and a human interviewer will not be fooled.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

TRADEOFF_TERMS = ["trade off", "tradeoff", "אבל", "לעומת", "מצד שני", "על חשבון", "חיסרון", "חסרון",
                  "במחיר", "but", "however", "versus", "vs", "the cost is"]
CONCRETE_TERMS = ["למשל", "לדוגמה", "לדוגמא", "for example", "for instance", "e.g."]
MEASURE_TERMS = ["מדד", "למדוד", "מדידה", "מודד", "מדדתי", "eval", "metric", "p50", "p95", "p99",
                 "recall", "precision", "accuracy", "golden set", "אחוז", "latency", "cost per"]


def normalize(text: str) -> str:
    """Lowercase, turn - _ / into spaces, collapse whitespace."""
    text = re.sub(r"[-_/]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def term_pattern(term: str) -> re.Pattern:
    """A normalized term, not glued to Latin letters or digits on either side.

    Hebrew prefixes (ו, ה, ב, ל, מ, ש, כ) are allowed before a term because the
    boundary only looks at [a-z0-9]. An English plural "s"/"es" is allowed after
    a term that ends in a Latin letter. Boundaries apply only on a side where the
    term itself starts/ends with [a-z0-9], so "%" still matches inside "20%".
    A trailing "*" makes the term a prefix: "calibrat*" matches "calibration".
    """
    prefix = term.endswith("*")
    n = normalize(term.rstrip("*"))
    left = r"(?<![a-z0-9])" if n[:1].isascii() and n[:1].isalnum() else ""
    if prefix:
        return re.compile(left + re.escape(n))
    plural = "(?:s|es)?" if n[-1:].isascii() and n[-1:].isalpha() else ""
    right = r"(?![a-z0-9])" if n[-1:].isascii() and n[-1:].isalnum() else ""
    return re.compile(left + re.escape(n) + plural + right)


def term_in(text: str, term: str) -> bool:
    """normalize() is idempotent, so already-normalized text is fine too."""
    return bool(term_pattern(term).search(normalize(text)))


def any_term(text_norm: str, terms: Iterable[str]) -> bool:
    return any(term_in(text_norm, t) for t in terms)


def _groups(point: dict) -> list[list[str]]:
    return [[g] if isinstance(g, str) else list(g) for g in point.get("concepts", [])]


def structure_checks(answer: str, min_words: int = 40, max_words: int = 400) -> dict[str, bool]:
    norm = normalize(answer)
    words = len(answer.split())
    return {
        "length_ok": min_words <= words <= max_words,
        "tradeoff": any_term(norm, TRADEOFF_TERMS),
        "concrete": bool(re.search(r"\d", answer)) or any_term(norm, CONCRETE_TERMS),
        "measurement": "%" in answer or any_term(norm, MEASURE_TERMS),
    }


def score_answer(answer: str, question: dict[str, Any], min_words: int = 40, max_words: int = 400) -> dict:
    """Score an answer against question["rubric"]. See labs/28-interview-prep/mine.py for the spec."""
    rubric = question.get("rubric") or []
    total = sum(p.get("weight", 1) for p in rubric)
    if total <= 0:
        raise ValueError("rubric has no weight")
    norm = normalize(answer)
    covered, missing, hits = [], [], {}
    got = 0.0
    for p in rubric:
        groups = _groups(p)
        matched = []
        for g in groups:
            m = next((t for t in g if term_in(norm, t)), None)
            if m is not None:
                matched.append(m)
        need = min(p.get("need", 1), len(groups)) if groups else 1
        hits[p["id"]] = matched
        if groups and len(matched) >= need:
            covered.append(p["id"])
            got += p.get("weight", 1)
        else:
            missing.append(p["id"])
    checks = structure_checks(answer, min_words, max_words)
    coverage = got / total
    score = round(100 * (0.75 * coverage + 0.25 * sum(checks.values()) / len(checks)))
    return {"score": score, "coverage": round(coverage, 3), "covered": covered, "missing": missing,
            "hits": hits, "checks": checks, "words": len(answer.split())}

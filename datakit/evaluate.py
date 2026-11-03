"""Evaluating data answers (lesson 8): execution accuracy.

Two SQL queries can look nothing alike and return the same answer, or look almost
identical and return different answers. So we do not compare SQL text: we run the
predicted SQL and compare its RESULT with the golden result. This is "execution
accuracy" (EX), the metric of Spider and BIRD.

Details that decide whether EX is fair:
- row order only matters when the question asks for an order ("top 3 by ...")
- values are normalized: 3 == 3.0, floats rounded, strings trimmed
- column order does not matter (Spider's evaluator also permutes columns)
- extra columns: strict EX fails them; allow_extra_columns accepts a prediction whose
  columns CONTAIN the golden ones (e.g. name + count when the gold is just count)
"""

from __future__ import annotations

from collections import Counter
from itertools import permutations
from typing import Any, Iterable, Optional, Sequence

FLOAT_DIGITS = 4


def normalize_value(v: Any) -> Any:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, float):
        r = round(v, FLOAT_DIGITS)
        return int(r) if r == int(r) else r
    if isinstance(v, str):
        return v.strip()
    return v


def _norm_rows(rows: Iterable[Sequence[Any]]) -> list[tuple]:
    return [tuple(normalize_value(v) for v in r) for r in rows]


def _same(a: list[tuple], b: list[tuple], ordered: bool) -> bool:
    return a == b if ordered else Counter(a) == Counter(b)


def results_match(pred_rows: Sequence[Sequence[Any]], gold_rows: Sequence[Sequence[Any]],
                  ordered: bool = False, allow_extra_columns: bool = False) -> bool:
    """Reference implementation. Exercise 5 asks you to write your own in mine.py."""
    pred, gold = _norm_rows(pred_rows), _norm_rows(gold_rows)
    if len(pred) != len(gold):
        return False
    if not gold:
        return True  # both empty
    pw, gw = len(pred[0]), len(gold[0])
    if pw < gw or (pw > gw and not allow_extra_columns):
        return False
    if pw > 8:  # too many permutations to try: compare as-is
        return _same([r[:gw] for r in pred], gold, ordered)
    for cols in permutations(range(pw), gw):
        proj = [tuple(r[i] for i in cols) for r in pred]
        if _same(proj, gold, ordered):
            return True
    return False


def summarize(rows: list[dict], key: str = "category") -> dict[str, tuple[int, int]]:
    """{category: (correct, total)} from eval rows with a boolean 'correct'."""
    out: dict[str, list[int]] = {}
    for r in rows:
        c = out.setdefault(r.get(key) or "-", [0, 0])
        c[0] += 1 if r.get("correct") else 0
        c[1] += 1
    return {k: (v[0], v[1]) for k, v in sorted(out.items())}


def mismatch_hint(pred_rows: Optional[Sequence], gold_rows: Sequence) -> str:
    """A short human hint about why two results differ."""
    if pred_rows is None:
        return "no result"
    if len(pred_rows) != len(gold_rows):
        return f"{len(pred_rows)} rows, expected {len(gold_rows)}"
    if pred_rows and gold_rows and len(pred_rows[0]) != len(gold_rows[0]):
        return f"{len(pred_rows[0])} columns, expected {len(gold_rows[0])}"
    return "same shape, different values"

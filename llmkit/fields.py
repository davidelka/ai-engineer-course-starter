"""Field-level scoring of extracted objects (lesson 21).

Reference implementation. Lab 21 exercise 2 asks you to write field_accuracy yourself in
labs/21-multimodal/mine.py; the tests there check yours against this behavior.

"Accuracy" of an extraction is not one number: a receipt with the right total and a wrong
VAT is useful, the reverse is not. So we score each field separately, after normalizing the
things that are not errors ("345.40", "₪345.40" and 345.4 are the same amount).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                      "nov", "dec"], 1)}
_CURRENCY = re.compile(r"(₪|\$|€|£|\bnis\b|\bils\b|\busd\b|\beur\b|\bgbp\b)", re.I)


def _text(v: Any) -> str:
    s = " ".join(str(v).split()).casefold()
    return s.strip(" .,:;!?\"'")


def normalize_money(v: Any) -> Any:
    """345.4, "345.40", "₪ 345.40", "NIS 1,345.40", "1.345,40"? (no: European decimal
    commas are NOT handled; a comma is a thousands separator) -> a float with 2 decimals."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = _CURRENCY.sub("", str(v)).replace(" ", "").replace(",", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return _text(v)


def normalize_date(v: Any) -> Any:
    """'2026-10-14', '14/10/2026', '14.10.2026', '14-10-2026' (day first, as in Israel),
    'Oct 14, 2026', '14 October 2026' -> '2026-10-14'. Anything else: normalized text."""
    if v is None:
        return None
    s = str(v).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", s)
        if m:
            d, mo, y = map(int, m.groups())
        else:
            m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.? (\d{1,2}),? (\d{4})", s) or None
            m2 = re.fullmatch(r"(\d{1,2}) ([A-Za-z]{3})[a-z]*\.?,? (\d{4})", s)
            if m and m.group(1).lower() in MONTHS:
                mo, d, y = MONTHS[m.group(1).lower()], int(m.group(2)), int(m.group(3))
            elif m2 and m2.group(2).lower() in MONTHS:
                d, mo, y = int(m2.group(1)), MONTHS[m2.group(2).lower()], int(m2.group(3))
            else:
                return _text(s)
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return _text(s)


def normalize_int(v: Any) -> Any:
    if v is None or isinstance(v, bool):
        return v
    try:
        return int(round(float(str(v).replace(",", ""))))
    except ValueError:
        return _text(v)


def normalize_field(v: Any, kind: str) -> Any:
    """kind: money | date | int | text | code | list."""
    if kind == "money":
        return normalize_money(v)
    if kind == "date":
        return normalize_date(v)
    if kind == "int":
        return normalize_int(v)
    if kind == "code":
        return None if v is None else str(v).strip()
    if kind == "list":
        return None if v is None else sorted(_text(x) for x in v)
    return None if v is None else _text(v)  # text


@dataclass
class FieldReport:
    correct: dict[str, bool] = field(default_factory=dict)
    mismatches: list[tuple[str, Any, Any]] = field(default_factory=list)  # (field, predicted, gold)

    @property
    def accuracy(self) -> float:
        return sum(self.correct.values()) / len(self.correct) if self.correct else 0.0


def field_accuracy(pred: Optional[Any], gold: dict, kinds: dict[str, str]) -> FieldReport:
    """Compare a predicted object with the gold answer, field by field.

    pred: a dict, a Pydantic model (model_dump() is used), or None (the extraction failed:
    every field counts as wrong). Only the fields in `kinds` are scored, in that order.
    A field is correct when normalize_field(pred, kind) == normalize_field(gold, kind);
    a missing key in pred counts as None (so it is correct only when gold is None too).
    Mismatches keep the ORIGINAL (unnormalized) predicted and gold values.
    """
    if pred is not None and hasattr(pred, "model_dump"):
        pred = pred.model_dump()
    rep = FieldReport()
    for name, kind in kinds.items():
        g = gold.get(name)
        p = None if pred is None else pred.get(name)
        ok = pred is not None and normalize_field(p, kind) == normalize_field(g, kind)
        rep.correct[name] = ok
        if not ok:
            rep.mismatches.append((name, p, g))
    return rep

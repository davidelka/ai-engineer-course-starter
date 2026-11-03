"""Your code for lesson 21. Each part is checked by tests in ./tests.

Reference versions: llmkit/fields.py (exercise 2), llmkit/media.py (exercise 3),
voicekit/text.py (exercise 5). Try not to peek before your tests pass.

    python -m pytest -q labs/21-multimodal/tests
"""

from __future__ import annotations

import math  # noqa: F401  (exercise 3)
import re  # noqa: F401
import unicodedata  # noqa: F401  (exercise 5)
from datetime import datetime  # noqa: F401  (exercise 2)
from typing import Any, Optional

from llmkit.fields import FieldReport  # noqa: F401  (exercise 2 returns one of these)
from voicekit.text import ErrorRate  # noqa: F401  (exercise 5 returns one of these)


# ------------------------------------------------------------------ exercise 2
def normalize_field(value: Any, kind: str) -> Any:
    """Normalize one extracted value so that formatting differences are not counted as errors.

    kind == "money": None stays None. int/float -> round(float(v), 2). A string: remove the
        currency marks ₪ $ € £ and the words NIS ILS USD EUR GBP (any case), remove spaces and
        commas (a comma is a thousands separator), then round(float(...), 2).
        "₪ 1,345.40" -> 1345.4, "NIS 52.69" -> 52.69. If float() still fails: the text rule.
    kind == "date": None stays None. Return "yyyy-mm-dd" for "2026-10-14", "14/10/2026",
        "14.10.2026", "14-10-2026" (DAY first, as on Israeli receipts), "Oct 14, 2026",
        "October 14 2026", "14 Oct 2026". An impossible date ("2026-14-10") or any other
        string: the text rule.
    kind == "int": None stays None; int(round(float(str(v).replace(",", "")))); on failure the text rule.
    kind == "code": None stays None; str(v).strip() (case matters: "SPW-4013" != "spw-4013").
    kind == "list": None stays None; sorted list of the text rule applied to each item
        (so order and case do not matter).
    kind == "text" (and the "text rule" above): None stays None; collapse whitespace,
        casefold(), then strip these characters from both ends: space . , : ; ! ? " '
    Booleans are returned unchanged for money and int.
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement normalize_field")


def field_accuracy(pred: Optional[Any], gold: dict, kinds: dict[str, str]) -> FieldReport:
    """Score a predicted object against the gold answer, field by field.

    pred: a dict, a Pydantic model (use pred.model_dump()), or None (extraction failed).
    For each (name, kind) in kinds, in order:
        g = gold.get(name); p = None if pred is None else pred.get(name)
        ok = pred is not None and normalize_field(p, kind) == normalize_field(g, kind)
        report.correct[name] = ok
        if not ok: report.mismatches.append((name, p, g))   # original values, not normalized
    Return the FieldReport (its .accuracy property is the share of correct fields).
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement field_accuracy")


# ------------------------------------------------------------------ exercise 3
def image_tokens(provider: str, model: str, width: int, height: int, detail: Optional[str] = None) -> int:
    """Input tokens one image costs, per the providers' published rules (November 2026).

    anthropic (any model): tier = "high" when the model's version is 4.7 or later
        ("claude-haiku-5-5" -> (5, 5) >= (4, 7)) or the name has no version (e.g. "mock-model");
        else "standard" ("claude-haiku-4-5"). Limits: high = long edge 2576 px and 4784
        tokens; standard = 1568 px and 1568 tokens. tokens(w, h) = ceil(w/28) * ceil(h/28).
        Resize: if long edge <= limit AND tokens(w, h) <= token limit, keep (w, h).
        Otherwise new_long = (min(long, limit) // 28) * 28, and repeat:
            new_short = max(1, round(short * new_long / long))
            stop if tokens(new_long, new_short) <= token limit (or new_long <= 28)
            else new_long -= 28
        Return tokens of the resized image (keep the orientation: portrait stays portrait).
    openai, patch models: model starting with "gpt-5.4" (gpt-5.4, gpt-5.4-mini, gpt-5.4-nano).
        detail "auto" means "high". (max_dim, budget): low = (2048, 6144), high = (2048, 2500),
        original = (6000, 10000).
        1. fit: s = min(1, max_dim / w, max_dim / h); if s < 1: w, h = int(w * s), int(h * s)
        2. patches = ceil(w/32) * ceil(h/32)
        3. if patches > budget: s = sqrt(budget * 32 * 32 / (w * h)); loop: nw, nh = int(w * s),
           int(h * s); if ceil(nw/32) * ceil(nh/32) <= budget: break; else s *= 0.99.
           Then patches = ceil(nw/32) * ceil(nh/32).
        4. tokens = ceil(patches * 1.2)
    openai, tile model "gpt-4o": detail "low" -> 85. Otherwise fit within 2048 x 2048 (as in
        step 1); if min(w, h) > 768: s = 768 / min(w, h); w, h = int(w * s), int(h * s);
        tokens = 85 + 170 * ceil(w/512) * ceil(h/512).
    gemini, model "gemini-3..." or later: detail (media resolution) low 280, medium 560,
        high 1120, ultra_high 2240; None or anything else -> 1120. The size does not matter.
    gemini, model "gemini-2...": 258 if w <= 384 and h <= 384. Otherwise
        crop = max(256, min(768, floor(min(w, h) / 1.5))); tokens = 258 * ceil(w/crop) * ceil(h/crop).
    Anything else: raise ValueError.
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement image_tokens")


# ------------------------------------------------------------------ exercise 5
def normalize_hebrew(text: str, *, finals: bool = True) -> str:
    """Normalize Hebrew (and mixed Hebrew/English) text before computing WER. In this order:
      1. unicodedata.normalize("NFC", text)
      2. remove the invisible direction marks U+200E, U+200F, U+202A..U+202E, U+2066..U+2069
      3. remove niqqud and cantillation: U+0591..U+05BD, U+05BF, U+05C1, U+05C2, U+05C4, U+05C5, U+05C7
      4. replace maqaf (U+05BE) and "-" with a space          ("בית־ספר" -> "בית ספר")
      5. remove geresh U+05F3, gershayim U+05F4, ' and " when they sit BETWEEN two word
         characters (\\w on both sides): 'צה"ל' -> "צהל", "ג'ירפה" -> "גירפה".
         Then every remaining character whose unicodedata.category starts with "P" becomes a space.
      6. if finals: ך->כ ם->מ ן->נ ף->פ ץ->צ
      7. lowercase, and collapse all whitespace to single spaces (strip the ends)
    "שָׁלוֹם, עוֹלָם!" -> "שלומ עולמ". Digits stay as they are.
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement normalize_hebrew")


def wer(reference: str, hypothesis: str, *, normalize=normalize_hebrew) -> ErrorRate:
    """Word error rate with a word-level Levenshtein alignment.

    If normalize is not None, apply it to both texts first. Split on whitespace.
    Fill the (n+1) x (m+1) edit-distance table (substitution, deletion, insertion all cost 1).
    Backtrack from (n, m) to build ops, preferring in this order when costs tie:
      diagonal ("ok" if the words are equal else "sub"), then "del" (a reference word the
      hypothesis lacks: ("del", ref_word, "")), then "ins" (("ins", "", hyp_word)).
    Return ErrorRate(rate, substitutions, deletions, insertions, ref_len, hyp_len, ops) with
    ops in reading order and rate = (S + D + I) / ref_len. Empty reference: rate 0.0 if the
    hypothesis is empty too, else 1.0. The rate can exceed 1.0.
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement wer")

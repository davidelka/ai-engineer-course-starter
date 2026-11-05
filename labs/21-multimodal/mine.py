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

    None always stays None. By kind:
      "money": a float rounded to 2 places; strings may carry ₪ $ € £, the words NIS ILS USD EUR
               GBP (any case), spaces and thousands commas: "₪ 1,345.40" -> 1345.4.
      "date":  "yyyy-mm-dd" from "2026-10-14", "14/10/2026", "14.10.2026", "14-10-2026" (DAY
               first, as on Israeli receipts), "Oct 14, 2026", "October 14 2026", "14 Oct 2026".
      "int":   an int, rounded; thousands commas allowed: "1,200" -> 1200, 4.6 -> 5.
      "code":  the string with the ends stripped; case matters ("SPW-4013" != "spw-4013").
      "list":  a sorted list of the items, each normalized as text (order and case do not matter).
      "text":  whitespace collapsed, casefolded, and the characters  space . , : ; ! ? " '
               stripped from both ends: "  Cafe   NOIR. " -> "cafe noir".
    A money/int/date value that cannot be parsed (including an impossible date like
    "2026-14-10") falls back to the text rule. Booleans are returned unchanged for money and int.

    Stuck? HINTS.md -> normalize_field
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement normalize_field")


def field_accuracy(pred: Optional[Any], gold: dict, kinds: dict[str, str]) -> FieldReport:
    """Score a predicted object against the gold answer, field by field.

    pred: a dict, a Pydantic model, or None (extraction failed). gold: dict. kinds: {field: kind}.
    Returns a FieldReport: report.correct[name] -> bool for every field of `kinds`, in the order of
    `kinds` (a field is correct when both values normalize equal with normalize_field; a field
    missing from pred counts as None; everything is wrong when pred is None), and
    report.mismatches = [(name, pred_value, gold_value), ...] with the ORIGINAL, not normalized,
    values. report.accuracy is computed by FieldReport.

    Stuck? HINTS.md -> field_accuracy
    """
    # TODO(ex2)
    raise NotImplementedError("exercise 2: implement field_accuracy")


# ------------------------------------------------------------------ exercise 3
def image_tokens(provider: str, model: str, width: int, height: int, detail: Optional[str] = None) -> int:
    """Input tokens one image costs, per the providers' published rules (November 2026).

    Returns an int. detail is provider-specific (OpenAI detail, Gemini media resolution).
      anthropic (any model): tokens = ceil(w/28) * ceil(h/28) after downscaling, keeping the
          aspect ratio and orientation, to fit the tier's limits. Tier "high" (long edge 2576 px,
          4784 tokens) for models of version 4.7 or later ("claude-haiku-5-5") or with no version
          ("mock-model"); else "standard" (1568 px, 1568 tokens), e.g. "claude-haiku-4-5".
      openai patch models (name starts with "gpt-5.4"): 32 px patches, tokens = ceil(patches * 1.2).
          detail "auto" means "high". (max_dim, patch budget): low (2048, 6144), high (2048, 2500),
          original (6000, 10000); the image is fitted in max_dim, then shrunk to the budget.
      openai tile model "gpt-4o": "low" -> 85. Otherwise fit in 2048 x 2048, shrink so the short
          side is at most 768, tokens = 85 + 170 * (number of 512 px tiles).
      gemini "gemini-3..." or later: low 280, medium 560, high 1120, ultra_high 2240; None or
          anything else 1120; the size does not matter.
      gemini "gemini-2...": 258 when both sides <= 384; otherwise 258 per crop tile, crop side =
          min(w, h) / 1.5 rounded down and clamped to [256, 768].
    Anything else: ValueError.
    A test compares you with the reference over many sizes, so the exact resize rounding
    matters: if you are off by a little, the details are in HINTS.md level 3.

    Stuck? HINTS.md -> image_tokens
    """
    # TODO(ex3)
    raise NotImplementedError("exercise 3: implement image_tokens")


# ------------------------------------------------------------------ exercise 5
def normalize_hebrew(text: str, *, finals: bool = True) -> str:
    """Normalize Hebrew (and mixed Hebrew/English) text before computing WER.

    Returns the text in NFC form, with:
      - no invisible direction marks (U+200E, U+200F, U+202A..U+202E, U+2066..U+2069);
      - no niqqud or cantillation (U+0591..U+05BD, U+05BF, U+05C1, U+05C2, U+05C4, U+05C5, U+05C7);
      - maqaf (U+05BE) and "-" as a space: "בית־ספר" -> "בית ספר";
      - geresh U+05F3, gershayim U+05F4, ' and " deleted when between two word characters:
        'צה"ל' -> "צהל", "ג'ירפה" -> "גירפה"; any other punctuation (Unicode category P*) -> space;
      - if finals: final letters replaced by regular ones (ך->כ ם->מ ן->נ ף->פ ץ->צ);
      - lowercase, single spaces, no spaces at the ends. Digits stay as they are.
    "שָׁלוֹם, עוֹלָם!" -> "שלומ עולמ".

    Stuck? HINTS.md -> normalize_hebrew
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement normalize_hebrew")


def wer(reference: str, hypothesis: str, *, normalize=normalize_hebrew) -> ErrorRate:
    """Word error rate with a word-level Levenshtein alignment.

    Both texts go through `normalize` first unless it is None; words are split on whitespace.
    Returns ErrorRate(rate, substitutions, deletions, insertions, ref_len, hyp_len, ops):
      ops in reading order: ("ok", w, w), ("sub", ref_w, hyp_w), ("del", ref_w, ""), ("ins", "", hyp_w);
      substitution, deletion and insertion each cost 1; among equally cheap alignments prefer
      ok/sub, then del, then ins (from the end of the texts backwards);
      rate = (S + D + I) / ref_len, and can exceed 1.0. Empty reference: 0.0 if the hypothesis
      is empty too, else 1.0.

    Stuck? HINTS.md -> wer
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement wer")

"""Text normalization and error rates for speech evaluation (lesson 21).

Reference implementations. Lab 21 exercise 5 asks you to write normalize_hebrew and wer
yourself in labs/21-multimodal/mine.py; the tests there check yours against this behavior.

Why normalize before WER: the score should count words the recognizer got WRONG, not
spelling conventions. "שָׁלוֹם," and "שלום" are the same word; a transcript with niqqud or
a comma is not a worse transcript. What is normalized away must be written down, because
it changes the numbers: two papers that normalize differently report different WERs for
the same output.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Hebrew points and cantillation marks (U+0591-U+05C7) that are not letters or punctuation.
_NIQQUD = re.compile("[\u0591-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7]")
_BIDI = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069]")  # invisible direction marks
FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})


def normalize_hebrew(text: str, *, finals: bool = True) -> str:
    """Normalize Hebrew (and mixed Hebrew/English) text for WER.

    In this order:
      1. Unicode NFC.
      2. remove invisible direction marks (U+200E, U+200F, U+202A-U+202E, U+2066-U+2069);
      3. remove niqqud and cantillation (U+0591-U+05BD, U+05BF, U+05C1, U+05C2, U+05C4, U+05C5, U+05C7);
      4. maqaf (U+05BE, the Hebrew hyphen) and "-" become a space ("בית-ספר" -> "בית ספר");
      5. geresh/gershayim (U+05F3, U+05F4) and ASCII ' " are removed INSIDE words
         ("צה"ל" -> "צהל", "ג'ירפה" -> "גירפה"); every other punctuation character
         (Unicode category P*) becomes a space;
      6. finals=True: final letters become regular letters (ך ם ן ף ץ -> כ מ נ פ צ), so a
         recognizer that writes the wrong final form is not counted as a word error;
      7. lowercase (for Latin words) and collapse whitespace.
    Digits are kept as they are: "3" and "שלוש" stay different (number normalization is a
    separate decision; see the lesson).
    """
    t = unicodedata.normalize("NFC", text)
    t = _BIDI.sub("", t)
    t = _NIQQUD.sub("", t)
    t = t.replace("\u05BE", " ").replace("-", " ")
    t = re.sub("(?<=\\w)[\u05F3\u05F4'\"](?=\\w)", "", t)
    t = "".join(" " if unicodedata.category(c).startswith("P") else c for c in t)
    if finals:
        t = t.translate(FINALS)
    return " ".join(t.lower().split())


@dataclass
class ErrorRate:
    """Edit distance result. rate = (substitutions + deletions + insertions) / ref_len."""

    rate: float
    substitutions: int
    deletions: int
    insertions: int
    ref_len: int
    hyp_len: int
    ops: list[tuple[str, str, str]] = field(default_factory=list)  # (op, ref_token, hyp_token)

    @property
    def hits(self) -> int:
        return self.ref_len - self.substitutions - self.deletions


def align(ref: list[str], hyp: list[str]) -> list[tuple[str, str, str]]:
    """Levenshtein alignment of two token lists. Ops in order: ("ok"|"sub"|"del"|"ins",
    ref_token, hyp_token), "" for the missing side. When several alignments have the same
    cost, backtracking prefers the diagonal (ok/sub), then deletion, then insertion."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j - 1] + cost, d[i - 1][j] + 1, d[i][j - 1] + 1)
    ops: list[tuple[str, str, str]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1):
            ops.append(("ok" if ref[i - 1] == hyp[j - 1] else "sub", ref[i - 1], hyp[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            ops.append(("del", ref[i - 1], ""))
            i -= 1
        else:
            ops.append(("ins", "", hyp[j - 1]))
            j -= 1
    return ops[::-1]


def _rate(ref: list[str], hyp: list[str]) -> ErrorRate:
    ops = align(ref, hyp)
    s = sum(o[0] == "sub" for o in ops)
    dl = sum(o[0] == "del" for o in ops)
    ins = sum(o[0] == "ins" for o in ops)
    if not ref:
        rate = 0.0 if not hyp else 1.0
    else:
        rate = (s + dl + ins) / len(ref)
    return ErrorRate(rate, s, dl, ins, len(ref), len(hyp), ops)


def wer(reference: str, hypothesis: str, *, normalize=normalize_hebrew) -> ErrorRate:
    """Word error rate. Both texts go through `normalize` (None = only split on whitespace).
    An empty reference gives 0.0 for an empty hypothesis and 1.0 otherwise. WER can be
    above 1.0 (many insertions)."""
    if normalize:
        reference, hypothesis = normalize(reference), normalize(hypothesis)
    return _rate(reference.split(), hypothesis.split())


def cer(reference: str, hypothesis: str, *, normalize=normalize_hebrew) -> ErrorRate:
    """Character error rate (spaces removed). Useful for Hebrew, where prefixes are glued to
    words (ו, ה, ב, ל, מ, ש, כ): "ובבית" vs "ו בבית" is one or two WORD errors but a tiny
    character error."""
    if normalize:
        reference, hypothesis = normalize(reference), normalize(hypothesis)
    return _rate(list(reference.replace(" ", "")), list(hypothesis.replace(" ", "")))

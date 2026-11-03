"""PII redaction before a prompt leaves the company: emails, Israeli phones, Israeli IDs.

Reference implementation. Exercise 4 of lab 25 asks you to write your own in mine.py.

- Placeholders are numbered per type in order of first appearance: [EMAIL_1],
  [PHONE_IL_1], [IL_ID_1]. The same value always gets the same placeholder, so the
  model can still reason ("[EMAIL_1] asked to give [EMAIL_2] access").
- Findings carry offsets and a salted fingerprint, never the raw value: the audit
  log must not become the place where all the PII is collected.
- An Israeli ID is 9 digits WITH a valid check digit. Nine digits without one are
  left alone: they are much more likely an order or invoice number. That check is
  what keeps the false-positive rate tolerable.
- Types are matched in priority order (email, phone_il, il_id). A later type never
  takes a span that overlaps an earlier match. This matters: "035550199" is both a
  Tel Aviv landline without separators and a 9-digit number; as a phone it wins.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Optional +972 / 972 (replaces the leading 0) or a leading 0; then a mobile prefix 5X,
# a 7X (VoIP) prefix, or a one-digit landline area code (2,3,4,8,9); then 7 digits as
# 3+4. A single "-" or " " is allowed between the groups.
PHONE_IL_RE = re.compile(r"(?<![\d+])(?:\+972[-\s]?|972[-\s]?|0)(?:5\d|7\d|[23489])[-\s]?\d{3}[-\s]?\d{4}(?!\d)")
IL_ID_RE = re.compile(r"(?<!\d)\d{9}(?!\d)")

TYPES = ("email", "phone_il", "il_id")
PLACEHOLDER_PREFIX = {"email": "EMAIL", "phone_il": "PHONE_IL", "il_id": "IL_ID"}


@dataclass
class Finding:
    type: str  # email | phone_il | il_id
    placeholder: str  # e.g. "[EMAIL_1]"
    start: int  # offsets in the ORIGINAL text
    end: int
    fingerprint: str  # sha256(salt + normalized value)[:12], for correlation without the value


@dataclass
class Redaction:
    text: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in self.findings:
            out[f.type] = out.get(f.type, 0) + 1
        return out


def israeli_id_valid(digits: str) -> bool:
    """Israeli ID check digit: weights 1,2,1,2,... ; a two-digit product counts as the sum of its digits."""
    if not re.fullmatch(r"\d{9}", digits):
        return False
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def normalize(kind: str, value: str) -> str:
    if kind == "email":
        return value.lower()
    if kind == "phone_il":
        digits = re.sub(r"\D", "", value)
        return "0" + digits[3:] if digits.startswith("972") else digits
    return value


def _matches(kind: str, text: str) -> Iterable[tuple[int, int]]:
    if kind == "email":
        yield from (m.span() for m in EMAIL_RE.finditer(text))
    elif kind == "phone_il":
        yield from (m.span() for m in PHONE_IL_RE.finditer(text))
    elif kind == "il_id":
        yield from (m.span() for m in IL_ID_RE.finditer(text) if israeli_id_valid(m.group()))


def redact(text: str, types: Iterable[str] = TYPES, salt: str = "",
           known: Optional[dict] = None) -> Redaction:
    """Replace PII of the given types with placeholders.

    known: optional dict {(type, normalized_value): placeholder} shared across calls,
    so several messages of one request use one numbering. It is updated in place.
    """
    types = list(types)
    for t in types:
        if t not in TYPES:
            raise ValueError(f"unknown PII type {t!r}; choose from {TYPES}")
    known = {} if known is None else known
    taken: list[tuple[int, int, str]] = []
    for kind in TYPES:  # priority order, regardless of the order the caller gave
        if kind not in types:
            continue
        for start, end in _matches(kind, text):
            if any(start < e and s < end for s, e, _ in taken):
                continue
            taken.append((start, end, kind))
    taken.sort()
    findings: list[Finding] = []
    for start, end, kind in taken:
        norm = normalize(kind, text[start:end])
        ph = known.get((kind, norm))
        if ph is None:
            n = sum(1 for (k, _), _p in known.items() if k == kind) + 1
            ph = f"[{PLACEHOLDER_PREFIX[kind]}_{n}]"
            known[(kind, norm)] = ph
        fp = hashlib.sha256((salt + norm).encode()).hexdigest()[:12]
        findings.append(Finding(kind, ph, start, end, fp))
    out, pos = [], 0
    for f in findings:
        out.append(text[pos:f.start])
        out.append(f.placeholder)
        pos = f.end
    out.append(text[pos:])
    return Redaction("".join(out), findings)

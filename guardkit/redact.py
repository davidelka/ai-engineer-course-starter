"""PII redaction for logs (lesson 24, exercise 8). Reference version.

Prompts and answers of an LLM app end up in logs, traces and eval datasets, and they are
full of personal data that users pasted. Redact BEFORE the record is written:

    redact_pii("call 050-1234567 or mail dana@acme.example, ID 000000018")
    -> "call [PHONE] or mail [EMAIL], ID [IL_ID]"

Order matters: Israeli ID numbers first (9 digits with a valid check digit), then emails,
then phone numbers. A 9-digit number that fails the checksum is NOT an ID (it may be an
order number) and is left alone.

RedactingFilter plugs the same function into Python's logging module.
For production, look at Microsoft Presidio (pip install presidio-analyzer): NER plus
regex recognizers, including an Israeli ID recognizer, with confidence scores.
"""

from __future__ import annotations

import logging
import re

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Israeli numbers: +972 or 0, then a 1-digit area code (2,3,4,8,9), or 5x / 7x, then 7 digits,
# with optional '-' or ' ' separators.
PHONE_RE = re.compile(r"(?<![\d+])(?:\+972[-\s]?|0)(?:[23489]|5\d|7\d)[-\s]?\d{3}[-\s]?\d{4}(?!\d)")
ID_CANDIDATE_RE = re.compile(r"(?<![\d-])(\d{8})-?(\d)(?![\d-])")
SECRET_RE = re.compile(r"\b(?:sk-ant-[\w-]{10,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})\b")


def is_valid_israeli_id(value: str) -> bool:
    """Israeli ID (teudat zehut) check digit. Accepts up to 9 digits (left-padded with zeros)
    and an optional '-' before the last digit. Weights 1,2,1,2,...; a product above 9 has
    its digits summed (equivalently, minus 9); the total must divide by 10.
    All zeros is rejected."""
    s = value.strip().replace("-", "")
    if not s.isdigit() or not 1 <= len(s) <= 9:
        return False
    s = s.zfill(9)
    if set(s) == {"0"}:
        return False
    total = 0
    for i, ch in enumerate(s):
        n = int(ch) * (1 if i % 2 == 0 else 2)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def redact_pii(text: str) -> str:
    def _id(m: re.Match) -> str:
        return "[IL_ID]" if is_valid_israeli_id(m.group(1) + m.group(2)) else m.group(0)

    text = ID_CANDIDATE_RE.sub(_id, text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return text


def redact_secrets(text: str) -> str:
    return SECRET_RE.sub("[SECRET]", text)


class RedactingFilter(logging.Filter):
    """logging.Filter that redacts the formatted message (and drops args) of every record."""

    def __init__(self, redact=redact_pii):
        super().__init__()
        self.redact = redact

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        record.msg = redact_secrets(self.redact(msg))
        record.args = ()
        return True

"""What may leave the machine, in what form, and the record of everything that did.

Three layers, in this order, before any cloud call (pss.answer uses them; the web UI and
`pss ask --cloud --dry-run` show the result BEFORE anything is sent):

1. withhold:  sources whose file matches cloud.never_send (default: health/ and finance/) are
              removed from the prompt. The answer is built from the remaining sources, and the
              user is told how many were withheld. This is a folder rule, not a guess about
              content, so it is predictable.
2. redact:    every remaining byte (system prompt, sources, question) goes through
              redact_for_cloud: Israeli ID numbers (with check digit), emails and phone numbers
              (guardkit, lesson 24), plus payment cards (Luhn check), Israeli IBANs and bank
              account numbers written as branch-account. Regexes miss things (a name, an
              address), which is exactly why layer 1 exists.
3. log first: one JSON line per call in <index>/egress.jsonl, written BEFORE the request is
              sent, with the exact redacted payload, its sha256, the files it came from and
              the redaction counts. A second line records the outcome (ok/error, tokens, cost).
              `pss egress` prints it; the web UI shows a counter.

Nothing here runs unless cloud.enabled is true in the config AND the call asks for the cloud
(`--cloud`, or the cloud toggle in the UI). The local path never imports a cloud client.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from guardkit.redact import redact_pii

IBAN_RE = re.compile(r"\bIL\d{2}(?:[ -]?\d{4}){4}[ -]?\d{3}\b", re.I)
CARD_RE = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
BANK_ACCOUNT_RE = re.compile(r"(?<![\d-])\d{2}-\d{3}-\d{4,9}(?![\d-])")
LABELS = ("IBAN", "CARD", "IL_ID", "EMAIL", "PHONE", "BANK_ACCOUNT")


def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def redact_for_cloud(text: str) -> tuple[str, dict[str, int]]:
    """Reference implementation (see mine.redact_for_cloud for the contract)."""
    counts = {k: 0 for k in LABELS}

    def sub_iban(m: re.Match) -> str:
        counts["IBAN"] += 1
        return "[IBAN]"

    def sub_card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and luhn_ok(digits):
            counts["CARD"] += 1
            return "[CARD]"
        return m.group(0)

    text = IBAN_RE.sub(sub_iban, text)
    text = CARD_RE.sub(sub_card, text)
    before = {k: text.count(f"[{k}]") for k in ("IL_ID", "EMAIL", "PHONE")}
    text = redact_pii(text)
    for k in ("IL_ID", "EMAIL", "PHONE"):
        counts[k] += text.count(f"[{k}]") - before[k]

    def sub_acct(m: re.Match) -> str:
        counts["BANK_ACCOUNT"] += 1
        return "[BANK_ACCOUNT]"

    text = BANK_ACCOUNT_RE.sub(sub_acct, text)
    return text, {k: v for k, v in counts.items() if v}


def protected(file_id: str, never_send: list[str]) -> Optional[str]:
    """The never_send pattern that protects this file, or None (same semantics as excludes)."""
    from . import hooks

    return hooks.get("is_excluded")(file_id, never_send)


class PrivacyError(RuntimeError):
    pass


@dataclass
class EgressRecord:
    id: str
    ts: float
    provider: str
    model: str
    question: str                       # redacted
    files: list[str]
    withheld: list[str]
    redactions: dict[str, int]
    chars: int
    sha256: str
    payload: dict[str, Any] = field(default_factory=dict)   # {"system": ..., "user": ...} exactly as sent


class EgressLog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _append(self, obj: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def before_send(self, rec: EgressRecord) -> None:
        self._append({"event": "send", **rec.__dict__})

    def after_send(self, rec_id: str, *, ok: bool, input_tokens: int = 0, output_tokens: int = 0,
                   cost_usd: float = 0.0, error: str = "") -> None:
        self._append({"event": "result", "id": rec_id, "ts": time.time(), "ok": ok,
                      "input_tokens": input_tokens, "output_tokens": output_tokens,
                      "cost_usd": round(cost_usd, 6), "error": error[:200]})

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    def summary(self) -> dict:
        es = self.entries()
        sends = [e for e in es if e.get("event") == "send"]
        results = [e for e in es if e.get("event") == "result"]
        return {"calls": len(sends), "chars_sent": sum(e.get("chars", 0) for e in sends),
                "files_sent": len({f for e in sends for f in e.get("files", [])}),
                "redactions": sum(sum(e.get("redactions", {}).values()) for e in sends),
                "cost_usd": round(sum(r.get("cost_usd", 0.0) for r in results), 6),
                "last": sends[-1]["ts"] if sends else None}


def make_record(provider: str, model: str, question: str, system: str, user: str, files: list[str],
                withheld: list[str], redactions: dict[str, int]) -> EgressRecord:
    blob = (system + "\n\n" + user).encode("utf-8")
    return EgressRecord(id=uuid.uuid4().hex[:12], ts=time.time(), provider=provider, model=model,
                        question=question, files=files, withheld=withheld, redactions=redactions,
                        chars=len(system) + len(user), sha256=hashlib.sha256(blob).hexdigest(),
                        payload={"system": system, "user": user})

"""The digest: what the owner reads in the WhatsApp group "משרות" three times a day.

Only jobs that are NEW since the previous run (the pipeline filters with the state store),
grouped by tier and then by target category, in Hebrew, with WhatsApp markup (*bold*,
_italic_). Every match line says where to apply and which CV to attach, because that is the
next action. "Other jobs" are listed briefly: the owner asked to still see them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .match import CAT_HE, MODE_HE, REGION_HE
from .models import Job

HE_DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]  # datetime.weekday(): Monday = 0


@dataclass
class Digest:
    slot_key: str
    text: str
    matches: list[Job] = field(default_factory=list)
    maybes: list[Job] = field(default_factory=list)
    others: list[Job] = field(default_factory=list)
    posts_seen: int = 0

    @property
    def empty(self) -> bool:
        return not (self.matches or self.maybes or self.others)

    @property
    def job_count(self) -> int:
        return len(self.matches) + len(self.maybes) + len(self.others)


def _where(j: Job) -> str:
    p = j.posting
    parts = [p.location or "מיקום לא צוין"]
    if j.region and j.region not in ("other",):
        parts[0] += f" ({REGION_HE.get(j.region, j.region)})"
    parts.append(MODE_HE.get(p.work_mode, "לא צוין") if p.work_mode else "מתכונת לא צוינה")
    if p.years_required is not None:
        parts.append(f"{p.years_required}+ שנים")
    return " · ".join(parts)


def _head(j: Job) -> str:
    p = j.posting
    return f"*{p.title}*" + (f" · {p.company}" if p.company else "")


def _weakest_reason(j: Job) -> str:
    """The reason that cost the most points: the one line that explains a 'maybe'."""
    import re

    def lost(r: str) -> int:
        m = re.search(r"(\d+)/(\d+)", r)
        return int(m.group(2)) - int(m.group(1)) if m else 0

    rs = [r for r in j.reasons if "/" in r] or j.reasons
    if not rs:
        return ""
    worst = max(rs, key=lost)
    return re.sub(r"^\[[^\]]+\]\s*", "", worst)


def format_slot(slot_key: str) -> str:
    dt = datetime.fromisoformat(slot_key)
    return f"{dt:%H:%M} · יום {HE_DAYS[dt.weekday()]} {dt.day}.{dt.month}"


def build_digest(slot_key: str, jobs: list[Job], *, category_order: Optional[list[str]] = None,
                 posts_seen: int = 0, drafted: Optional[set[str]] = None, show_others: bool = True) -> Digest:
    """jobs: the NEW, de-duplicated, scored jobs of this run. drafted: fingerprints that got a Gmail draft."""
    drafted = drafted or set()
    order = list(category_order or []) + [c for c in CAT_HE if c not in (category_order or [])]
    rank = {c: i for i, c in enumerate(order)}
    key = lambda j: (rank.get(j.category or j.posting.primary_category or "other", 99), -j.score, j.posting.title)
    matches = sorted([j for j in jobs if j.tier == "match"], key=key)
    maybes = sorted([j for j in jobs if j.tier == "maybe"], key=key)
    others = sorted([j for j in jobs if j.tier == "skip"], key=key)

    lines = [f"*משרות חדשות · {format_slot(slot_key)}*"]
    if not (matches or maybes or others):
        lines.append("אין משרות חדשות מאז הריצה הקודמת.")
        return Digest(slot_key, "\n".join(lines), posts_seen=posts_seen)
    lines.append(f"{len(matches)} התאמות, {len(maybes)} אולי, {len(others)} אחרות (מתוך {posts_seen} פוסטים חדשים)")

    if matches:
        lines += ["", "*✅ התאמות*"]
        current, n = None, 0
        for j in matches:
            if j.category != current:
                current = j.category
                lines.append(f"_{CAT_HE.get(current, current)}_")
            n += 1
            lines.append(f"{n}. {_head(j)}{' ⚠️' if j.suspicious else ''}")
            lines.append(f"   {_where(j)} · ציון {j.score}")
            act = []
            if j.posting.apply:
                act.append(f"להגשה: {j.posting.apply}")
            if j.cv:
                act.append(f"קו\"ח: {j.cv}")
            if j.fingerprint in drafted:
                act.append("טיוטה מחכה ב-Gmail")
            if act:
                lines.append("   " + " · ".join(act))
    if maybes:
        lines += ["", "*🤔 אולי מעניין*"]
        for j in maybes:
            why = _weakest_reason(j)
            lines.append(f"- {_head(j)}{' ⚠️' if j.suspicious else ''} · {_where(j)} · ציון {j.score}"
                         + (f"\n  למה רק אולי: {why}" if why else "")
                         + (f"\n  להגשה: {j.posting.apply}" if j.posting.apply else ""))
    if others and show_others:
        lines += ["", "*שאר המשרות (לידיעה)*"]
        for j in others:
            lines.append(f"- {j.posting.title}" + (f" · {j.posting.company}" if j.posting.company else "")
                         + (f" · {j.posting.location}" if j.posting.location else ""))
    if any(j.suspicious for j in matches + maybes):
        lines += ["", "⚠️ = בפוסט נמצא טקסט שמנסה להפעיל מערכת AI. בדוק את הפרטים מול הפוסט המקורי."]
    return Digest(slot_key, "\n".join(lines), matches, maybes, others, posts_seen)

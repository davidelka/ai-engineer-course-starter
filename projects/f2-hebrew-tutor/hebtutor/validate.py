"""Reference version of milestone 4 (mine.validate_assessment): code checks the model's output.

llmkit.structured guarantees the SHAPE of the Assessment. It cannot guarantee that the
correction quotes words the student actually said, that the Arabic explanation is Arabic and
short, that the reply is Hebrew, or that the model did not lower a safety flag the input
screen raised. Those are checked here, and every change is reported as a Finding so the eval
and the traces can count them.
"""

from __future__ import annotations

import re

from voicekit.text import normalize_hebrew

from .content import ARB, HEB, arabic_share, share
from .models import Assessment, Finding
from .prompts import LEVEL_LIMITS
from .rules import EXPLAIN_AR

MAX_EXPLANATION = 160
MAX_HELP = 220
FALLBACK_REPLY = {"A1": "סליחה, לא הבנתי. את{ה|} {יכול|יכולה} להגיד שוב?",
                  "A2": "סליחה, לא הבנתי. את{ה|} {יכול|יכולה} להגיד את זה שוב במילים אחרות?",
                  "B1": "סליחה, לא הבנתי עד הסוף. את{ה|} {יכול|יכולה} להסביר שוב במילים אחרות?"}
SEVERITY = ["distress", "unsafe", "personal_info", "injection", "off_topic", "none"]


def cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit]
    return (head[:head.rfind(" ")] if " " in head else head).rstrip() + "…"


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s]


def validate_assessment(a: Assessment, student_text: str, *, level: str = "A1", mode: str = "text",
                        input_flag: str = "none") -> tuple[Assessment, list[Finding]]:
    from .content import render

    a = a.model_copy(deep=True)
    f: list[Finding] = []
    # ---- correction
    c = a.correction
    if c is not None:
        orig, fixed = normalize_hebrew(c.original), normalize_hebrew(c.corrected)
        if not orig or orig not in normalize_hebrew(student_text):
            f.append(Finding("correction_not_grounded", c.original, "block"))
            a.correction = None
        elif orig == fixed:
            f.append(Finding("correction_noop", c.original, "warn"))
            a.correction = None
        elif mode == "voice" and c.error_type == "spelling":
            f.append(Finding("spelling_in_voice", c.original, "info"))
            a.correction = None
        else:
            if arabic_share(c.explanation_ar) < 0.5:
                f.append(Finding("explanation_not_arabic", c.explanation_ar[:40], "warn"))
                c.explanation_ar = EXPLAIN_AR.get(c.error_type, EXPLAIN_AR["other"]).format(fix=c.corrected)
            if len(c.explanation_ar) > MAX_EXPLANATION:
                f.append(Finding("explanation_too_long", str(len(c.explanation_ar)), "warn"))
                c.explanation_ar = cut(c.explanation_ar, MAX_EXPLANATION)
    # ---- reply
    if share(HEB, a.reply_he) < 0.6:
        f.append(Finding("reply_not_hebrew", a.reply_he[:40], "block"))
        a.reply_he = render(FALLBACK_REPLY.get(level, FALLBACK_REPLY["A1"]), "m")
    else:
        lim = LEVEL_LIMITS.get(level, LEVEL_LIMITS["B1"])
        ss = sentences(a.reply_he)
        if len(ss) > lim["sentences"] + 1:
            f.append(Finding("reply_too_long", f"{len(ss)} sentences", "warn"))
            a.reply_he = " ".join(ss[:lim["sentences"] + 1])
    # ---- help
    if a.help_ar is not None:
        if arabic_share(a.help_ar) < 0.5:
            f.append(Finding("help_not_arabic", a.help_ar[:40], "warn"))
            a.help_ar = None
        elif len(a.help_ar) > MAX_HELP:
            f.append(Finding("help_too_long", str(len(a.help_ar)), "warn"))
            a.help_ar = cut(a.help_ar, MAX_HELP)
    # ---- vocabulary
    kept, seen = [], set()
    for v in a.new_vocabulary:
        key = normalize_hebrew(v.he)
        if share(HEB, v.he) < 0.8 or share(ARB, v.ar) < 0.5 or key in seen or len(kept) >= 3:
            f.append(Finding("vocab_dropped", v.he, "info"))
            continue
        seen.add(key)
        kept.append(v)
    a.new_vocabulary = kept
    # ---- safety: the model may raise a flag, never lower the screen's
    if input_flag != "none" and SEVERITY.index(a.safety_flag) > SEVERITY.index(input_flag):
        f.append(Finding("safety_downgrade", f"{input_flag} -> {a.safety_flag}", "block"))
        a.safety_flag = input_flag
    return a, f

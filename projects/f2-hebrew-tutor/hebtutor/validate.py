"""Reference version of milestone 4 (mine.validate_assessment): code checks the model's output.

llmkit.structured guarantees the SHAPE of the Assessment. It cannot guarantee that the
correction quotes words the student actually said, that the Arabic explanation is Arabic and
short, that the reply is Hebrew, or that the model did not lower a safety flag the input
screen raised. Those are checked here, and every change is reported as a Finding so the eval
and the traces can count them.
"""

from __future__ import annotations

import re



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


def validate_assessment(*args, **kwargs):
    """Milestone 5: runs your mine.validate_assessment (see hebtutor/hooks.py)."""
    from .hooks import call
    return call("validate_assessment", *args, **kwargs)

"""Deduplication, at two levels.

1. Post level (before extraction, saves money): the same text is reposted in several
   groups, often with a different emoji or an added line. Character 5-gram shingles and
   Jaccard similarity catch that without any model call.
2. Job level (after extraction): the same role arrives from WhatsApp and from Airtable
   with different wording. A fingerprint of normalized title + company + location finds
   exact repeats; a looser comparison of the same fields finds near-duplicates.

Reference implementations. The project's mine.py asks you to write `job_fingerprint`
and `near_duplicate` yourself (milestone 3).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional


# Words that do not distinguish one role from another.
_TITLE_SYNONYMS = {
    "developer": "eng", "engineer": "eng", "dev": "eng", "programmer": "eng", "מפתח": "eng", "מפתחת": "eng",
    "מהנדס": "eng", "מהנדסת": "eng", "sw": "software", "תוכנה": "software", "backend": "backend",
    "back-end": "backend", "back": "backend", "בקאנד": "backend", "אוטומציה": "automation", "automation": "automation",
    "embedded": "embedded", "אמבדד": "embedded", "sr": "senior", "snr": "senior", "בכיר": "senior", "בכירה": "senior",
    "ולידציה": "validation", "validation": "validation",
}
_DROP_WORDS = {"end", "the", "a", "an", "for", "of", "and", "to", "ל", "ה", "ו", "role", "position", "משרה", "דרוש",
               "דרושה", "דרושים", "דרושות", "hiring", "we're", "looking"}
SENIORITY_WORDS = {"junior", "senior", "lead", "principal", "staff", "mid", "head", "ג'וניור"}
_COMPANY_SUFFIX = re.compile(r"\b(?:ltd|inc|llc|corp|co|group|technologies|technology|tech|israel|il)\b\.?|בע\"?מ", re.I)


def strip_marks(s: str) -> str:
    """Lowercase, drop emojis/punctuation, keep letters (Hebrew and Latin) and digits."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"/(?:ת|ה|ית|ות)\b", "", s)  # Hebrew gender endings: מפתח/ת -> מפתח
    s = "".join(ch if (ch.isalnum() or ch.isspace() or ch in "+#-") else " " for ch in s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_title(title: Optional[str]) -> str:
    """Canonical title tokens, sorted: 'Senior Back-End Developer' == 'Backend Engineer, Senior'."""
    words = []
    for w in strip_marks(title or "").replace("back-end", "backend").replace("back end", "backend").split():
        w = _TITLE_SYNONYMS.get(w, w)
        if w not in _DROP_WORDS:
            words.append(w)
    return " ".join(sorted(set(words)))


def normalize_company(company: Optional[str]) -> str:
    return re.sub(r"\s+", " ", _COMPANY_SUFFIX.sub(" ", strip_marks(company or ""))).strip()


def normalize_location(location: Optional[str]) -> str:
    s = strip_marks(location or "")
    return {"באר שבע": "beer sheva", "beersheba": "beer sheva", "be er sheva": "beer sheva", "beer-sheva": "beer sheva",
            "tlv": "tel aviv", "תל אביב": "tel aviv"}.get(s, s)


def normalize_contact(apply: Optional[str]) -> str:
    return (apply or "").strip().lower().removeprefix("mailto:").rstrip("/")


def job_fingerprint(*args, **kwargs):
    """Milestone 3: runs your mine.job_fingerprint (see jobagent/hooks.py)."""
    from .hooks import call
    return call("job_fingerprint", *args, **kwargs)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def near_duplicate(*args, **kwargs):
    """Milestone 3: runs your mine.near_duplicate (see jobagent/hooks.py)."""
    from .hooks import call
    return call("near_duplicate", *args, **kwargs)


# ---------------------------------------------------------------- post level
def shingles(text: str, k: int = 5) -> set[str]:
    s = strip_marks(text)
    return {s[i:i + k] for i in range(max(1, len(s) - k + 1))} if s else set()


def text_similarity(a: str, b: str, k: int = 5) -> float:
    return jaccard(shingles(a, k), shingles(b, k))


def find_repost(*args, **kwargs):
    """Milestone 3: runs your mine.find_repost (see jobagent/hooks.py)."""
    from .hooks import call
    return call("find_repost", *args, **kwargs)

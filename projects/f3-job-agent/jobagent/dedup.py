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

import hashlib
import re
import unicodedata
from typing import Iterable, Optional

from .models import JobPosting

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


def job_fingerprint(job: JobPosting) -> str:
    """sha1 of 'title|company|location' (normalized), first 16 hex chars. When the company is
    unknown, the apply contact stands in for it: otherwise every anonymous "Backend Engineer"
    in Tel Aviv would get the same fingerprint."""
    who = normalize_company(job.company) or normalize_contact(job.apply)
    key = "|".join([normalize_title(job.title), who, normalize_location(job.location)])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def near_duplicate(a: JobPosting, b: JobPosting, *, title_threshold: float = 0.6) -> bool:
    """Same role, written differently.

    - companies: equal after normalization, or one of them unknown (a recruiter repost)
      but then the titles must be identical after normalization, and the apply contacts
      must be equal when both posts have one
    - locations: equal, or at least one unknown
    - seniority words in the titles (junior, senior, lead...) must be the same
    - titles: Jaccard similarity of normalized title tokens >= title_threshold
    """
    ca, cb = normalize_company(a.company), normalize_company(b.company)
    la, lb = normalize_location(a.location), normalize_location(b.location)
    if la and lb and la != lb:
        return False
    ta, tb = set(normalize_title(a.title).split()), set(normalize_title(b.title).split())
    if (ta & SENIORITY_WORDS) != (tb & SENIORITY_WORDS):  # "Junior Rust" is not "Rust"
        return False
    if ca and cb:
        return ca == cb and jaccard(ta, tb) >= title_threshold
    # One company unknown: a generic title like "Backend Engineer" in Tel Aviv is not enough.
    # Require the same title AND, when both posts give one, the same apply contact.
    if a.apply and b.apply and normalize_contact(a.apply) != normalize_contact(b.apply):
        return False
    return ta == tb and bool(ta)


# ---------------------------------------------------------------- post level
def shingles(text: str, k: int = 5) -> set[str]:
    s = strip_marks(text)
    return {s[i:i + k] for i in range(max(1, len(s) - k + 1))} if s else set()


def text_similarity(a: str, b: str, k: int = 5) -> float:
    return jaccard(shingles(a, k), shingles(b, k))


def find_repost(text: str, previous: Iterable[tuple[str, str]], threshold: float = 0.8) -> Optional[str]:
    """Key of an earlier post whose text is a near copy of `text`, else None.
    previous: (key, text) pairs. Fine for hundreds of posts a day; for millions you would
    use MinHash + LSH (e.g. the datasketch library) instead of comparing all pairs."""
    sh = shingles(text)
    best, best_key = 0.0, None
    for key, other in previous:
        sim = jaccard(sh, shingles(other))
        if sim > best:
            best, best_key = sim, key
    return best_key if best >= threshold else None

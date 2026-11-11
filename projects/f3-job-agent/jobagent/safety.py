"""Job posts are untrusted input. Defenses, in the order a post flows through them.

1. screen_post      guardkit's HeuristicDetector (English/Hebrew/Arabic regex signals) plus two
                    structural signals of our own (forged post markers, "SYSTEM:" lines) on
                    the raw text. A flagged post is still processed, but every job from it is
                    marked suspicious: it can never reach the "match" tier or get a draft.
2. spotlight        the post enters the prompt between random-nonce markers, with every space
                    replaced by a datamark character (Hines et al. 2024, guardkit.Spotlight).
                    The system prompt says: text between the markers is data.
3. validate_job     output validation, the layer that does not depend on the model obeying:
                    the apply link must be copied from the post, URLs must be http(s),
                    numbers must appear in the post, text fields cannot smuggle links.
4. cap_jobs         at most MAX_JOBS_PER_POST jobs per post (an attack can ask for 50).
5. redact           PII (phones, emails, Israeli IDs) is removed before text reaches
                    traces, logs or stored eval data. The digest itself keeps the apply contact:
                    it goes to the owner's own group, and they need it.

What the agent can DO is also limited by design: it can write a digest to one fixed group
and create Gmail DRAFTS. It cannot send email, cannot message anyone else, and has no
tool the model can call. A successful injection can at worst put a bad line in a digest.
"""

from __future__ import annotations

import re
from typing import Optional

from guardkit.detectors import HeuristicDetector
from guardkit.redact import redact_pii, redact_secrets

from .models import Finding, PostExtraction

DATAMARK = "ˆ"  # the same marker guardkit.Spotlight uses
MAX_JOBS_PER_POST = 8
MAX_TITLE_LEN = 120
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ANY_SCHEME_RE = re.compile(r"\b[a-z][a-z0-9+.-]{1,15}:(?://)?\S+", re.I)

_detector = HeuristicDetector("balanced")


# Structural signals specific to THIS prompt format, added on top of guardkit's generic ones:
# a forged copy of our own post markers, or a line that starts with "SYSTEM:".
FORGED_MARKER = re.compile(r"<<\s*/?\s*post\b", re.I)
SYSTEM_LINE = re.compile(r"(?im)^\s*(?:system|assistant)\s*:")


def screen_post(*args, **kwargs):
    """Milestone 4: runs your mine.screen_post (see jobagent/hooks.py)."""
    from .hooks import call
    return call("screen_post", *args, **kwargs)


def spotlight(*args, **kwargs):
    """Milestone 4: runs your mine.spotlight (see jobagent/hooks.py)."""
    from .hooks import call
    return call("spotlight", *args, **kwargs)


def unmark(text: Optional[str]) -> Optional[str]:
    """Models sometimes copy the datamark into their output; turn it back into spaces."""
    return text.replace(DATAMARK, " ") if isinstance(text, str) else text


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace(DATAMARK, " ")).strip().lower().rstrip("/.")


def appears_in(needle: str, haystack: str) -> bool:
    return bool(needle) and _norm(needle) in _norm(haystack)


HE_NUMBERS = {1: ("שנה",), 2: ("שנתיים",), 3: ("שלוש",), 4: ("ארבע",), 5: ("חמש",), 6: ("שש",), 7: ("שבע",),
              8: ("שמונה",), 10: ("עשר",)}


def number_in_text(n: int, text: str) -> bool:
    """The number as digits, or as a Hebrew number word ("שנתיים" = 2)."""
    if re.search(rf"(?<!\d){n}(?!\d)", text):
        return True
    return any(w in text for w in HE_NUMBERS.get(n, ()))


def validate_job(*args, **kwargs):
    """Milestone 4: runs your mine.validate_job (see jobagent/hooks.py)."""
    from .hooks import call
    return call("validate_job", *args, **kwargs)


def validate_extraction(ex: PostExtraction, source_text: str,
                        validate=validate_job) -> tuple[PostExtraction, list[list[Finding]]]:
    """Apply `validate` to every job, and cap the number of jobs. Returns the cleaned
    extraction and one list of findings per kept job."""
    jobs, per_job = [], []
    for job in ex.jobs[:MAX_JOBS_PER_POST]:
        clean, f = validate(job, source_text)
        jobs.append(clean)
        per_job.append(f)
    if len(ex.jobs) > MAX_JOBS_PER_POST and per_job:
        per_job[0].append(Finding(code="too_many_jobs", detail=str(len(ex.jobs)), severity="block"))
    return ex.model_copy(update={"jobs": jobs}), per_job


def redact(text: str) -> str:
    """For traces, logs and stored data: no phone numbers, emails, IDs or API keys."""
    return redact_secrets(redact_pii(text or ""))


def redact_for_span(text: str) -> tuple[str, int]:
    """obskit's redactor signature: (text, number of replacements)."""
    out = redact(text)
    return out, int(out != text)

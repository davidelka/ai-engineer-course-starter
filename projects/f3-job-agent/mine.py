"""Your code for final project F3 (the job agent). Four milestones are coding TODOs:

    M3  job_fingerprint, near_duplicate      dedup across sources
    M5  validate_job                         output validation: posts are untrusted
    M6  score_job                            the matcher: rules + explanations
    M7  due_slot                             which schedule slot to run, idempotently

Each is checked by tests in ./tests (python -m pytest -q projects/f3-job-agent/tests).
Every command of the project (`python -m jobagent ...`) uses YOUR function once it stops
raising NotImplementedError, and the reference one until then (it says so once per run).
`--reference` forces the references. The references are in jobagent/ (dedup.py, safety.py,
match.py, schedule.py): try not to read them before your tests pass.

The data you work with (all in jobagent/models.py):
    JobPosting  title, company, location (canonical city), work_mode (onsite|hybrid|remote|None),
                seniority (junior|mid|senior|lead|None), years_required (int|None),
                categories [CategoryScore(category, confidence)], hardware_oriented (bool),
                language (he|en), apply (email or URL|None), tech_stack, posted_at
                .primary_category  -> the category with the highest confidence
    Finding     code, detail, severity ("info" | "warn" | "block")
    Preferences data/preferences.yaml, loaded by jobagent.prefs.load_prefs()
"""

from __future__ import annotations

import hashlib  # noqa: F401  (you will likely need it)
import re  # noqa: F401
from datetime import datetime, timedelta
from typing import Iterable, Optional

from jobagent.dedup import jaccard, normalize_company, normalize_contact, normalize_location, normalize_title  # noqa: F401
from jobagent.models import Finding, JobPosting  # noqa: F401
from jobagent.prefs import Preferences, region_of  # noqa: F401
from jobagent.safety import EMAIL_RE, URL_RE, appears_in, number_in_text, unmark  # noqa: F401
from jobagent.schedule import TZ, latest_slot, slot_key  # noqa: F401


# ------------------------------------------------------------------ M3: dedup
def job_fingerprint(job: JobPosting) -> str:
    """A stable id for "the same role": 16 lowercase hex characters.

    The recipe is fixed (tests and stored data depend on it): the first 16 hex characters of the
    sha1 of the UTF-8 string
        normalize_title(job.title) + "|" + WHO + "|" + normalize_location(job.location)
    where WHO = normalize_company(job.company), or normalize_contact(job.apply) when the company
    normalizes to "" (otherwise every anonymous "Backend Engineer" in Tel Aviv would share one id).
    None fields normalize to "".
    Example: "Senior Back-End Developer" at "CyberDome Ltd." in "Beer Sheva" and
    "Developer, Senior Backend" at "cyberdome" in "beer sheva" get the same fingerprint.

    Stuck? HINTS.md -> job_fingerprint
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement job_fingerprint")


def near_duplicate(a: JobPosting, b: JobPosting, *, title_threshold: float = 0.6) -> bool:
    """True when a and b are the same role written differently (symmetric). All must hold:

    1. locations equal after normalize_location, or at least one unknown (None/"");
    2. the same seniority words {junior, senior, lead, principal, staff, mid, head} in both
       normalized titles ("Junior Rust Developer" is NOT "Rust Developer");
    3. companies (normalize_company):
         both known   -> equal, AND jaccard of the title tokens >= title_threshold
         one unknown  -> identical, non-empty normalized titles, AND when both jobs have an apply
                         contact, equal contacts (normalize_contact). Two different "Backend
                         Engineer" jobs in Tel Aviv with unknown companies are not the same job.
    Title tokens = the words of normalize_title(title).

    Stuck? HINTS.md -> near_duplicate
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement near_duplicate")


# ------------------------------------------------------------------ M5: output validation
def validate_job(job: JobPosting, source_text: str) -> tuple[JobPosting, list[Finding]]:
    """Return (a CLEANED deep copy of job, findings). Never modify `job` itself.

    Posts are untrusted, and so is the model that read them. The datamark character (unmark())
    is removed from title, company, location and apply. Findings (tests check `code` and
    `severity`; `detail` is free text) and their fixes:
      apply_bad_scheme     (block)  apply is neither an email (EMAIL_RE) nor an http(s):// URL -> None
      apply_not_in_source  (block)  apply does not appear in source_text (appears_in; a "mailto:"
                                    prefix is dropped, also in the cleaned value)      -> None
                                    (a bad scheme is reported instead of this, never both)
      years_not_in_source  (warn)   years_required not in the text (number_in_text: digits or a
                                    Hebrew word like "שנתיים")                         -> None
      link_in_text_field   (block)  title or company contains a URL or email: cut at the first
                                    link, strip " -:|,"; if empty: company None, title "(unknown title)"
      title_too_long       (warn)   title over 120 characters -> cut to 120 (rstrip)

    Stuck? HINTS.md -> validate_job
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement validate_job")


# ------------------------------------------------------------------ M6: the matcher
def score_job(p: JobPosting, prefs: Preferences, *, suspicious: bool = False) -> dict:
    """Return {"score": int, "tier": "match"|"maybe"|"skip", "category": str|None,
               "cv": str|None, "reasons": [str, ...]}.

    score = category (0-50) + location (0-30) + experience (0-20). Every number comes from
    `prefs` (data/preferences.yaml): never hard-code the owner's criteria.
    Category: only categories with confidence >= 0.5 that are in prefs.targets count. A full
      match is 50; automation when targets["automation"].prefer_hardware and the job is not
      hardware_oriented is worth targets["automation"].web_score; a category other than
      p.primary_category is worth at most prefs.secondary_points. The best wins; a tie goes to the
      earlier key in prefs.targets. No target -> 0 points, category None.
    Location (region_of(p.location), p.work_mode): unknown region -> 30 if remote, else
      prefs.location.unknown_location_points; otherwise the points of the FIRST rule in
      prefs.location.rules for that region (or "any") whose modes include the work mode (None is a
      valid mode: "not stated"); no rule -> prefs.location.default_points.
    Experience (prefs.experience; accepted seniority = targets[category].accept_seniority, or
      ["mid", "senior"] with no category): the lower of a seniority score (junior or lead not
      accepted -> junior_points / lead_points, else 20) and a years score (None or up to
      ok_up_to_years -> 20, up to stretch_up_to_years -> stretch_points, more -> 0).
    Tier: "match" needs score >= thresholds.match and 50 category points; "maybe" needs
      score >= thresholds.maybe and category points > 0; else "skip". suspicious=True turns a
      "match" into "maybe" and adds a reason.
    cv = prefs.targets[category].cv when there is a category.
    reasons: at least one Hebrew line per component, each with "<points>/<max>", e.g.
      "[כלל] Beer Sheva (דרום, היברידי): 30/30". Prefix "[מודל]" when the line rests on a model
      judgment (category, hardware_oriented, seniority word), "[כלל]" otherwise.

    Stuck? HINTS.md -> score_job
    """
    # TODO(M6)
    raise NotImplementedError("M6: implement score_job")


# ------------------------------------------------------------------ M7: scheduling
def due_slot(now: datetime, done: Iterable[str], *, max_late: timedelta = timedelta(hours=6)) -> Optional[str]:
    """The slot key to run at `now`, or None. Slots: 08:30, 15:00, 21:00 Asia/Jerusalem (TZ).

    The candidate is the most recent slot at or before `now` (before 08:30 that is yesterday's
    21:00), as a key like "2026-11-01T08:30" (slot_key). Return None when that key is in `done`
    (a retry or a duplicate trigger already ran it), or when `now` is more than `max_late` after
    the slot (the next slot covers the posts). `now` may be in any time zone; daylight saving
    time must not shift the slots.

    Stuck? HINTS.md -> due_slot
    """
    # TODO(M7)
    raise NotImplementedError("M7: implement due_slot")

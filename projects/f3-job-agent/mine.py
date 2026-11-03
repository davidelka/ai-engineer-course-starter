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
    """A stable id for "the same role": the first 16 hex characters of the sha1 of
        normalize_title(job.title) + "|" + WHO + "|" + normalize_location(job.location)
    where WHO = normalize_company(job.company), or, when that is empty, normalize_contact(job.apply)
    (without it, every anonymous "Backend Engineer" in Tel Aviv would share one fingerprint).
    None fields normalize to "". Encode the string as UTF-8 before hashing.

    Example: "Senior Back-End Developer" at "CyberDome Ltd." in "Beer Sheva" and
    "Developer, Senior Backend" at "cyberdome" in "beer sheva" get the same fingerprint.
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement job_fingerprint")


def near_duplicate(a: JobPosting, b: JobPosting, *, title_threshold: float = 0.6) -> bool:
    """True when a and b are the same role written differently. All of these must hold:

    1. locations: equal after normalize_location, or at least one of them is unknown (None/"")
    2. seniority words: the sets {junior, senior, lead, principal, staff, mid, head} found in the
       two normalized titles are equal ("Junior Rust Developer" is NOT "Rust Developer")
    3. companies (normalize_company):
         both known   -> they must be equal AND jaccard(title tokens) >= title_threshold
         one unknown  -> the normalized titles must be identical (and not empty), AND if both
                         jobs have an apply contact, the contacts must be equal
                         (normalize_contact). Two different "Backend Engineer" jobs in
                         Tel Aviv with unknown companies are not the same job.
    Title tokens = set(normalize_title(title).split()). jaccard() is imported above.
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement near_duplicate")


# ------------------------------------------------------------------ M5: output validation
def validate_job(job: JobPosting, source_text: str) -> tuple[JobPosting, list[Finding]]:
    """Return (a CLEANED deep copy of job, findings). Never modify `job` itself.

    First apply unmark() to title, company, location and apply (models sometimes copy the
    datamark character from the spotlighted prompt). Then:

    apply_not_in_source  (block)  apply is set but does not appear in source_text. Use
                                  appears_in(needle, haystack): case-insensitive, whitespace-
                                  normalized, trailing "/" or "." ignored. A "mailto:" prefix is
                                  removed before comparing (and in the cleaned value).
                                  -> apply = None
    apply_bad_scheme     (block)  apply is neither an email (EMAIL_RE.fullmatch) nor a URL that
                                  starts with http:// or https://   -> apply = None
                                  (check the scheme BEFORE checking the source)
    years_not_in_source  (warn)   years_required is set, but number_in_text(years, source_text)
                                  is False (digits, or a Hebrew word like "שנתיים")
                                  -> years_required = None
    link_in_text_field   (block)  title or company contains a URL or an email (URL_RE / EMAIL_RE):
                                  cut the field at the first link, strip " -:|,"; if nothing is
                                  left: company -> None, title -> "(unknown title)"
    title_too_long       (warn)   len(title) > 120 -> cut to 120 characters (rstrip)

    `detail` is free text (the value or the field name); tests check `code` and `severity`.
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement validate_job")


# ------------------------------------------------------------------ M6: the matcher
def score_job(p: JobPosting, prefs: Preferences, *, suspicious: bool = False) -> dict:
    """Return {"score": int, "tier": "match"|"maybe"|"skip", "category": str|None,
               "cv": str|None, "reasons": [str, ...]}.

    score = category (0-50) + location (0-30) + experience (0-20). Read every number from
    `prefs` (data/preferences.yaml), never hard-code the owner's criteria.

    Category (consider only categories with confidence >= 0.5 that are in prefs.targets):
      - automation with targets["automation"].prefer_hardware and not p.hardware_oriented
                                                    -> targets["automation"].web_score points
      - otherwise                                   -> 50
      - a category that is not p.primary_category   -> at most prefs.secondary_points
      Take the best; on a tie prefer the earlier key in prefs.targets. No target -> 0, None.
    Location: region = region_of(p.location); mode = p.work_mode
      - region None: 30 if mode == "remote" else prefs.location.unknown_location_points
      - else the FIRST rule in prefs.location.rules whose region is `region` or "any" and whose
        modes list contains mode (None is a valid entry: "mode not stated") -> rule.points
      - no rule matched -> prefs.location.default_points
    Experience (e = prefs.experience; accepted = targets[category].accept_seniority, or
    ["mid", "senior"] when there is no category):
      - seniority points: junior not accepted -> e.junior_points; lead not accepted ->
        e.lead_points; otherwise 20
      - years points: None or <= e.ok_up_to_years -> 20; <= e.stretch_up_to_years ->
        e.stretch_points; more -> 0
      - experience = min(seniority points, years points)
    Tier: "match" if score >= prefs.thresholds.match AND category points == 50;
          "maybe" if score >= prefs.thresholds.maybe AND category points > 0; else "skip".
          suspicious=True turns a "match" into "maybe" (and adds a reason).
    cv = prefs.targets[category].cv when there is a category.
    reasons: at least one Hebrew line per component, each with "<points>/<max>", e.g.
      "[כלל] Beer Sheva (דרום, היברידי): 30/30". Prefix "[מודל]" when the line depends on a
      model judgment (category, hardware_oriented, seniority word) and "[כלל]" otherwise.
    """
    # TODO(M6)
    raise NotImplementedError("M6: implement score_job")


# ------------------------------------------------------------------ M7: scheduling
def due_slot(now: datetime, done: Iterable[str], *, max_late: timedelta = timedelta(hours=6)) -> Optional[str]:
    """The slot key to run at `now`, or None. Slots: 08:30, 15:00, 21:00 Asia/Jerusalem.

    - candidate = latest_slot(now): the most recent slot time <= now (before 08:30 that is
      yesterday's 21:00). slot_key(dt) turns it into "2026-11-01T08:30".
    - None if that key is in `done` (already ran: a retry or a duplicate trigger)
    - None if now - candidate > max_late (too late to be useful; the next slot covers the posts)
    `now` may be in any time zone (compare aware datetimes, or convert with .astimezone(TZ)).
    """
    # TODO(M7)
    raise NotImplementedError("M7: implement due_slot")

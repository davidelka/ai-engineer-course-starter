"""Your code for final project F3 (the job agent, production edition): eleven functions.

You build the parts of the agent that the course taught: deduplication at two levels, the defences
against untrusted posts (screen, spotlighting, output validation), the structured extraction call,
the matcher, the idempotent scheduling, and the evaluation's alignment and relevance metrics. The
course gives you the rest ready: the sources (WhatsApp exports, Airtable), the SQLite state store,
the digest and the delivery ports, the reports and traces, the admin API and the deployment files.

    M3  find_repost, job_fingerprint, near_duplicate   dedup: a reposted message, the same job twice
    M4  screen_post, spotlight, validate_job           posts are untrusted: screen, mark, check the output
    M5  extract_post                                   one post -> jobs, with a structured-output call
    M6  score_job                                      the matcher: rules + explanations
    M7  due_slot                                       which schedule slot to run, idempotently
    M9  align, relevance                               the evaluation: which predicted job is which, and
                                                       precision/recall of what reaches the digest

After milestone 7 a full run works on your code (milestone 5 is needed for the LLM extractor only).
Each is checked by tests in ./tests (python -m pytest -q projects/f3-job-agent/tests). Every command
of the project (`python -m jobagent ...`) uses YOUR functions; a command that needs one you have not
written yet stops and names the milestone. The reference implementations are on the repo's
`solutions` branch, for comparing AFTER your tests pass. Stuck? HINTS.md has three graded hints per
function. mine.py is loaded under the module name "f3_mine".

The data you work with (all in jobagent/models.py):
    JobPosting  title, company, location (canonical city), work_mode (onsite|hybrid|remote|None),
                seniority (junior|mid|senior|lead|None), years_required (int|None),
                categories [CategoryScore(category, confidence)], hardware_oriented (bool),
                language (he|en), apply (email or URL|None), tech_stack, posted_at
                .primary_category  -> the category with the highest confidence
    RawPost     source, channel, text, ...            PostExtraction(is_job_post, jobs)
    Finding     code, detail, severity ("info" | "warn" | "block")
    Preferences data/preferences.yaml, loaded by jobagent.prefs.load_prefs()
"""

from __future__ import annotations

import hashlib  # noqa: F401  (you will likely need it)
import re  # noqa: F401
import secrets  # noqa: F401
import time  # noqa: F401
from datetime import datetime, timedelta
from typing import Iterable, Optional

from guardkit.detectors import HeuristicDetector, Verdict  # noqa: F401

from jobagent.dedup import (SENIORITY_WORDS, jaccard, normalize_company, normalize_contact,  # noqa: F401
                            normalize_location, normalize_title, shingles)
from jobagent.evaluate import prf  # noqa: F401
from jobagent.extract import SYSTEM_PROMPT, ExtractResult, build_user_prompt  # noqa: F401
from jobagent.models import Finding, JobPosting, PostExtraction, RawPost  # noqa: F401
from jobagent.prefs import Preferences, region_of  # noqa: F401
from jobagent.safety import (DATAMARK, EMAIL_RE, FORGED_MARKER, SYSTEM_LINE, URL_RE, appears_in,  # noqa: F401
                             number_in_text, unmark)
from jobagent.schedule import TZ, latest_slot, slot_key  # noqa: F401


# ------------------------------------------------------------------ M3: a reposted message
def find_repost(text: str, previous: Iterable[tuple[str, str]], threshold: float = 0.8) -> Optional[str]:
    """The key of an earlier post whose text is a near copy of `text`, else None.

    The same message is often posted again, in another group or the next day, with an emoji or a line
    changed. Catching it BEFORE the model is called saves the extraction. `previous` is an iterable of
    (key, text) pairs. Compare the character shingles of the two texts (jobagent.dedup.shingles, k=5)
    with jaccard: return the key of the MOST similar earlier post when its similarity is >= threshold,
    else None (also None when there is nothing to compare with).

    Stuck? HINTS.md -> find_repost
    """
    # TODO(M3)
    raise NotImplementedError("M3: implement find_repost")


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


# ------------------------------------------------------------------ M4: the input screen
_detector = HeuristicDetector("balanced")


def screen_post(text: str) -> Verdict:
    """Does this post try to talk to the model? Returns a guardkit Verdict(flagged, score, reasons).

    Start from guardkit's detector: _detector.detect(text, kind="document"). Then add two structural
    signals of THIS prompt format: "forged_post_marker" when FORGED_MARKER matches (a fake copy of our
    <<post>> markers) and "system_line" when SYSTEM_LINE matches (a line that starts with "SYSTEM:" or
    "assistant:"). If any of the two matched: Verdict(True, detector score + 3.0 per matched signal,
    detector reasons + the matched names, in that order). Otherwise the detector's verdict as it is.
    None or "" is a clean post.

    Stuck? HINTS.md -> screen_post
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement screen_post")


# ------------------------------------------------------------------ M4: spotlighting
def spotlight(text: str, nonce: Optional[str] = None) -> tuple[str, str]:
    """Wrap an untrusted post for the prompt. Returns (wrapped, nonce).

    - nonce: the one given, or a new random one (secrets.token_hex(4));
    - every run of spaces and tabs in the text becomes DATAMARK (newlines stay);
    - wrapped = "<<post nonce=N>>\n" + marked text + "\n<</post nonce=N>>".
    The system prompt tells the model that text between the markers is data. A new nonce per post means
    a post cannot close the markers in advance (screen_post flags anyone who tries).

    Stuck? HINTS.md -> spotlight
    """
    # TODO(M4)
    raise NotImplementedError("M4: implement spotlight")


# ------------------------------------------------------------------ M4: output validation
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
    # TODO(M4)
    raise NotImplementedError("M4: implement validate_job")


# ------------------------------------------------------------------ M5: structured extraction
def extract_post(llm, post: RawPost, *, name: str = "llm", max_tokens: int = 2000, max_repairs: int = 1,
                 mode: str = "native", cache_system: bool = True) -> ExtractResult:
    """One post in, its jobs out, with one structured-output call (llmkit.structured.complete_structured).

    - the prompt: when cache_system is True and mode == "native", a ChatRequest with one user message,
      build_user_prompt(post) (it spotlights the post), and system=[Block(SYSTEM_PROMPT, cache="5m")]
      (llmkit.types), max_tokens as given; otherwise just the string build_user_prompt(post).
    - the call: complete_structured(llm, prompt, PostExtraction, system=SYSTEM_PROMPT, mode=mode,
      max_tokens=max_tokens, max_repairs=max_repairs).
    - success: ExtractResult(r.value, r.cost_usd, r.input_tokens, r.output_tokens, r.attempts,
      latency_s, extractor=name), where latency_s is the wall time of the call (time.perf_counter()).
    - StructuredError: FAIL CLOSED. ExtractResult(PostExtraction(is_job_post=False, jobs=[]), with the
      cost, tokens and attempts of exc.result (0 or 1 when missing), latency_s,
      error=f"structured_{exc.stage}", extractor=name). A post we could not read yields no jobs; it
      never yields half a job.

    Stuck? HINTS.md -> extract_post
    """
    # TODO(M5)
    raise NotImplementedError("M5: implement extract_post")


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


# ------------------------------------------------------------------ M9: the evaluation
def align(preds: list[JobPosting], golds: list[dict]) -> list[Optional[JobPosting]]:
    """Match the predicted jobs of one post to its labeled (gold) jobs. Returns one entry per gold job:
    the predicted job matched to it, or None.

    The similarity of a (gold, predicted) pair is the jaccard of the words of normalize_title(gold
    "title") and normalize_title(predicted .title), plus a 0.2 bonus when predicted .primary_category
    equals gold "primary_category". Match greedily: go over all pairs from the most similar down, and
    take a pair when neither its gold nor its predicted job is taken yet. Each predicted job is used at
    most once; a gold job with no match left gets None. (Ties: sort the (similarity, gold index,
    predicted index) tuples in reverse, as Python does.)

    Stuck? HINTS.md -> align
    """
    # TODO(M9)
    raise NotImplementedError("M9: implement align")


def relevance(pred_tiers: list[str], gold_tiers: list[str]) -> dict:
    """Precision and recall of what reaches the digest, from the tier of each job ("match", "maybe"
    or "other"), predicted vs labeled, position by position.

    Two views, each prf(tp, fp, fn) (jobagent.evaluate.prf):
    - "match": positive = the tier is "match" (the top of the digest);
    - "shown": positive = the tier is "match" or "maybe" (everything that appears in the digest).
    tp: both positive; fp: predicted positive, gold not; fn: gold positive, predicted not.
    Plus "tier_accuracy": the share of positions where the two tiers are equal (divide by
    max(1, len(gold_tiers))).

    Stuck? HINTS.md -> relevance
    """
    # TODO(M9)
    raise NotImplementedError("M9: implement relevance")

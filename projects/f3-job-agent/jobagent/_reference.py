"""Reference implementations of the F3 milestones (solutions branch only).

This file exists only on the `solutions` branch of the course repo. On `main` the agent runs your
functions from mine.py, and a milestone you have not written yet stops the command with a message
that names it. Compare with this file AFTER your tests pass.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from datetime import datetime, timedelta
from typing import Iterable, Optional

from guardkit.detectors import Verdict
from jobagent.dedup import (SENIORITY_WORDS, jaccard, normalize_company, normalize_contact, normalize_location,
                            normalize_title, shingles)
from jobagent.evaluate import prf
from jobagent.extract import SYSTEM_PROMPT, ExtractResult, build_user_prompt
from jobagent.match import FULL_CATEGORY, category_points, experience_points, location_points
from jobagent.models import Finding, JobPosting, PostExtraction, RawPost
from jobagent.prefs import Preferences
from jobagent.safety import (ANY_SCHEME_RE, DATAMARK, EMAIL_RE, FORGED_MARKER, MAX_TITLE_LEN, SYSTEM_LINE, URL_RE,
                             _detector, appears_in, number_in_text, unmark)
from jobagent.schedule import TZ, latest_slot, slot_key


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


def job_fingerprint(job: JobPosting) -> str:
    """sha1 of 'title|company|location' (normalized), first 16 hex chars. When the company is
    unknown, the apply contact stands in for it: otherwise every anonymous "Backend Engineer"
    in Tel Aviv would get the same fingerprint."""
    who = normalize_company(job.company) or normalize_contact(job.apply)
    key = "|".join([normalize_title(job.title), who, normalize_location(job.location)])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


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


def screen_post(text: str) -> Verdict:
    v = _detector.detect(text, kind="document")
    extra = [name for name, rx in (("forged_post_marker", FORGED_MARKER), ("system_line", SYSTEM_LINE))
             if rx.search(text or "")]
    if extra:
        return Verdict(True, v.score + 3.0 * len(extra), v.reasons + extra)
    return v


def spotlight(text: str, nonce: Optional[str] = None) -> tuple[str, str]:
    """Wrap untrusted text for the prompt. Returns (wrapped, nonce)."""
    nonce = nonce or secrets.token_hex(4)
    marked = re.sub(r"[ \t]+", DATAMARK, text)
    return f"<<post nonce={nonce}>>\n{marked}\n<</post nonce={nonce}>>", nonce


def validate_job(job: JobPosting, source_text: str) -> tuple[JobPosting, list[Finding]]:
    """Reference version of milestone 5. Returns a CLEANED copy and what was found.

    Rules:
      apply_not_in_source  apply is set but does not appear in the post (case-insensitive,
                           whitespace-normalized, trailing '/' or '.' ignored) -> apply=None, block
      apply_bad_scheme     apply is neither an email nor an http(s) URL -> apply=None, block
      years_not_in_source  years_required is set but that number is not in the post (as digits
                           or as a Hebrew number word, see number_in_text) -> None, warn
      link_in_text_field   title or company contains a URL or email -> the field is cut at
                           the link (company becomes None if nothing is left), block
      title_too_long       title longer than MAX_TITLE_LEN -> cut, warn
    """
    j = job.model_copy(deep=True)
    findings: list[Finding] = []
    j.title, j.company, j.location, j.apply = unmark(j.title), unmark(j.company), unmark(j.location), unmark(j.apply)

    if j.apply:
        a = j.apply.strip()
        is_email = bool(EMAIL_RE.fullmatch(a.removeprefix("mailto:")))
        is_http = a.lower().startswith(("http://", "https://"))
        if not (is_email or is_http):
            findings.append(Finding(code="apply_bad_scheme", detail=a[:80], severity="block"))
            j.apply = None
        elif not appears_in(a.removeprefix("mailto:"), source_text):
            findings.append(Finding(code="apply_not_in_source", detail=a[:80], severity="block"))
            j.apply = None
        else:
            j.apply = a.removeprefix("mailto:")

    if j.years_required is not None and not number_in_text(j.years_required, source_text):
        findings.append(Finding(code="years_not_in_source", detail=str(j.years_required)))
        j.years_required = None

    for field in ("title", "company"):
        val = getattr(j, field)
        if val and (URL_RE.search(val) or EMAIL_RE.search(val) or ANY_SCHEME_RE.search(val)):
            m = min(x.start() for x in (URL_RE.search(val), EMAIL_RE.search(val), ANY_SCHEME_RE.search(val)) if x)
            cut = val[:m].strip(" -:|,")
            findings.append(Finding(code="link_in_text_field", detail=field, severity="block"))
            setattr(j, field, cut or (None if field == "company" else "(unknown title)"))

    if len(j.title) > MAX_TITLE_LEN:
        findings.append(Finding(code="title_too_long", detail=str(len(j.title))))
        j.title = j.title[:MAX_TITLE_LEN].rstrip()
    return j, findings


def score_job(p: JobPosting, prefs: Preferences, *, suspicious: bool = False) -> dict:
    """{score, tier, category, cv, reasons}. Pure function of the posting and the prefs."""
    cat_pts, cat, cat_reason = category_points(p, prefs)
    loc_pts, loc_reason = location_points(p, prefs)
    exp_pts, exp_reason = experience_points(p, prefs, cat)
    score = cat_pts + loc_pts + exp_pts
    th = prefs.thresholds
    if score >= th.match and cat_pts == FULL_CATEGORY:
        tier = "match"
    elif score >= th.maybe and cat_pts > 0:
        tier = "maybe"
    else:
        tier = "skip"
    reasons = [cat_reason, loc_reason, exp_reason]
    if suspicious and tier == "match":
        tier = "maybe"
        reasons.append("[כלל] בפוסט זוהה ניסיון הזרקה: הורד ל'אולי', בלי טיוטה")
    return {"score": score, "tier": tier, "category": cat,
            "cv": prefs.targets[cat].cv if cat in prefs.targets else None, "reasons": reasons}


def due_slot(now: datetime, done: Iterable[str], *, max_late: timedelta = timedelta(hours=6)) -> Optional[str]:
    """Reference version of milestone 7. The slot key to run now, or None.

    - the candidate is latest_slot(now)
    - None if that slot is already in `done`
    - None if it is more than `max_late` in the past (the next slot will pick up the posts;
      catching up a 12-hour-old digest helps nobody)
    Missed older slots are never run separately: posts are filtered by "since the last done
    run", so the next run covers them.
    """
    s = latest_slot(now)
    key = slot_key(s)
    if key in set(done):
        return None
    if now.astimezone(TZ) - s > max_late:
        return None
    return key


def align(preds: list[JobPosting], golds: list[dict]) -> list[Optional[JobPosting]]:
    """For each gold job, the predicted job with the most similar title (each used once)."""
    out: list[Optional[JobPosting]] = [None] * len(golds)
    pairs = []
    for gi, g in enumerate(golds):
        gt = set(normalize_title(g["title"]).split())
        for pi, p in enumerate(preds):
            pt = set(normalize_title(p.title).split())
            bonus = 0.2 if p.primary_category == g["primary_category"] else 0.0
            pairs.append((jaccard(gt, pt) + bonus, gi, pi))
    used_g, used_p = set(), set()
    for sim, gi, pi in sorted(pairs, reverse=True):
        if gi in used_g or pi in used_p:
            continue
        out[gi] = preds[pi]
        used_g.add(gi)
        used_p.add(pi)
    return out


def relevance(pred_tiers: list[str], gold_tiers: list[str]) -> dict:
    out = {}
    for name, pos in (("match", {"match"}), ("shown", {"match", "maybe"})):
        tp = sum(1 for p, g in zip(pred_tiers, gold_tiers) if p in pos and g in pos)
        fp = sum(1 for p, g in zip(pred_tiers, gold_tiers) if p in pos and g not in pos)
        fn = sum(1 for p, g in zip(pred_tiers, gold_tiers) if p not in pos and g in pos)
        out[name] = prf(tp, fp, fn)
    out["tier_accuracy"] = sum(p == g for p, g in zip(pred_tiers, gold_tiers)) / max(1, len(gold_tiers))
    return out


# ------------------------------------------------------------------ M5: structured extraction
def extract_post(llm, post: RawPost, *, name: str = "llm", max_tokens: int = 2000, max_repairs: int = 1,
                 mode: str = "native", cache_system: bool = True) -> ExtractResult:
    from llmkit.structured import StructuredError, complete_structured

    t0 = time.perf_counter()
    try:
        if cache_system and mode == "native":
            from llmkit.types import Block, ChatRequest, Message

            prompt = ChatRequest(messages=[Message("user", build_user_prompt(post))],
                                 system=[Block(SYSTEM_PROMPT, cache="5m")], max_tokens=max_tokens)
        else:
            prompt = build_user_prompt(post)
        r = complete_structured(llm, prompt, PostExtraction, system=SYSTEM_PROMPT,
                                mode=mode, max_tokens=max_tokens, max_repairs=max_repairs)
        return ExtractResult(r.value, r.cost_usd, r.input_tokens, r.output_tokens, r.attempts,
                             time.perf_counter() - t0, extractor=name)
    except StructuredError as exc:  # fail closed: no jobs from a post we could not read
        res = exc.result
        return ExtractResult(PostExtraction(is_job_post=False, jobs=[]), getattr(res, "cost_usd", 0.0) or 0.0,
                             getattr(res, "input_tokens", 0), getattr(res, "output_tokens", 0),
                             getattr(res, "attempts", 1), time.perf_counter() - t0,
                             error=f"structured_{exc.stage}", extractor=name)

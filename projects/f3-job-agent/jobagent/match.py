"""Matching: deterministic rules over extracted facts, with an explanation per rule.

    score = category (0-50) + location (0-30) + experience (0-20)
    tier  = match  if score >= thresholds.match and the category fit is full and not suspicious
            maybe  if score >= thresholds.maybe and there is some category fit
            skip   otherwise

Where the model's judgment enters, and where it does not:
  - The extractor (an LLM in production) supplies FACTS that need reading comprehension:
    categories with confidence, hardware_oriented, seniority word, years, city, work mode.
    Each reason that depends on such a judgment is marked "[מודל]".
  - The DECISION is code: thresholds, regions, CV choice. Reasons from pure rules are
    marked "[כלל]". Changing the model never silently changes the policy, and every tier
    can be explained line by line.

Reference version of milestone 6 (`score_job` in mine.py).
"""

from __future__ import annotations

from typing import Optional

from .models import Job, JobPosting
from .prefs import Preferences, region_of

CAT_HE = {"backend": "Backend", "automation": "אוטומציה/ולידציה", "embedded": "Embedded/System", "rust": "Rust",
          "frontend": "Frontend", "fullstack": "Fullstack", "devops": "DevOps", "data": "Data/ML",
          "qa_manual": "QA ידני", "other": "אחר"}
MODE_HE = {"onsite": "מהמשרד", "hybrid": "היברידי", "remote": "מהבית", None: "לא צוין"}
REGION_HE = {"south": "דרום", "center": "מרכז", "north": "צפון", "jerusalem": "ירושלים", "other": "אחר", None: "לא צוין"}
MIN_CONF = 0.5
FULL_CATEGORY = 50


def category_points(p: JobPosting, prefs: Preferences) -> tuple[int, Optional[str], str]:
    """Best target category of the job: (points 0-50, category or None, reason).

    Only categories with confidence >= MIN_CONF count. The PRIMARY category (highest
    confidence) can earn 50; a secondary target category earns at most prefs.secondary_points
    (a Fullstack role that also touches Backend is worth a look, not a full match)."""
    best: tuple[int, Optional[str], str] = (0, None, "[מודל] התחום לא ברשימת היעדים")
    order = list(prefs.targets)
    for c in sorted(p.categories, key=lambda c: -c.confidence):
        if c.confidence < MIN_CONF or c.category not in prefs.targets:
            continue
        t = prefs.targets[c.category]
        if c.category == "automation" and t.prefer_hardware and not p.hardware_oriented:
            cand = (t.web_score, "automation", f"[מודל] אוטומציה בלי חומרה (Web/SaaS): {t.web_score}/50")
        elif c.category == "automation" and p.hardware_oriented:
            cand = (FULL_CATEGORY, "automation", "[מודל] אוטומציה/ולידציה עם חומרה: 50/50")
        else:
            cand = (FULL_CATEGORY, c.category, f"[מודל] תחום יעד: {CAT_HE[c.category]} (ביטחון {c.confidence:.1f}): 50/50")
        if c.category != p.primary_category and cand[0] > prefs.secondary_points:
            cand = (prefs.secondary_points, cand[1],
                    f"[מודל] {CAT_HE[c.category]} הוא תחום משני במשרה (העיקרי: {CAT_HE.get(p.primary_category, '?')}): "
                    f"{prefs.secondary_points}/50")
        if cand[0] > best[0] or (cand[0] == best[0] and best[1] and order.index(cand[1]) < order.index(best[1])):
            best = cand
    return best


def location_points(p: JobPosting, prefs: Preferences) -> tuple[int, str]:
    region = region_of(p.location)
    mode = p.work_mode
    where = f"{p.location or 'מיקום לא צוין'} ({REGION_HE.get(region, region)}, {MODE_HE[mode]})"
    if region is None:
        if mode == "remote":
            return 30, f"[כלל] מהבית, מיקום לא צוין: 30/30"
        return prefs.location.unknown_location_points, f"[כלל] מיקום לא צוין: {prefs.location.unknown_location_points}/30"
    for r in prefs.location.rules:
        if r.region in (region, "any") and mode in r.modes:
            return r.points, f"[כלל] {where}: {r.points}/30"
    return prefs.location.default_points, f"[כלל] {where}: מחוץ לאזורים המועדפים, {prefs.location.default_points}/30"


def experience_points(p: JobPosting, prefs: Preferences, category: Optional[str]) -> tuple[int, str]:
    e = prefs.experience
    accepted = prefs.targets[category].accept_seniority if category in prefs.targets else ["mid", "senior"]
    sen_pts, sen_reason = 20, ""
    if p.seniority == "junior" and "junior" not in accepted:
        sen_pts, sen_reason = e.junior_points, f"[מודל] משרת ג'וניור: {e.junior_points}/20"
    elif p.seniority == "lead" and "lead" not in accepted:
        sen_pts, sen_reason = e.lead_points, f"[מודל] משרת ניהול/Lead: {e.lead_points}/20"
    y = p.years_required
    if y is None:
        yrs_pts, yrs_reason = 20, "[כלל] לא צוינו שנות ניסיון: 20/20"
    elif y <= e.ok_up_to_years:
        yrs_pts, yrs_reason = 20, f"[כלל] נדרשות {y} שנים, יש לך {prefs.experience_years}: 20/20"
    elif y <= e.stretch_up_to_years:
        yrs_pts, yrs_reason = e.stretch_points, f"[כלל] נדרשות {y} שנים, קצת מעל: {e.stretch_points}/20"
    else:
        yrs_pts, yrs_reason = 0, f"[כלל] נדרשות {y} שנים: 0/20"
    if sen_pts < yrs_pts:
        return sen_pts, sen_reason
    return yrs_pts, yrs_reason


def score_job(*args, **kwargs):
    """Milestone 6: runs your mine.score_job (see jobagent/hooks.py)."""
    from .hooks import call
    return call("score_job", *args, **kwargs)


def apply_score(job: Job, prefs: Preferences, scorer=score_job) -> Job:
    r = scorer(job.posting, prefs, suspicious=job.suspicious)
    job.score, job.tier, job.category, job.cv, job.reasons = r["score"], r["tier"], r["category"], r["cv"], r["reasons"]
    job.region = region_of(job.posting.location)
    return job

"""M6: the matcher (mine.score_job). Numbers come from data/preferences.yaml."""

import pytest

from jobagent.models import CategoryScore, JobPosting
from jobagent.prefs import load_prefs
from mine import score_job

PREFS = load_prefs()


def J(cats="backend", location="Beer Sheva", mode="hybrid", seniority=None, years=4, hw=False, title="Engineer"):
    cs = [CategoryScore(category=c, confidence=round(0.9 - 0.25 * i, 2)) for i, c in enumerate(cats.split(","))]
    return JobPosting(title=title, location=location, work_mode=mode, seniority=seniority, years_required=years,
                      categories=cs, hardware_oriented=hw)


def test_perfect_backend_match():
    r = score_job(J(), PREFS)
    assert r["score"] == 100 and r["tier"] == "match" and r["category"] == "backend"
    assert r["cv"] == PREFS.targets["backend"].cv


def test_result_shape_and_reasons():
    r = score_job(J(), PREFS)
    assert set(r) >= {"score", "tier", "category", "cv", "reasons"}
    assert len(r["reasons"]) >= 3 and all("/" in x for x in r["reasons"][:3])
    assert any(x.startswith("[מודל]") for x in r["reasons"]) and any(x.startswith("[כלל]") for x in r["reasons"])


@pytest.mark.parametrize("hw,cat_pts,tier", [(True, 50, "match"), (False, 25, "maybe")])
def test_automation_prefers_hardware(hw, cat_pts, tier):
    r = score_job(J("automation", hw=hw), PREFS)
    assert r["score"] == cat_pts + 30 + 20 and r["tier"] == tier


@pytest.mark.parametrize("location,mode,pts", [
    ("Beer Sheva", "onsite", 30), ("Omer", None, 30), ("Tel Aviv", "hybrid", 30), ("Tel Aviv", "remote", 30),
    ("Tel Aviv", None, 15), ("Herzliya", "onsite", 10), ("Haifa", "remote", 30), ("Haifa", "onsite", 5),
    ("Jerusalem", "hybrid", 5), (None, None, 15), (None, "remote", 30)])
def test_location_rules(location, mode, pts):
    assert score_job(J(location=location, mode=mode), PREFS)["score"] == 50 + pts + 20


@pytest.mark.parametrize("seniority,years,pts", [
    (None, None, 20), ("senior", 6, 20), ("mid", 3, 20), (None, 7, 8), (None, 8, 8), (None, 9, 0),
    ("junior", 1, 5), ("lead", 5, 8), ("lead", 10, 0)])
def test_experience_rules(seniority, years, pts):
    assert score_job(J(seniority=seniority, years=years), PREFS)["score"] == 50 + 30 + pts


def test_any_rust_role_even_junior():
    r = score_job(J("rust", location="Tel Aviv", mode="remote", seniority="junior", years=1), PREFS)
    assert r["tier"] == "match" and r["category"] == "rust" and r["cv"] == PREFS.targets["rust"].cv


def test_secondary_category_is_capped():
    r = score_job(J("fullstack,backend", location="Ramat Gan"), PREFS)
    assert r["category"] == "backend" and r["score"] == PREFS.secondary_points + 30 + 20 and r["tier"] == "maybe"


def test_low_confidence_category_is_ignored():
    p = J("data")
    p.categories.append(CategoryScore(category="embedded", confidence=0.4))
    r = score_job(p, PREFS)
    assert r["category"] is None and r["tier"] == "skip"


def test_non_target_category_is_skip():
    r = score_job(J("devops"), PREFS)
    assert r["tier"] == "skip" and r["category"] is None and r["cv"] is None


def test_tie_prefers_earlier_target():
    r = score_job(J("embedded"), PREFS)  # only one category: its own CV
    assert r["category"] == "embedded"


def test_suspicious_caps_match_to_maybe():
    r = score_job(J(), PREFS, suspicious=True)
    assert r["tier"] == "maybe" and r["score"] == 100 and len(r["reasons"]) >= 4


def test_reads_numbers_from_prefs():
    p2 = PREFS.model_copy(deep=True)
    p2.thresholds.match = 101
    assert score_job(J(), p2)["tier"] == "maybe"
    p2.location.rules[0].points = 0
    assert score_job(J(), p2)["score"] == 70

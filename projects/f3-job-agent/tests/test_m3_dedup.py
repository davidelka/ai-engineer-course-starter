"""M3: dedup across sources (mine.job_fingerprint, mine.near_duplicate)."""

import re

import pytest

from jobagent.models import CategoryScore, JobPosting
from mine import job_fingerprint, near_duplicate


def J(title, company=None, location=None, **kw):
    return JobPosting(title=title, company=company, location=location,
                      categories=[CategoryScore(category="backend", confidence=0.9)], **kw)


def test_fingerprint_shape_and_stability():
    fp = job_fingerprint(J("Backend Engineer", "Negev Robotics", "Beer Sheva"))
    assert re.fullmatch(r"[0-9a-f]{16}", fp)
    assert fp == job_fingerprint(J("Backend Engineer", "Negev Robotics", "Beer Sheva"))


def test_fingerprint_matches_the_documented_recipe():
    import hashlib
    from jobagent.dedup import normalize_company, normalize_contact, normalize_location, normalize_title
    j = J("Senior Backend Developer", "CyberDome", "Beer Sheva")
    key = f"{normalize_title(j.title)}|{normalize_company(j.company)}|{normalize_location(j.location)}"
    assert job_fingerprint(j) == hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    k = J("Backend Engineer", None, "Tel Aviv", apply="CV@cobaltpay.example")
    key = f"{normalize_title(k.title)}|{normalize_contact(k.apply)}|{normalize_location(k.location)}"
    assert job_fingerprint(k) == hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def test_anonymous_jobs_are_told_apart_by_contact():
    a = J("Backend Engineer", None, "Tel Aviv", apply="cv@cobaltpay.example")
    b = J("Backend Engineer", None, "Tel Aviv", apply="https://ferrumlabs.example/careers/backend-go")
    assert job_fingerprint(a) != job_fingerprint(b)


@pytest.mark.parametrize("a,b", [
    (J("Senior Back-End Developer", "CyberDome Ltd.", "Beer Sheva"), J("Developer, Senior Backend", "cyberdome", "beer sheva")),
    (J("Backend Engineer", "Helios Defense", "Beer Sheva"), J("backend developer", "HELIOS DEFENSE", "Beer Sheva")),
    (J("מפתח/ת Backend", None, None), J("מפתח Backend", None, None)),
])
def test_fingerprint_ignores_wording(a, b):
    assert job_fingerprint(a) == job_fingerprint(b)


def test_fingerprint_separates_different_roles():
    assert job_fingerprint(J("Backend Engineer", "SkyCore", "Herzliya")) != job_fingerprint(J("Backend Engineer", "SkyCore", "Haifa"))
    assert job_fingerprint(J("Backend Engineer", "SkyCore")) != job_fingerprint(J("Frontend Engineer", "SkyCore"))


def test_near_duplicate_same_role_other_source():
    wa = J("Senior Backend Engineer", "Negev Robotics", "Beer Sheva")
    at = J("Senior Backend Developer", "Negev Robotics Ltd", "Beer Sheva")
    assert near_duplicate(wa, at) and near_duplicate(at, wa)


def test_near_duplicate_location_unknown_on_one_side():
    assert near_duplicate(J("Backend Engineer", "Helios Defense", "Beer Sheva"), J("Backend Engineer", "Helios Defense"))


def test_not_duplicate_different_city():
    assert not near_duplicate(J("Backend Engineer", "Ferrum Labs", "Tel Aviv"), J("Backend Engineer", "Ferrum Labs", "Haifa"))


def test_not_duplicate_different_seniority():
    # the bug the reference had at first: "Junior Rust Developer" swallowed "Rust Engineer"
    assert not near_duplicate(J("Rust Engineer", "Ferrum Labs", "Tel Aviv"), J("Junior Rust Developer", "Ferrum Labs", "Tel Aviv"))
    assert not near_duplicate(J("Backend Team Lead", "SkyCore"), J("Backend Engineer", "SkyCore"))


def test_not_duplicate_different_company():
    assert not near_duplicate(J("Backend Engineer", "SkyCore", "Herzliya"), J("Backend Engineer", "Datanest", "Herzliya"))


def test_unknown_company_needs_identical_title():
    assert near_duplicate(J("Embedded Software Engineer", None, "Dimona"), J("Embedded Software Engineer", "AgroSense", "Dimona"))
    assert not near_duplicate(J("Embedded Software Engineer", None, "Dimona"), J("Embedded Linux Engineer", None, "Dimona"))


def test_title_threshold_is_used():
    a, b = J("Backend Platform Engineer", "SkyCore"), J("Backend Engineer", "SkyCore")
    assert near_duplicate(a, b, title_threshold=0.6)
    assert not near_duplicate(a, b, title_threshold=0.9)


def test_unknown_company_different_apply_is_not_duplicate():
    a = J("Backend Engineer", None, "Tel Aviv", apply="cv@cobaltpay.example")
    b = J("Backend Engineer", None, "Tel Aviv", apply="https://ferrumlabs.example/careers/backend-go")
    assert not near_duplicate(a, b)
    assert near_duplicate(a, J("Backend Engineer", "Cobalt Pay", "Tel Aviv", apply="CV@cobaltpay.example"))

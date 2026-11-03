"""Exercise 5: ACL by classification x role (mine.acl_allows), and where it runs."""

import pytest

import mine
from guardkit import Answerer, ObedientModel, User
from guardkit.defenses import AclFilter
from guardkit.evaluate import attack_succeeded, load_attacks

MATRIX = {
    # role:        public internal confidential(engineering) confidential(hr) confidential(sales_support)
    "contractor":  (True, False, False, False, False),
    "employee":    (True, True, False, False, False),
    "support":     (True, True, False, False, True),
    "engineering": (True, True, True, False, False),
    "hr":          (True, True, False, True, False),
    "security":    (True, True, True, True, True),
}
METAS = [
    {"classification": "public", "department": "company"},
    {"classification": "internal", "department": "hr"},
    {"classification": "confidential", "department": "engineering"},
    {"classification": "confidential", "department": "hr"},
    {"classification": "confidential", "department": "sales_support"},
]


@pytest.mark.parametrize("role", list(MATRIX))
def test_matrix(role):
    got = tuple(mine.acl_allows(role, m) for m in METAS)
    assert got == MATRIX[role]


@pytest.mark.parametrize("meta", [
    {"classification": "restricted", "department": "hr"},
    {"department": "engineering"},
    {"classification": "", "department": "engineering"},
    {"classification": None},
    {"classification": "confidental", "department": "engineering"},
])
def test_fail_closed_on_bad_classification(meta):
    assert all(not mine.acl_allows(r, meta) for r in MATRIX)


def test_unknown_role_sees_nothing():
    assert not mine.acl_allows("ceo", {"classification": "public"})
    assert not mine.acl_allows("", {"classification": "public"})


def test_classification_is_normalized():
    assert mine.acl_allows("employee", {"classification": " Internal ", "department": "hr"})
    assert mine.acl_allows("engineering", {"classification": "CONFIDENTIAL", "department": "engineering"})


def _attack(aid):
    return next(a for a in load_attacks() if a["id"] == aid)


@pytest.mark.parametrize("aid", ["a01", "a02", "a03", "a04"])
def test_leak_attacks_blocked_by_your_acl(aid):
    """The real answerer, with YOUR acl_allows as the only defense: no confidential fact leaks."""
    a = _attack(aid)
    user = User("u", a["role"], f"{a['role']}@acme.example")
    undefended = Answerer(ObedientModel(), []).ask(a["question"], user)
    assert attack_succeeded(a, undefended)[0], "sanity: without an ACL this attack leaks"
    defended = Answerer(ObedientModel(), [AclFilter(mine.acl_allows)]).ask(a["question"], user)
    assert not attack_succeeded(a, defended)[0]
    assert defended.acl_removed, "the ACL should have removed chunks from the candidate set"


def test_engineer_still_gets_the_postmortem():
    user = User("u", "engineering", "eng@acme.example")
    tr = Answerer(ObedientModel(), [AclFilter(mine.acl_allows)]).ask(
        "What was the root cause of the August 19 flow-api outage?", user)
    assert any(c.doc_id == "eng-pm-2026-08-api" for c in tr.retrieved)

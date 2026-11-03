"""Exercise 2: the spec linter."""

from pathlib import Path

import pytest

from mine import lint_spec
from spectools.spec import parse_spec

SPEC = Path(__file__).resolve().parent.parent / "spec"


def keys(findings):
    return {(f.rule, f.req_id) for f in findings}


def one(text):
    return parse_spec("# T\n\n## 3. Requirements\n\n" + text)


GOOD = """### REQ-1: Create
**Statement:** WHEN a caller posts a valid body, THE SYSTEM SHALL respond 201.
**Acceptance criteria:**
- AC-1.1: GIVEN a valid body WHEN it is posted THEN the response is 201.
"""


def test_good_requirement_has_no_findings():
    assert lint_spec(one(GOOD)) == []


def test_the_example_spec_is_clean():
    assert lint_spec(parse_spec(SPEC / "access-requests.spec.md")) == []


def test_missing_id():
    f = lint_spec(one(GOOD.replace("REQ-1: Create", "Create things")))
    assert ("missing-id", None) in keys(f)


def test_duplicate_id_reports_the_later_one():
    f = lint_spec(one(GOOD + "\n" + GOOD.replace("Create", "Again")))
    assert [x.rule for x in f] == ["duplicate-id"]
    assert f[0].req_id == "REQ-1"


@pytest.mark.parametrize("statement", [
    "The system should respond 201.",                        # no SHALL
    "Respond 201, THE SYSTEM SHALL.",                         # does not start with an EARS keyword
    "Whenever a caller posts, THE SYSTEM SHALL respond 201.", # "Whenever" is not "WHEN "
])
def test_not_ears(statement):
    f = lint_spec(one(GOOD.replace("WHEN a caller posts a valid body, THE SYSTEM SHALL respond 201.", statement)))
    assert ("not-ears", "REQ-1") in keys(f)


@pytest.mark.parametrize("start", ["THE SYSTEM SHALL respond 201.", "while busy, the system shall queue it.",
                                   "IF the body is invalid, THEN THE SYSTEM SHALL respond 422.",
                                   "WHERE audit is on, THE SYSTEM SHALL log it."])
def test_ears_forms_pass(start):
    f = lint_spec(one(GOOD.replace("WHEN a caller posts a valid body, THE SYSTEM SHALL respond 201.", start)))
    assert "not-ears" not in {x.rule for x in f}


def test_weak_modal_is_a_warning_and_names_the_word():
    f = lint_spec(one(GOOD.replace("SHALL respond 201.", "SHALL respond 201 and may log it.")))
    w = [x for x in f if x.rule == "weak-modal"]
    assert len(w) == 1 and w[0].severity == "warning" and '"may"' in w[0].message


def test_vague_words_in_statement_and_criteria():
    f = lint_spec(one(GOOD.replace("respond 201.", "respond quickly with the appropriate code.")
                      .replace("THEN the response is 201", "THEN some response is shown, etc.")))
    msgs = sorted(x.message for x in f if x.rule == "vague-word")
    assert msgs == ['"appropriate" in statement', '"etc" in AC-1.1', '"quickly" in statement', '"some" in AC-1.1']
    assert all(x.severity == "error" for x in f if x.rule == "vague-word")


def test_word_boundaries():
    # "breakfast" contains "fast", "somewhere" contains "some", "fastest"... none of them is a match
    f = lint_spec(one(GOOD.replace("a valid body", "a breakfast order from somewhere")))
    assert f == []


def test_multiword_entries():
    f = lint_spec(one(GOOD.replace("respond 201.", "respond 201 as needed in a User-Friendly way.")))
    assert sorted(x.message for x in f) == ['"as needed" in statement', '"user-friendly" in statement']


def test_no_criteria_and_missing_statement():
    f = lint_spec(one("### REQ-1: Nothing here\n\nJust prose.\n"))
    assert keys(f) == {("missing-statement", "REQ-1"), ("no-criteria", "REQ-1")}


def test_criterion_not_gwt():
    f = lint_spec(one(GOOD.replace("GIVEN a valid body WHEN it is posted THEN", "WHEN it is posted GIVEN a valid body THEN")))
    assert keys(f) == {("criterion-not-gwt", "REQ-1")}


def test_nfr_needs_a_number():
    text = """## 4. Non-functional requirements

### NFR-1: Latency
**Statement:** THE SYSTEM SHALL answer within budget.
**Acceptance criteria:**
- AC-N1.1: GIVEN load WHEN measured THEN p95 is at most 50 ms.
"""
    f = lint_spec(parse_spec("# T\n\n" + text))
    assert keys(f) == {("nfr-not-measurable", "NFR-1")}
    f = lint_spec(parse_spec("# T\n\n" + text.replace("within budget", "within 50 ms at p95")))
    assert f == []


def test_the_vague_draft():
    f = lint_spec(parse_spec(SPEC / "draft-vague.spec.md"))
    assert keys(f) == {
        ("vague-word", "REQ-1"),
        ("missing-id", None),
        ("vague-word", "REQ-3"), ("criterion-not-gwt", "REQ-3"), ("duplicate-id", "REQ-3"),
        ("not-ears", "REQ-4"), ("weak-modal", "REQ-4"), ("vague-word", "REQ-4"), ("no-criteria", "REQ-4"),
        ("vague-word", "NFR-1"), ("nfr-not-measurable", "NFR-1"),
    }
    assert len([x for x in f if x.rule == "vague-word"]) == 12

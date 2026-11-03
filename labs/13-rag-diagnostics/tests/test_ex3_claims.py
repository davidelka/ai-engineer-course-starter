"""Exercise 3: claim-level groundedness, offline (ragkit.replay answers the two structured calls)."""
import json

import pytest

import mine
from ragkit.diagnose import (DECOMPOSE_MARKER, VERIFY_MARKER, Claims, ClaimVerdict, ClaimVerdicts,
                             heuristic_judge_llm)
from ragkit.replay import body_text, replay_llm

CTX = ["## Carry-over\n\n- Up to 5 unused days may be carried over to the next calendar year. "
       "Carried-over days expire on March 31.",
       "## Requesting vacation\n\n- Requests of 3 days or more must be submitted 2 weeks in advance."]


def scripted(claims, verdicts, calls):
    """A replay LLM that returns fixed claims and verdicts, and records which calls were made."""
    def respond(body):
        system, user = body_text(body)
        if DECOMPOSE_MARKER in system:
            calls.append("decompose")
            return Claims(claims=claims).model_dump_json()
        if VERIFY_MARKER in system:
            calls.append("verify")
            assert "<sources>" in user and "<claims>" in user
            return ClaimVerdicts(verdicts=[ClaimVerdict(**v) for v in verdicts]).model_dump_json()
        return "{}"
    return replay_llm(respond)


def test_refusal_makes_no_call():
    calls = []
    llm = scripted([], [], calls)
    for ans in ("not in the documents", "Not in the documents.", "   "):
        rep = mine.check_claims(ans, CTX, llm)
        assert rep.refusal and rep.claims == [] and rep.label == "grounded"
    assert calls == []


def test_two_calls_and_evidence_verification():
    calls = []
    llm = scripted(
        [" Up to 5 days can be carried over ", "They expire on March 31", "Unused days can be cashed out", ""],
        [{"claim": "Up to 5 days can be carried over", "evidence": "Up to 5 unused days may be carried over",
          "source": 1, "verdict": "supported"},
         {"claim": "They expire on March 31", "evidence": "Carried-over days expire on April 30",   # invented
          "source": 1, "verdict": "supported"},
         {"claim": "Unused days can be cashed out", "evidence": None, "source": None, "verdict": "not_found"}],
        calls)
    rep = mine.check_claims("Up to 5 days carry over [1]. They expire on March 31 [1]. Cash out [1].", CTX, llm)
    assert calls == ["decompose", "verify"]
    assert [c.claim for c in rep.claims] == ["Up to 5 days can be carried over", "They expire on March 31",
                                             "Unused days can be cashed out"]
    assert [c.verdict for c in rep.claims] == ["supported", "supported", "not_found"]
    assert [c.evidence_verified for c in rep.claims] == [True, False, None]
    assert [c.supported for c in rep.claims] == [True, False, False]
    assert rep.score == pytest.approx(1 / 3)
    assert rep.label == "partially_grounded"
    assert rep.cost_usd > 0                                    # replay estimates Haiku's price


def test_missing_verdict_counts_as_not_found():
    calls = []
    llm = scripted(["A", "B"], [{"claim": "A", "evidence": "Up to 5 unused days", "source": 1, "verdict": "supported"}],
                   calls)
    rep = mine.check_claims("A. B.", CTX, llm)
    assert [c.verdict for c in rep.claims] == ["supported", "not_found"]
    assert rep.label == "partially_grounded"


def test_no_claims_skips_the_second_call():
    calls = []
    rep = mine.check_claims("Hello!", CTX, scripted([], [], calls))
    assert calls == ["decompose"] and rep.claims == [] and rep.score is None


def test_structured_error_is_reported_not_raised():
    llm = replay_llm(lambda body: "this is not json")
    rep = mine.check_claims("Up to 5 days [1].", CTX, llm)
    assert rep.error and rep.label is None and rep.claims == []


def test_offline_heuristic_judge_on_the_examples(claim_examples):
    """The lexical judge: catches the invented sentence of e2, and is blind to translation (e4)."""
    j = heuristic_judge_llm()
    by = {e["id"]: mine.check_claims(e["answer"], [c["text"] for c in e["contexts"]], j) for e in claim_examples}
    assert by["e2"].label == "partially_grounded"
    assert any("two hours" in c.claim for c in by["e2"].unsupported)
    assert by["e3"].label == "grounded"            # grounded in a stale document: still "grounded"
    assert by["e4"].label == "not_grounded"        # English answer, Hebrew source: lexical cannot see it

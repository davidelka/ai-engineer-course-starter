"""Exercise 4: the handoff contract (what MUST be passed to the next agent)."""
import pytest

import mine
from multikit.handoff import HandoffError

TASK = "Who is on call for flow-api? Dana Levi wants admin on aws-production for 3 days. Open the request, but do not file it before Friday."


def good(**kw):
    s = {"original_request": TASK, "goal": "Handle the access part for Dana Levi.",
         "facts": [{"claim": "flow-api is covered by core-api-oncall", "source": "get_oncall_for_service"}],
         "actions_taken": [], "constraints": ["Open the request, but do not file it before Friday."], "open_questions": []}
    s.update(kw)
    return s


def problems(summary, task=TASK, se=()):
    with pytest.raises(HandoffError) as e:
        mine.make_handoff_brief(summary, task, list(se), from_agent="oncall", to_agent="it_access")
    return e.value.problems


def test_good_summary_renders_the_brief():
    text = mine.make_handoff_brief(good(), TASK, [], from_agent="oncall", to_agent="it_access")
    assert text.startswith('<handoff from="oncall" to="it_access">') and text.endswith("</handoff>")
    assert "<original_request>\n" + TASK + "\n</original_request>" in text
    assert "- flow-api is covered by core-api-oncall (source: get_oncall_for_service)" in text
    assert "<actions_taken>\n- (none)\n</actions_taken>" in text


def test_whitespace_and_case_do_not_matter():
    mine.make_handoff_brief(good(original_request="  " + TASK.upper().replace(" ", "   ") + "\n"), TASK, [])


def test_paraphrase_is_rejected():
    p = problems(good(original_request="Who is on call for flow-api? Dana wants AWS admin. Open the request."))
    assert p[0] == "original_request must be the user's message verbatim"


def test_lost_constraint_is_rejected():
    p = problems(good(constraints=[]))
    assert p == ["constraint missing: 'do not file it before Friday'"]


def test_constraint_may_be_part_of_a_longer_item():
    mine.make_handoff_brief(good(constraints=["User said: DO NOT file it before Friday (wait)"]), TASK, [])


def test_facts_need_claim_and_source():
    p = problems(good(facts=[{"claim": "x", "source": ""}, {"claim": " ", "source": "tool"}]))
    assert p == ["fact 1 has no source", "fact 2 has no claim"]


def test_side_effects_must_be_reported():
    se = [{"id": "AR-00007", "system": "figma"}, {"system": "no id"}]
    assert problems(good(), se=se) == ["actions_taken does not mention AR-00007"]
    mine.make_handoff_brief(good(actions_taken=["Filed AR-00007 (figma editor)"]), TASK, se)


def test_all_problems_are_collected_in_order():
    p = problems({"original_request": "something else", "goal": "", "facts": [], "actions_taken": [],
                  "constraints": [], "open_questions": []}, se=[{"id": "AR-1"}])
    assert p == ["original_request must be the user's message verbatim", "goal is empty",
                 "constraint missing: 'do not file it before Friday'", "actions_taken does not mention AR-1"]


def test_handoff_chain_with_your_contract_stops_a_lossy_summary():
    from multikit import build
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        r = build("handoff", requests_db=Path(d) / "r.db", confirm=lambda c: True, lossy=True,
                  brief=mine.make_handoff_brief).run(TASK, task_id="h01")
    filed = [c for rec in r.records if rec.get("type") == "step" for c in rec["calls"] if c["name"] == "create_access_request"]
    assert r.info["rejected"] and not filed and r.info["chain"] == ["triage", "oncall", "it_access"]

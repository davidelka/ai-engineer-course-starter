"""Exercise 3: node functions, tested directly with a fake LLM, then inside the graph."""
import json

import mine
from flowkit import FakeLLM, store
from flowkit.nodes import call_tool

GOOD = json.dumps({"employee": None, "system": "figma", "access_level": "editor", "external_sharing": False,
                   "duration_days": None, "justification": "dashboard designs"})


def base_state(**kw):
    return {"thread_id": "n1", "requester": "dana.levi@acme.example", "text": "I need a Figma editor seat",
            "status": "received", "audit": [], **kw}


def test_intake_extracts_and_defaults_employee_to_sender(lab):
    llm = FakeLLM(replies=[GOOD])
    out = mine.intake_node(base_state(), lab.deps(llm))
    assert out["status"] == "extracted"
    assert out["request"]["system"] == "figma" and out["request"]["access_level"] == "editor"
    assert out["request"]["employee"] == "dana.levi@acme.example"
    assert out["usage"]["calls"] == 1 and out["audit"][0]["to_status"] == "extracted"
    sent = llm.calls[0]
    assert sent.response_schema is not None  # native structured output, not "please return JSON"
    assert "<request>" in sent.messages[0].content and "dana.levi@acme.example" in sent.messages[0].content


def test_intake_repairs_once_then_gives_up(lab):
    bad = json.dumps({"system": "figma", "access_level": "superuser", "external_sharing": False})
    out = mine.intake_node(base_state(), lab.deps(FakeLLM(replies=[bad, GOOD])))
    assert out["status"] == "extracted" and out["usage"]["calls"] == 2
    out = mine.intake_node(base_state(), lab.deps(FakeLLM(replies=[bad, bad])))
    assert out["status"] == "needs_info" and "invalid" in out["error"]
    assert out["audit"][0]["to_status"] == "needs_info"


def enriched(lab, level="editor", system="figma", external=False, who="dana.levi@acme.example"):
    d = lab.deps()
    emp = call_tool(d, "lookup_employee", {"employee": who})
    return base_state(requester=who, request={"employee": who, "system": system, "access_level": level,
                                              "external_sharing": external, "duration_days": None,
                                              "justification": "work"},
                      employee=emp, requester_info=emp, system_info=call_tool(d, "get_system_info", {"system": system}),
                      status="enriched"), d


def test_policy_node_is_deterministic(lab):
    st, d = enriched(lab)
    out = mine.policy_node(st, d)
    assert out["route"] == "needs_manager" and out["status"] == "routed"
    assert out["policy"]["policy_version"] == "2.2"
    st, d = enriched(lab, level="admin")
    assert mine.policy_node(st, d)["route"] == "needs_security"
    st, d = enriched(lab, level="member", system="google-workspace", external=True)
    assert mine.policy_node(st, d)["route"] == "needs_security"


def test_file_request_is_idempotent(lab):
    st, d = enriched(lab)
    st = {**st, **mine.policy_node(st, d)}
    first = mine.file_request_node(st, d)
    second = mine.file_request_node(st, d)  # the node ran twice: retry or resume
    assert first["status"] == second["status"] == "pending_manager"
    assert first["record"]["id"] == second["record"]["id"]
    assert second["record"]["deduplicated"] is True
    dump = store.dump(lab.db)
    assert len(dump["access_requests"]) == 1
    assert len(dump["audit"]) == 1  # same event id -> one durable audit row
    ev = first["audit"][0]
    assert {"request_id", "actor", "from_status", "to_status"} <= set(ev)  # SPEC-006 REQ-11
    assert ev["from_status"] is None and ev["actor"] == "system"


def test_file_request_raises_route_for_external_sharing(lab):
    st, d = enriched(lab, level="member", system="google-workspace", external=True, who="alon.sasson@acme.example")
    st = {**st, **mine.policy_node(st, d)}
    out = mine.file_request_node(st, d)
    assert out["status"] == "pending_security"
    assert store.get_request(lab.db, out["record"]["id"])["status"] == "pending_security"


def test_graph_with_your_nodes(lab):
    app = lab.app("ex3")
    for tid in ("r1", "r2", "r4", "r6", "r8"):
        out = lab.run(app, tid, tid)
        assert out["status"] == lab.samples[tid]["expect_status"], tid

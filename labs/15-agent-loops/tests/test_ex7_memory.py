"""Exercise 7: clearing old tool results without breaking the conversation."""
import mine
from agentkit import AcmeHeuristic, Agent, FakeLLM
from agentkit.memory import is_cleared
from llmkit.types import Block, Message, ToolCall, ToolResult
from toolkit import acme_registry

DANA = ("Dana Levi asks for admin access on AWS production for 3 days to debug the billing outage. Who is her "
        "manager, what does the policy say, and open the request (it goes to whatever track the policy requires).")


def convo():
    return [
        Message("user", "the task"),
        Message("assistant", [Block("Looking up."), ToolCall("c1", "lookup_employee", {"employee": "E016"}),
                              ToolCall("c2", "check_policy", {"system": "figma"})], raw=["raw1"], raw_provider="anthropic"),
        Message("user", [ToolResult("c1", "A" * 400, name="lookup_employee"),
                         ToolResult("c2", "bad args", is_error=True, name="check_policy"), Block("extra text")]),
        Message("assistant", [ToolCall("c3", "check_policy", {"system": "figma", "access_level": "editor"})]),
        Message("user", [ToolResult("c3", {"route": "needs_manager"}, name="check_policy")]),
        Message("assistant", [ToolCall("c4", "list_access_grants", {"employee": "E016"})]),
        Message("user", [ToolResult("c4", "G" * 300, name="list_access_grants")]),
    ]


def test_keep_last_two():
    msgs = convo()
    out, n = mine.clear_old_tool_results(msgs, keep=2)
    assert n == 2 and len(out) == len(msgs)
    old = out[2]
    assert [r.call_id for r in old.tool_results] == ["c1", "c2"]
    assert [r.is_error for r in old.tool_results] == [False, True]
    assert [r.name for r in old.tool_results] == ["lookup_employee", "check_policy"]
    assert all(is_cleared(r) for r in old.tool_results) and "400 chars" in old.tool_results[0].content
    assert old.content[-1].text == "extra text"  # other parts stay
    assert out[4].tool_results[0].content == {"route": "needs_manager"} and out[6].tool_results[0].content == "G" * 300
    assert out[1] is msgs[1] and out[1].raw == ["raw1"]  # assistant turns untouched (raw replay keeps working)


def test_input_not_modified():
    msgs = convo()
    before = [r.content for m in msgs for r in m.tool_results]
    mine.clear_old_tool_results(msgs, keep=1)
    assert [r.content for m in msgs for r in m.tool_results] == before


def test_keep_zero_and_idempotent():
    out, n = mine.clear_old_tool_results(convo(), keep=0)
    assert n == 4 and all(is_cleared(r) for m in out for r in m.tool_results)
    again, n2 = mine.clear_old_tool_results(out, keep=0)
    assert n2 == 0 and [r.content for m in again for r in m.tool_results] == [r.content for m in out for r in m.tool_results]


def test_keep_more_than_exists():
    msgs = convo()
    out, n = mine.clear_old_tool_results(msgs, keep=10)
    assert n == 0 and all(a is b for a, b in zip(out, msgs))


def test_inside_an_agent(tmp_path):
    reg = acme_registry(requests_db=tmp_path / "r.db")
    r = Agent(FakeLLM(AcmeHeuristic()), reg, confirm=lambda c: True, keep_tool_results=1,
              trim=mine.clear_old_tool_results).run(DANA)
    assert r.stop_reason == "repetition"  # it forgot, so it re-fetched
    r = Agent(FakeLLM(AcmeHeuristic()), reg, confirm=lambda c: True, keep_tool_results=1, scratchpad=True,
              trim=mine.clear_old_tool_results).run(DANA)
    assert r.stop_reason == "final_answer" and "Michal Ben-David" in r.text
    ids = [p.call_id for m in r.messages for p in m.tool_results]
    calls = [c.id for m in r.messages for c in m.tool_calls]
    assert ids == calls  # every call still has its result: the history stays valid

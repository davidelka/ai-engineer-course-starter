"""Exercise 4: the tool-calling loop for one question, against mockllm."""
import json

import pytest

import mine

PROVIDERS = ["anthropic", "openai", "gemini"]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_one_round_then_answer(mock, reg, make_llm, provider):
    _, url = mock
    res = mine.run_tool_loop(make_llm(url, provider), "Look up employee dana.levi@acme.example", reg)
    assert res.stop == "answer" and res.rounds == 1 and res.model_calls == 2
    assert [c.name for c in res.calls] == ["lookup_employee"]
    assert "Dana Levi" in res.text and res.input_tokens > 0 and res.cost_usd > 0
    assert [m.role for m in res.messages] == ["user", "assistant", "user", "assistant"]


def test_parallel_results_in_one_message(mock, reg, make_llm):
    server, url = mock
    server.state.cfg.tool_script = json.dumps([{"match": "compare", "calls": [
        {"name": "get_system_info", "arguments": {"system": "figma"}},
        {"name": "get_system_info", "arguments": {"system": "salesforce"}}]}])
    res = mine.run_tool_loop(make_llm(url), "compare figma and salesforce", reg)
    assert res.rounds == 1 and len(res.calls) == 2
    user_turn = res.messages[2]
    assert len(user_turn.tool_results) == 2  # both results, one message
    assert [r.call_id for r in user_turn.tool_results] == [c.id for c in res.calls]


def test_chained_rounds(mock, reg, make_llm):
    server, url = mock
    server.state.cfg.tool_script = json.dumps([{"match": "approve", "calls": [
        {"name": "lookup_employee", "arguments": {"employee": "dana.levi@acme.example"}}],
        "then": [[{"name": "check_policy", "arguments": {"system": "figma", "access_level": "editor",
                                                         "external_sharing": False,
                                                         "holds_customer_or_financial_data": None}}]]}])
    res = mine.run_tool_loop(make_llm(url), "Who would approve Figma editor for Dana?", reg)
    assert [c.name for c in res.calls] == ["lookup_employee", "check_policy"] and res.rounds == 2
    assert "needs_manager" in res.text


@pytest.mark.parametrize("fault", ["invalid_args", "unknown_tool"])
def test_recovers_from_errors(mock, reg, make_llm, fault):
    server, url = mock
    server.state.cfg.tool_fault, server.state.cfg.tool_fault_first = fault, 1
    res = mine.run_tool_loop(make_llm(url), "Look up employee dana.levi@acme.example", reg)
    assert res.results[0].is_error and not res.results[-1].is_error
    assert res.stop == "answer" and "Dana Levi" in res.text


def test_loop_is_bounded(mock, reg, make_llm):
    server, url = mock
    server.state.cfg.tool_fault, server.state.cfg.tool_fault_rate = "loop", 1.0
    res = mine.run_tool_loop(make_llm(url), "Look up employee dana.levi@acme.example", reg, max_rounds=3)
    assert res.stop == "max_rounds" and res.rounds == 3 and res.model_calls == 4
    assert res.messages[-1].role == "user" and res.messages[-1].tool_results  # no dangling tool calls


def test_custom_executor_is_used(mock, reg, make_llm):
    _, url = mock
    seen = []

    def run(calls):
        seen.extend(calls)
        from llmkit.types import ToolResult
        return [ToolResult(c.id, {"name": "Stub Person"}, name=c.name) for c in calls]

    res = mine.run_tool_loop(make_llm(url), "Look up employee dana.levi@acme.example", reg, executor=run)
    assert len(seen) == 1 and "Stub Person" in res.text

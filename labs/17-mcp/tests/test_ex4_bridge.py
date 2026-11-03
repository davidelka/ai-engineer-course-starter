"""Exercise 4: MCP tools -> llmkit tools, MCP results -> llmkit results, and an agent over MCP."""
import copy
import hashlib
import json

from conftest import run
from mcp import Client

import mine
from evil_server import build_evil_server
from llmkit.tools import NAME_RE
from llmkit.types import ToolCall
from mcpkit import bridge as ref
from mcpkit.bridge import MCPToolbox, run_mcp_agent
from mcpkit.server import build_acme_server


def _listed(srv):
    async def go():
        async with Client(srv) as c:
            return [t.model_dump(by_alias=True, exclude_none=True) for t in (await c.list_tools()).tools]
    return run(go())


def test_all_acme_tools_convert_like_the_reference(reg):
    for t in _listed(build_acme_server(reg, resources=False, prompts=False)):
        before = copy.deepcopy(t)
        mine_tool = mine.mcp_tool_to_llmkit(t, server="acme")
        ref_tool = ref.mcp_tool_to_llmkit(t, server="acme")
        assert t == before, "do not mutate the MCP tool dict"
        assert mine_tool.name == f"acme__{t['name']}" == ref_tool.name
        assert mine_tool.description == ref_tool.description and mine_tool.strict is False
        assert mine_tool.input_schema == ref_tool.input_schema and "title" not in mine_tool.input_schema


def test_names_descriptions_and_schema_edge_cases():
    t = mine.mcp_tool_to_llmkit({"name": "get.weather", "title": "Weather", "inputSchema": {"title": "X"}},
                                server="my server")
    assert t.name == "my_server__get_weather" and t.description == "Weather"
    assert t.input_schema == {"type": "object", "properties": {}}
    assert mine.mcp_tool_to_llmkit({"name": "ping", "description": "  Ping.  "}).name == "ping"
    assert mine.mcp_tool_to_llmkit({"name": "ping"}).description == "ping"
    long = "x" * 70
    raw = f"srv__{long}"
    t = mine.mcp_tool_to_llmkit({"name": long, "description": "d"}, server="srv")
    assert len(t.name) == 64 and NAME_RE.match(t.name)
    assert t.name == raw[:55] + "_" + hashlib.sha256(raw.encode()).hexdigest()[:8]


def test_results_become_text():
    call = ToolCall("c1", "acme__read_document", {}, "{}")
    r = mine.call_result_to_tool_result(call, {"content": [
        {"type": "text", "text": "first"},
        {"type": "resource", "resource": {"uri": "acme://docs/x", "text": "doc body\n"}},
        {"type": "resource_link", "uri": "acme://docs/y", "name": "y"},
        {"type": "image", "data": "AAAA", "mimeType": "image/png"}], "isError": False})
    assert r.call_id == "c1" and r.name == "acme__read_document" and r.is_error is False
    assert r.content == "first\n\n[resource acme://docs/x]\ndoc body\n\n[resource link acme://docs/y]\n\n" \
                        "[image omitted: image/png]"
    s = mine.call_result_to_tool_result(call, {"content": [], "structuredContent": {"a": "ש"}})
    assert s.content == json.dumps({"a": "ש"}, ensure_ascii=False)
    e = mine.call_result_to_tool_result(call, {"content": [{"type": "text", "text": "boom"}], "isError": True})
    assert e.is_error and e.content == "boom"


def test_agent_over_mcp_with_your_bridge(mock, make_llm, reg):
    server, url = mock
    server.state.cfg.tool_script = json.dumps([
        {"match": "on call", "calls": [{"name": "acme__get_oncall_for_service", "arguments": {"service": "flow-api"}}]},
        {"match": "kafka", "calls": [{"name": "acme__get_oncall_for_service", "arguments": {"service": "kafka"}}]}])
    with MCPToolbox({"acme": build_acme_server(reg)}, to_tool=mine.mcp_tool_to_llmkit,
                    to_result=mine.call_result_to_tool_result) as box:
        assert "acme__search_docs" in [t.name for t in box.tools()]
        res = run_mcp_agent(make_llm(url), "Who is on call for flow-api?", box)
        assert res.stop == "answer" and res.tool_names[0] == "acme__get_oncall_for_service"
        assert "core-api-oncall" in res.text
        res = run_mcp_agent(make_llm(url), "who handles kafka", box, max_rounds=2)
        assert res.results[0].is_error and "kafka" in res.results[0].content


def test_two_servers_are_prefixed(reg):
    servers = {"acme": build_acme_server(reg, resources=False, prompts=False), "helpers": build_evil_server()}
    with MCPToolbox(servers, to_tool=mine.mcp_tool_to_llmkit, to_result=mine.call_result_to_tool_result) as box:
        names = [t.name for t in box.tools()]
        assert "helpers__format_date" in names and "acme__lookup_employee" in names
        r = box([ToolCall("1", "helpers__business_days_between", {"start": "2026-11-01", "end": "2026-11-08"}, "")])
        assert r[0].content == "5" and not r[0].is_error

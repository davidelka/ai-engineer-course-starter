"""Exercises 4 and 5: Company Brain (llmkit + Haiku) using acme-mcp through MCP.

    python labs/17-mcp/agent.py --model mock "Who is on call for billing-service?"
    python labs/17-mcp/agent.py --set                                   # 5 questions on Haiku 5.5, ~1-2 cents
    python labs/17-mcp/agent.py --set --mine                            # your bridge from mine.py
    python labs/17-mcp/agent.py --allow-write "File a Figma editor request for dana.levi@acme.example, she needs it for design reviews"
    python labs/17-mcp/agent.py --server http://127.0.0.1:8765/mcp --token-env ACME_MCP_TOKEN --set

--server: stdio (default: launches `python -m mcpkit` as a subprocess, like Claude Code does),
          inproc (same process, no transport), or an http(s) URL (Streamable HTTP).
create_access_request is hidden unless --allow-write (least privilege). With --allow-write the
SERVER asks you to confirm in this terminal (elicitation); the model never sees your answer.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import _lab
from mcpkit.bridge import HttpTarget, MCPToolbox, run_mcp_agent, terminal_elicitation

QUESTIONS = [
    "Who is on call for billing-service, when is the handover, and is there a runbook?",
    "Who would have to approve a Figma editor seat for dana.levi@acme.example, and why?",
    "How many vacation days can I carry over into 2026, and until when?",
    "What access does Sapir Golan have today?",
    "Which rotation covers flow-scheduler, and what does its runbook say to do first when triggers are late?",
]

MOCK_SCRIPT = [  # the mock is a keyword router, not a model: these rules make it call sensible tools
    {"match": "on call for billing", "calls": [{"name": "acme__get_oncall_for_service", "arguments": {"service": "billing-service"}}]},
    {"match": "on call for flow-api", "calls": [{"name": "acme__get_oncall_for_service", "arguments": {"service": "flow-api"}}]},
    {"match": "Figma editor seat", "calls": [{"name": "acme__lookup_employee", "arguments": {"employee": "dana.levi@acme.example"}}],
     "then": [[{"name": "acme__check_policy", "arguments": {"system": "figma", "access_level": "editor", "external_sharing": False}}]]},
    {"match": "vacation", "calls": [{"name": "acme__search_docs", "arguments": {"query": "vacation carry over 2026"}}]},
    {"match": "Sapir Golan", "calls": [{"name": "acme__list_access_grants", "arguments": {"employee": "Sapir Golan", "include_expired": False}}]},
    {"match": "flow-scheduler", "calls": [{"name": "acme__get_oncall_for_service", "arguments": {"service": "flow-scheduler"}}],
     "then": [[{"name": "acme__read_document", "arguments": {"doc_id": "eng-oncall-scheduler-he"}}]]},
    {"match": "File a Figma", "calls": [{"name": "acme__create_access_request", "arguments": {
        "employee": "dana.levi@acme.example", "system": "figma", "access_level": "editor",
        "justification": "design reviews", "idempotency_key": "dana.levi@acme.example:figma:editor"}}]},
]

p = argparse.ArgumentParser()
p.add_argument("question", nargs="?")
p.add_argument("--set", action="store_true", help="run the 5 built-in questions")
p.add_argument("--model", default=_lab.DEFAULT_MODEL, help="'mock' for the free offline path")
p.add_argument("--server", default="stdio")
p.add_argument("--token-env", default=None, help="env var holding a bearer token for an http server")
p.add_argument("--mine", action="store_true", help="use mine.mcp_tool_to_llmkit / call_result_to_tool_result")
p.add_argument("--allow-write", action="store_true", help="offer create_access_request (asks you to confirm)")
p.add_argument("--max-rounds", type=int, default=6)
a = p.parse_args()
if not a.set and not a.question:
    p.error("give a question or --set")

llm = _lab.make_llm(a.model, {"tool_script": json.dumps(MOCK_SCRIPT)} if a.model.startswith("mock") else None)
db = Path(tempfile.mkdtemp()) / "requests.db"  # demo writes never touch your lab 14 store
if a.server == "inproc":
    from toolkit import acme_registry
    from mcpkit.server import build_acme_server
    target = build_acme_server(acme_registry(requests_db=db))
elif a.server == "stdio":
    target = f"stdio:python -m mcpkit --requests-db {db}"
else:
    headers = {}
    if a.token_env:
        tok = os.environ.get(a.token_env) or sys.exit(f"{a.token_env} is not set")
        headers["Authorization"] = f"Bearer {tok}"
    target = HttpTarget(a.server, headers)

kw = {}
if a.mine:
    import mine
    kw = {"to_tool": mine.mcp_tool_to_llmkit, "to_result": mine.call_result_to_tool_result}
exclude = () if a.allow_write else ("acme__create_access_request",)
total = 0.0
with MCPToolbox({"acme": target}, elicitation=terminal_elicitation(), exclude=exclude, **kw) as box:
    proto = box.clients["acme"].protocol_version
    print(f"connected: {a.server} (protocol {proto}), {len(box.tools())} tools offered to {a.model}")
    for q in (QUESTIONS if a.set else [a.question]):
        r = run_mcp_agent(llm, q, box, max_rounds=a.max_rounds)
        total += r.cost_usd
        print(f"\nQ: {q}")
        for c, res in zip(r.calls, r.results):
            flag = "ERROR " if res.is_error else ""
            print(f"   -> {c.name}({json.dumps(c.arguments, ensure_ascii=False)[:90]})  {flag}{res.text[:90]!r}")
        print(f"A: {r.text.strip()}")
        print(f"   [{r.stop}, {r.rounds} tool rounds, {r.model_calls} model calls, "
              f"{r.input_tokens} in / {r.output_tokens} out tokens, ${r.cost_usd:.4f}]")
print(f"\ntotal cost: ${total:.4f}")

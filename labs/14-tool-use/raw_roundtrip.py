"""Exercise 1: one full tool round trip over plain HTTP. No SDK, no llmkit loop.

    python labs/14-tool-use/raw_roundtrip.py                    # Claude Haiku 5.5 (needs ANTHROPIC_API_KEY)
    python labs/14-tool-use/raw_roundtrip.py --mock             # free: the local mock server
    python labs/14-tool-use/raw_roundtrip.py --parallel         # a question that needs two calls at once
    python labs/14-tool-use/raw_roundtrip.py --provider openai  # the same round trip in OpenAI's shapes
    python labs/14-tool-use/raw_roundtrip.py --mock --provider gemini

Prints every JSON body: request 1 (with tools), the reply with the tool call, what YOUR
code ran, request 2 (with the result), and the final answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

import _lab  # noqa: F401  (paths)
from _lab import ROOT
from llmkit import load_dotenv
from llmkit.types import ToolCall
from toolkit import acme_registry, execute_tool

MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-5.4-mini", "gemini": "gemini-3.6-flash"}
Q1 = "Who is the manager of dana.levi@acme.example, and what is her title?"
Q2 = "Compare the systems figma and salesforce: owner team and whether each is sensitive."
SYSTEM = "You answer questions about Acme employees and systems. Use the tools; never guess."


def show(title, obj):
    print(f"\n===== {title}\n" + json.dumps(obj, indent=2, ensure_ascii=False)[:4000])


def tools_for(provider, reg, names):
    out = []
    for t in reg.tools(names=names, strict=False):
        if provider == "anthropic":
            out.append({"name": t.name, "description": t.description, "input_schema": t.input_schema})
        elif provider == "openai":
            out.append({"type": "function", "name": t.name, "description": t.description,
                        "parameters": t.input_schema, "strict": False})
        else:
            out.append({"name": t.name, "description": t.description, "parametersJsonSchema": t.input_schema})
    return [{"functionDeclarations": out}] if provider == "gemini" else out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(MODELS), default="anthropic")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--parallel", action="store_true")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    reg = acme_registry(requests_db=_lab.requests_db())
    names = ["lookup_employee", "get_system_info"]
    question = Q2 if a.parallel else Q1
    env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}[a.provider]
    key = "mock" if a.mock else os.environ.get(env, "")
    if not key:
        sys.exit(f"{env} is not set in .env (or use --mock)")
    if a.mock:
        from mockllm import MockConfig, start_in_thread
        rules = [{"match": "compare", "calls": [{"name": "get_system_info", "arguments": {"system": "figma"}},
                                                {"name": "get_system_info", "arguments": {"system": "salesforce"}}]}]
        _, base = start_in_thread(MockConfig(ttft=0, tps=0, tool_script=json.dumps(rules)))
        model = "mock-model"
    else:
        base = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com",
                "gemini": "https://generativelanguage.googleapis.com"}[a.provider]
        model = MODELS[a.provider]
    tools = tools_for(a.provider, reg, names)
    http = httpx.Client(timeout=60)

    if a.provider == "anthropic":
        url, headers = base + "/v1/messages", {"x-api-key": key, "anthropic-version": "2023-06-01",
                                               "content-type": "application/json"}
        body = {"model": model, "max_tokens": 1024, "system": SYSTEM, "tools": tools,
                "messages": [{"role": "user", "content": question}]}
    elif a.provider == "openai":
        url, headers = base + "/v1/responses", {"authorization": f"Bearer {key}", "content-type": "application/json"}
        body = {"model": model, "instructions": SYSTEM, "tools": tools, "max_output_tokens": 1500,
                "input": [{"role": "user", "content": question}]}
    else:
        url = base + f"/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": key, "content-type": "application/json"}
        body = {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "tools": tools,
                "contents": [{"role": "user", "parts": [{"text": question}]}]}

    show("REQUEST 1 (tools are part of the prompt)", body)
    r = http.post(url, headers=headers, json=body)
    if r.status_code >= 400:
        sys.exit(f"HTTP {r.status_code}: {r.text[:800]}")
    reply = r.json()
    show("REPLY 1 (the model only REQUESTS a call; nothing ran yet)", reply)

    # Find the calls in the provider's own shape.
    if a.provider == "anthropic":
        calls = [ToolCall(b["id"], b["name"], b["input"]) for b in reply["content"] if b["type"] == "tool_use"]
        print(f"\nstop_reason = {reply.get('stop_reason')}")
    elif a.provider == "openai":
        calls = [ToolCall(i["call_id"], i["name"], json.loads(i["arguments"])) for i in reply["output"]
                 if i["type"] == "function_call"]
    else:
        parts = reply["candidates"][0]["content"]["parts"]
        calls = [ToolCall(p["functionCall"].get("id", ""), p["functionCall"]["name"], p["functionCall"].get("args", {}))
                 for p in parts if "functionCall" in p]
    if not calls:
        print("\nThe model answered without tools.")
        return
    results = []
    for c in calls:
        res = execute_tool(c, reg)  # YOUR code runs the tool: validation, timeout, errors as data
        print(f"\n>>> your code ran {c.name}({json.dumps(c.arguments)}) -> is_error={res.is_error}\n    {res.text[:300]}")
        results.append(res)

    if a.provider == "anthropic":
        body["messages"] += [{"role": "assistant", "content": reply["content"]},
                             {"role": "user", "content": [
                                 {"type": "tool_result", "tool_use_id": res.call_id, "content": res.text,
                                  **({"is_error": True} if res.is_error else {})} for res in results]}]
    elif a.provider == "openai":
        body["input"] += reply["output"] + [{"type": "function_call_output", "call_id": res.call_id,
                                             "output": res.text} for res in results]
    else:
        body["contents"] += [{"role": "model", "parts": parts},  # thoughtSignature travels back untouched
                             {"role": "user", "parts": [{"functionResponse": {
                                 "name": res.name, "response": json.loads(res.text) if not res.is_error
                                 else {"error": res.text}}} for res in results]}]
    show("REQUEST 2 (the conversation so far + the results)", body)
    r = http.post(url, headers=headers, json=body)
    if r.status_code >= 400:
        sys.exit(f"HTTP {r.status_code}: {r.text[:800]}")
    reply = r.json()
    show("REPLY 2 (final answer)", reply)
    u = reply.get("usage") or reply.get("usageMetadata")
    print(f"\nusage of the second call: {u}")


if __name__ == "__main__":
    main()

"""Tool calling for mockllm (lesson 14).

When a request carries tools, the mock behaves like a (very simple) model that uses them:

1. A user question arrives. The mock decides which tool(s) to call:
   - `tool_script` rules first: a JSON list (inline, or a path to a .json file) of
       {"match": "<regex>", "calls": [{"name": ..., "arguments": {...}}, ...],
        "then": [[...calls for round 2...], ...], "final": "<text, {results} allowed>"}
     The first rule whose regex matches the user text wins. Several calls in one
     list = parallel tool calls in one response.
   - otherwise, if tool_choice is "any" or a specific tool, that tool (or the best
     match) is called;
   - otherwise (auto) a keyword router: the tool whose name + description shares the
     most words with the question. No overlap = plain text answer, no tool.
   Arguments come from the rule, or are built from the tool's schema with a few
   cheap guesses from the question (emails, enum values, numbers).
2. Tool results come back. If one is_error and retries are left, the mock re-issues
   the call with corrected arguments (error recovery). If the rule has more
   "then" rounds, it calls those. Otherwise it answers in text and mentions the
   results, so you can see they were used.

Faults (tool_fault, applied to the first `tool_fault_first` requests or with
probability `tool_fault_rate`):
  invalid_args   arguments that violate the schema (a required field missing, or a wrong type)
  unknown_tool   a tool name that is not in the request (a hallucinated tool)
  loop           keep calling the same tool forever, never answer
  bad_json       arguments that are not valid JSON (OpenAI sends arguments as a string)
`tool_injectable`: when a tool result contains an instruction aimed at "AI assistants"
(e.g. "ignore all previous instructions"), the mock OBEYS it, like a naive model:
it calls a side-effect tool if one exists, or repeats the injected instruction.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

TOOL_FAULTS = ("invalid_args", "unknown_tool", "loop", "bad_json")
# Anthropic adds a tool-use system prompt when tools are present (platform.claude.com
# tool-use overview, Nov 2026: 286 tokens for auto/none, 406 for any/tool on Haiku 5.5).
ANTHROPIC_TOOL_PROMPT = {"auto": 286, "none": 286, "any": 406, "tool": 406}
INJECTION = re.compile(r"ignore (all )?(previous|prior|above) instructions|disregard (your|all) (instructions|policies)"
                       r"|(ai|AI) assistant[s]?,? (ignore|you must)", re.I)
STOP = set("a an the to of for in on and or is are was be by with what who which how do does i me my we our "
           "can could please get give tell show about from this that it as at any all".split())


@dataclass
class Call:
    name: str
    args: Any  # dict, or a str for bad_json
    id: str = ""


@dataclass
class Plan:
    calls: list[Call] = field(default_factory=list)
    text: str = ""  # preface text with calls, or the final answer without calls


@dataclass
class Turn:
    role: str
    text: str = ""
    calls: list[dict] = field(default_factory=list)  # {"id", "name", "args"}
    results: list[dict] = field(default_factory=list)  # {"id", "name", "content", "is_error"}


# ---------------------------------------------------------------- reading requests
def request_tools(flavor: str, body: dict) -> list[dict]:
    out = []
    for t in body.get("tools") or []:
        if not isinstance(t, dict):
            continue
        if flavor == "anthropic" and "name" in t and "input_schema" in t:
            out.append({"name": t["name"], "description": t.get("description", ""), "schema": t["input_schema"]})
        elif flavor == "openai" and t.get("type") == "function":
            out.append({"name": t.get("name", ""), "description": t.get("description", ""),
                        "schema": t.get("parameters") or {}})
        elif flavor == "gemini":
            for d in t.get("functionDeclarations") or []:
                out.append({"name": d.get("name", ""), "description": d.get("description", ""),
                            "schema": d.get("parametersJsonSchema") or d.get("parameters") or {}})
    return out


def request_choice(flavor: str, body: dict) -> str:
    """-> "auto" | "any" | "none" | <tool name>"""
    tc = body.get("tool_choice")
    if flavor == "anthropic":
        if not isinstance(tc, dict):
            return "auto"
        return tc.get("name", "auto") if tc.get("type") == "tool" else tc.get("type", "auto")
    if flavor == "openai":
        if tc is None:
            return "auto"
        if isinstance(tc, str):
            return {"required": "any"}.get(tc, tc)
        return tc.get("name", "auto")
    cfg = ((body.get("toolConfig") or {}).get("functionCallingConfig") or {})
    mode = cfg.get("mode", "AUTO")
    names = cfg.get("allowedFunctionNames") or []
    if mode == "ANY":
        return names[0] if len(names) == 1 else "any"
    return "none" if mode == "NONE" else "auto"


def _block_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return json.dumps(content, ensure_ascii=False)


def conversation(flavor: str, body: dict) -> list[Turn]:
    turns: list[Turn] = []

    def turn(role: str) -> Turn:
        if not turns or turns[-1].role != role:
            turns.append(Turn(role))
        return turns[-1]

    if flavor == "anthropic":
        for m in body.get("messages") or []:
            t = turn(m.get("role", "user"))
            c = m.get("content")
            if isinstance(c, str):
                t.text += c
                continue
            for b in c or []:
                if b.get("type") == "text":
                    t.text += b.get("text", "")
                elif b.get("type") == "tool_use":
                    t.calls.append({"id": b.get("id"), "name": b.get("name"), "args": b.get("input")})
                elif b.get("type") == "tool_result":
                    t.results.append({"id": b.get("tool_use_id"), "content": _block_text(b.get("content", "")),
                                      "is_error": bool(b.get("is_error"))})
    elif flavor == "openai":
        inp = body.get("input")
        for it in ([{"role": "user", "content": inp}] if isinstance(inp, str) else inp or []):
            kind = it.get("type")
            if kind == "function_call":
                args = it.get("arguments", "")
                try:
                    args = json.loads(args)
                except (TypeError, json.JSONDecodeError):
                    pass
                turn("assistant").calls.append({"id": it.get("call_id"), "name": it.get("name"), "args": args})
            elif kind == "function_call_output":
                out = it.get("output", "")
                turn("user").results.append({"id": it.get("call_id"), "content": _block_text(out),
                                             "is_error": str(out).startswith("ERROR")})
            elif kind == "reasoning":
                continue
            elif "role" in it:
                c = it.get("content")
                if isinstance(c, list):
                    c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
                turn(it["role"]).text += str(c or "")
    else:
        for c in body.get("contents") or []:
            t = turn("assistant" if c.get("role") == "model" else "user")
            for p in c.get("parts") or []:
                if "text" in p:
                    t.text += p["text"]
                elif "functionCall" in p:
                    fc = p["functionCall"]
                    t.calls.append({"id": fc.get("id"), "name": fc.get("name"), "args": fc.get("args")})
                elif "functionResponse" in p:
                    fr = p["functionResponse"]
                    resp = fr.get("response") or {}
                    t.results.append({"id": fr.get("id"), "name": fr.get("name"),
                                      "content": json.dumps(resp, ensure_ascii=False),
                                      "is_error": isinstance(resp, dict) and "error" in resp})
    return turns


# ---------------------------------------------------------------- validation (real-API-like 400s)
def validate(flavor: str, body: dict) -> Optional[tuple[int, str]]:
    if flavor == "anthropic":
        msgs = body.get("messages") or []
        for i, m in enumerate(msgs):
            c = m.get("content")
            if m.get("role") != "assistant" or not isinstance(c, list):
                continue
            ids = [b.get("id") for b in c if isinstance(b, dict) and b.get("type") == "tool_use"]
            if not ids:
                continue
            nxt = msgs[i + 1] if i + 1 < len(msgs) else None
            got = []
            if nxt and isinstance(nxt.get("content"), list):
                blocks = nxt["content"]
                got = [b.get("tool_use_id") for b in blocks if b.get("type") == "tool_result"]
                kinds = [b.get("type") for b in blocks]
                if "tool_result" in kinds and "text" in kinds and kinds.index("text") < len(kinds) - 1 - kinds[::-1].index("tool_result"):
                    return 400, (f"messages.{i + 1}: tool_result blocks must come FIRST in the content array; "
                                 "any text must come after all tool results")
                extra = [x for x in got if x not in ids]
                if extra:
                    return 400, (f"messages.{i + 1}.content: unexpected `tool_use_id` found in `tool_result` blocks: "
                                 f"{', '.join(extra)}. Each `tool_result` block must have a corresponding `tool_use` "
                                 "block in the previous message.")
            missing = [x for x in ids if x not in got]
            if missing and nxt is not None:
                return 400, (f"messages.{i}: `tool_use` ids were found without `tool_result` blocks immediately after: "
                             f"{', '.join(missing)}. Each `tool_use` block must have a corresponding `tool_result` "
                             "block in the next message.")
        for t in body.get("tools") or []:
            if isinstance(t, dict) and "input_schema" in t and not re.match(r"^[a-zA-Z0-9_-]{1,128}$", t.get("name", "")):
                return 400, f"tools: name {t.get('name')!r} does not match '^[a-zA-Z0-9_-]{{1,128}}$'"
    elif flavor == "openai":
        inp = body.get("input")
        if isinstance(inp, list):
            seen = set()
            for it in inp:
                if it.get("type") == "function_call":
                    seen.add(it.get("call_id"))
                elif it.get("type") == "function_call_output" and it.get("call_id") not in seen:
                    return 400, f"No tool call found for function call output with call_id {it.get('call_id')}."
    else:
        contents = body.get("contents") or []
        # The current turn starts at the last user message with plain text.
        start = 0
        for i, c in enumerate(contents):
            if c.get("role") != "model" and any("text" in p for p in c.get("parts") or []):
                start = i
        for c in contents[start:]:
            if c.get("role") != "model":
                continue
            fcs = [p for p in c.get("parts") or [] if "functionCall" in p]
            if fcs and not fcs[0].get("thoughtSignature"):
                return 400, ("Function call is missing a thought_signature in functionCall parts. This is required "
                             "for tools to work correctly, and missing thought_signature may lead to degraded model "
                             "performance. Additional data, function call `default_api:"
                             f"{fcs[0]['functionCall'].get('name')}` , position 1.")
    return None


# ---------------------------------------------------------------- deciding
def load_script(spec: str) -> list[dict]:
    if not spec:
        return []
    if not spec.lstrip().startswith("[") and os.path.exists(spec):
        with open(spec, encoding="utf-8") as f:
            spec = f.read()
    rules = json.loads(spec)
    if not isinstance(rules, list):
        raise ValueError("tool_script must be a JSON list of rules")
    return rules


def _words(s: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-zA-Z0-9]+", (s or "").lower().replace("_", " ")):
        if w not in STOP and len(w) > 2:
            out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


def route(question: str, tools: list[dict]) -> Optional[dict]:
    """A toy router: the tool sharing the most words with the question. Like a real
    model, it only knows what the NAME and DESCRIPTION say."""
    q = _words(question)
    best, score = None, 0
    for t in tools:
        s = len(q & _words(t["name"] + " " + t["description"]))
        if s > score:
            best, score = t, s
    return best


def _resolve(schema: dict, root: dict) -> dict:
    if "$ref" in schema:
        defs = root.get("$defs") or root.get("definitions") or {}
        return _resolve(defs.get(schema["$ref"].split("/")[-1], {}), root)
    return schema


def sample_args(schema: dict, question: str = "") -> dict:
    """Valid-looking arguments for a tool schema, with cheap guesses from the question."""
    from .server import sample_from_schema
    base = sample_from_schema(schema) if schema else {}
    if not isinstance(base, dict):
        return {}
    props = schema.get("properties", {})
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", question or "")
    number = re.search(r"\b(\d{1,4})\b", question or "")
    ql = (question or "").lower()
    for k, p in props.items():
        p = _resolve(p, schema)
        opts = p.get("anyOf") or [p]
        enum = next((o.get("enum") for o in opts if "enum" in o), None)
        types = {o.get("type") for o in opts}
        if enum:
            hit = next((e for e in enum if isinstance(e, str) and e.lower().replace("_", " ") in ql), None)
            if hit:
                base[k] = hit
        elif email and "string" in types and ("email" in k or k in ("employee", "user", "requester", "person")
                                               or "email" in (p.get("description") or "").lower()):
            base[k] = email.group(0)
        elif "integer" in types and number:
            base[k] = int(number.group(1))
        elif "string" in types and base.get(k) in ("example", None) and k in ("system", "system_name", "tool"):
            hit = re.search(r"\b(jira|confluence|slack|github|figma|miro|zoom|notion|salesforce|zendesk|netsuite|"
                            r"datadog|pagerduty|aws-production|kubernetes-prod|google-workspace|1password)\b", ql)
            if hit:
                base[k] = hit.group(1)
    return base


def break_args(args: dict, schema: dict) -> dict:
    """invalid_args: drop the first required field, or put a wrong type in the first field."""
    args = dict(args)
    req = [r for r in schema.get("required", []) if r in args]
    if req:
        args.pop(req[0])
    elif args:
        k = next(iter(args))
        args[k] = 12345 if isinstance(args[k], str) else "not-a-number"
    else:
        args["unexpected"] = True
    return args


def _faulty(cfg, n: int, rng) -> str:
    if cfg.tool_fault and (n <= cfg.tool_fault_first or rng.random() < cfg.tool_fault_rate):
        return cfg.tool_fault
    return ""


def _rule_for(question: str, rules: list[dict]) -> Optional[dict]:
    for r in rules:
        try:
            if re.search(r.get("match", ""), question or "", re.I):
                return r
        except re.error:
            continue
    return None


def _calls(spec: list[dict]) -> list[Call]:
    return [Call(c["name"], dict(c.get("arguments") or {})) for c in spec]


def _shorten(s: str, n: int = 220) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 3] + "..."


def plan(flavor: str, body: dict, cfg, n: int, rng) -> Optional[Plan]:
    tools = request_tools(flavor, body)
    if not tools:
        return None
    choice = request_choice(flavor, body)
    if choice == "none":
        return None
    by_name = {t["name"]: t for t in tools}
    turns = conversation(flavor, body)
    if not turns:
        return None
    rules = load_script(cfg.tool_script)
    # The question = the last user turn that had text and no tool results.
    q_idx = max((i for i, t in enumerate(turns) if t.role == "user" and t.text and not t.results), default=0)
    question = turns[q_idx].text
    rule = _rule_for(question, rules)
    fault = _faulty(cfg, n, rng)
    last = turns[-1]

    def first_calls() -> list[Call]:
        if rule:
            calls = _calls(rule.get("calls") or [])
        else:
            if choice not in ("auto", "any"):
                tool = by_name.get(choice)
            else:
                tool = route(question, tools) if cfg.tool_router else None
                if tool is None and choice == "any":
                    tool = tools[0]
            calls = [Call(tool["name"], sample_args(tool["schema"], question))] if tool else []
        if choice not in ("auto", "any") and calls:
            calls = [c for c in calls if c.name == choice] or [Call(choice, sample_args(by_name[choice]["schema"], question))]
        return calls

    def apply_fault(calls: list[Call]) -> list[Call]:
        if not calls or fault in ("", "loop"):
            return calls
        c = calls[0]
        schema = by_name.get(c.name, {}).get("schema", {})
        if fault == "invalid_args":
            calls[0] = Call(c.name, break_args(c.args, schema))
        elif fault == "unknown_tool":
            base = c.name.split("_", 1)[-1]
            bad = "find_" + base if "find_" + base not in by_name else c.name + "_v2"
            calls[0] = Call(bad, c.args)
        elif fault == "bad_json":
            text = json.dumps(c.args)
            calls[0] = Call(c.name, text[: max(1, len(text) // 2)]) if flavor == "openai" else Call(
                c.name, break_args(c.args, schema))
        return calls

    if not last.results:  # a fresh question
        calls = apply_fault(first_calls())
        if not calls:
            return None
        return Plan(calls, "")

    # ---- tool results came back
    rounds = sum(1 for t in turns[q_idx + 1:] if t.role == "assistant" and t.calls)
    prev_calls = next((t.calls for t in reversed(turns) if t.role == "assistant" and t.calls), [])
    if fault == "loop":
        c = prev_calls[0] if prev_calls else {"name": tools[0]["name"], "args": {}}
        return Plan([Call(c["name"], c.get("args") or {})], "Let me check that again.")

    if cfg.tool_injectable:
        hit = next((r for r in last.results if INJECTION.search(r["content"] or "")), None)
        if hit:
            action = next((t for t in tools if re.match(r"(create|send|delete|update|grant|share)_", t["name"])), None)
            if action and rounds < 3:
                args = sample_args(action["schema"], hit["content"])
                return Plan([Call(action["name"], args)], "Following the instructions in the document.")
            m = INJECTION.search(hit["content"])
            injected = _shorten(hit["content"][m.end():], 300)
            return Plan([], f"Following the new instructions: {injected}")

    errors = [r for r in last.results if r.get("is_error")]
    if errors and rounds <= cfg.tool_max_retries:
        fixed: list[Call] = []
        good = first_calls() if not rule else _calls((rule.get("calls") or []))
        for r in errors:
            call = next((c for c in prev_calls if c.get("id") == r.get("id") and r.get("id")), None) or \
                next((c for c in prev_calls if c.get("name") == r.get("name")), None) or (prev_calls[0] if prev_calls else None)
            name = call["name"] if call else ""
            if name not in by_name:  # unknown tool: switch to the right one
                fixed += good[:1] or [Call(tools[0]["name"], sample_args(tools[0]["schema"], question))]
                continue
            replacement = next((g for g in good if g.name == name), None)
            fixed.append(replacement or Call(name, sample_args(by_name[name]["schema"], question)))
        if fixed:
            return Plan(fixed, f"The previous call failed ({_shorten(errors[0]['content'], 120)}). "
                               "Retrying with corrected arguments.")

    steps = (rule or {}).get("then") or []
    done_steps = rounds - 1 - sum(1 for t in turns[q_idx + 1:] if t.role == "user" and any(r.get("is_error") for r in t.results))
    if rule and 0 <= done_steps < len(steps):
        return Plan(_calls(steps[done_steps]), "")

    summary = "; ".join(f"{r.get('name') or _name_for(r, turns)} returned {_shorten(r['content'])}" for r in last.results)
    if errors:
        text = f"I could not complete the request. The tool reported an error: {_shorten(errors[0]['content'], 200)}"
    elif rule and rule.get("final"):
        text = rule["final"].replace("{results}", summary)
    else:
        text = f"Based on the tool results: {summary}."
    return Plan([], text)


def _name_for(result: dict, turns: list[Turn]) -> str:
    for t in turns:
        for c in t.calls:
            if c.get("id") and c.get("id") == result.get("id"):
                return c.get("name", "tool")
    return "the tool"


# ---------------------------------------------------------------- response bodies
def new_ids(flavor: str, calls: list[Call]) -> None:
    for c in calls:
        h = uuid.uuid4().hex[:20]
        c.id = {"anthropic": f"toolu_mock_{h}", "openai": f"call_{h}"}.get(flavor, "")


def args_text(c: Call) -> str:
    return c.args if isinstance(c.args, str) else json.dumps(c.args, ensure_ascii=False)


def anthropic_content(p: Plan) -> list[dict]:
    blocks = [{"type": "text", "text": p.text}] if p.text else []
    for c in p.calls:
        blocks.append({"type": "tool_use", "id": c.id, "name": c.name,
                       "input": c.args if isinstance(c.args, dict) else {}})
    return blocks


def openai_output(p: Plan) -> list[dict]:
    out = []
    if p.text:
        out.append({"type": "message", "id": f"msg_{uuid.uuid4().hex[:16]}", "status": "completed", "role": "assistant",
                    "content": [{"type": "output_text", "text": p.text, "annotations": []}]})
    for c in p.calls:
        out.append({"type": "function_call", "id": "fc_" + c.id[5:], "call_id": c.id, "name": c.name,
                    "arguments": args_text(c), "status": "completed"})
    return out


def gemini_parts(p: Plan) -> list[dict]:
    parts = [{"text": p.text}] if p.text else []
    for i, c in enumerate(p.calls):
        part = {"functionCall": {"name": c.name, "args": c.args if isinstance(c.args, dict) else {}}}
        if i == 0:  # like the real API: the signature rides on the FIRST functionCall part only
            part["thoughtSignature"] = "bW9jay1zaWduYXR1cmU" + uuid.uuid4().hex[:8]
        parts.append(part)
    return parts


def chunks(s: str, size: int = 12) -> list[str]:
    return [s[i:i + size] for i in range(0, len(s), size)] or [""]

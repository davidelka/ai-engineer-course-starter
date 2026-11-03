"""A local stand-in for three LLM APIs, with fault injection.

Speaks enough of each wire format for llmkit, raw_http.py and the tests:
  POST /v1/messages                               Anthropic (JSON or SSE)
  POST /v1/responses                              OpenAI Responses (JSON or SSE)
  POST /v1beta/models/{m}:generateContent         Gemini
  POST /v1beta/models/{m}:streamGenerateContent   Gemini SSE
Admin:
  GET  /__admin/stats     request and failure counters
  POST /__admin/config    change faults at runtime (JSON body, same names as MockConfig)
  POST /__admin/reset     zero the counters (and empty the prompt cache)

Prompt caching (lesson 4) is simulated: Anthropic cache_control breakpoints (block
level or top-level automatic) with 5m/1h lifetimes, a 20-block lookback and a minimum
prefix size; OpenAI and Gemini cache repeated prefixes automatically. Usage fields
(cache_read_input_tokens, cached_tokens, cachedContentTokenCount...) look like the real
ones. prefill_tps adds a delay per UNCACHED prompt token, so cache hits are faster.

Tool calling (lesson 14, see mockllm/tools.py): when a request carries tools, the mock
answers with provider-shaped tool calls (Anthropic tool_use blocks, OpenAI function_call
items, Gemini functionCall parts), chosen by `tool_script` rules or a keyword router, and
answers in text once the results come back. Faults: invalid_args, unknown_tool, loop,
bad_json; `tool_injectable` makes it obey instructions hidden in tool results.

Images and documents (lesson 21, see mockllm/vision.py): image / document blocks in each
provider's shape are measured from their bytes, validated like the real APIs (type mismatch,
size, page limits) and billed with the provider's image-token formula. The answer reports
what was seen; an optional "oracle" payload inside an image makes structured extraction
return plausible, resolution-dependent values offline.

Costs nothing, needs no key, and fails exactly how you tell it to.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, fields
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from . import tools as tooling
from . import vision


@dataclass
class MockConfig:
    reply: str = ""  # fixed answer; empty = echo-style answer built from the question
    latency: float = 0.0  # seconds before any response bytes (use a big value to test timeouts)
    ttft: float = 0.05  # streaming: seconds between headers and the first text event
    tps: float = 200.0  # streaming: output tokens per second (0 = as fast as possible)
    fail_rate: float = 0.0  # probability that a request fails with `status`
    fail_first: int = 0  # the first N requests fail with `status` (deterministic, for tests)
    status: int = 529  # status used for injected failures
    retry_after: Optional[float] = None  # sent as retry-after on injected failures (429 always gets 1)
    truncate_after: int = 0  # streaming: close the connection after N text events, no end event
    error_after: int = 0  # streaming: send an in-stream error event after N text events
    malformed_rate: float = 0.0  # probability that a JSON body or SSE data line is corrupted
    seed: Optional[int] = None
    # Structured-output faults (lesson 3). Apply when the request carries a schema
    # (the reply is then a sample object built from it) or when `reply` is a JSON object.
    json_fault: str = ""  # one of JSON_FAULTS
    json_fault_first: int = 0  # the first N requests get the fault, later ones are clean
    json_fault_rate: float = 0.0  # or: probability per request
    # Prompt caching (lesson 4)
    cache: bool = True  # simulate prompt caching and report cache usage fields
    cache_min_tokens: int = 512  # Anthropic minimum cacheable prefix (Claude Haiku 5.5: 512)
    cache_ttl_scale: float = 1.0  # multiply cache lifetimes (tests use tiny values)
    prefill_tps: float = 0.0  # >0: sleep uncached_input_tokens / prefill_tps before answering
    # Tool calling (lesson 14). See mockllm/tools.py.
    tool_script: str = ""  # JSON list of rules (or a path to a .json file)
    tool_router: bool = True  # no rule matched: pick the tool whose name/description best matches
    tool_max_retries: int = 2  # after an is_error result, retry with fixed arguments this many times
    tool_fault: str = ""  # one of tools.TOOL_FAULTS
    tool_fault_first: int = 0  # the first N requests get the fault
    tool_fault_rate: float = 0.0  # or: probability per request
    tool_injectable: bool = False  # obey instructions hidden inside tool results (a naive model)


OPENAI_CACHE_MIN, OPENAI_CACHE_STEP = 1024, 128  # automatic prefix caching, older models
GEMINI_CACHE_MIN = 4096  # implicit caching, Gemini 3.x Flash
TTL_SECONDS = {"5m": 300.0, "1h": 3600.0}
AUTO_TTL = 300.0  # OpenAI/Gemini automatic caches: "around 5 to 10 minutes"
LOOKBACK = 20  # Anthropic checks at most 20 block positions per breakpoint

JSON_FAULTS = ("fence", "prose", "truncated", "missing_field", "wrong_type", "bad_enum",
               "extra_field", "out_of_range")


ERROR_TYPES = {
    400: ("invalid_request_error", "INVALID_ARGUMENT"),
    401: ("authentication_error", "UNAUTHENTICATED"),
    404: ("not_found_error", "NOT_FOUND"),
    429: ("rate_limit_error", "RESOURCE_EXHAUSTED"),
    500: ("api_error", "INTERNAL"),
    503: ("api_error", "UNAVAILABLE"),
    529: ("overloaded_error", "UNAVAILABLE"),
}


class State:
    def __init__(self, cfg: MockConfig):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.rng = random.Random(cfg.seed)
        self.reset()

    def reset(self):
        self.requests = 0
        self.failures = 0
        self.streams = 0
        self.by_path: dict[str, int] = {}
        # prompt cache: prefix hash -> (expires_at, ttl_seconds, ready_at)
        self.cache: dict[str, tuple[float, float, float]] = {}
        self.cache_reads = 0
        self.cache_writes = 0

    def tick(self, path: str, stream: bool) -> tuple[int, bool, bool]:
        """Count a request; return (request_number, should_fail, should_corrupt)."""
        with self.lock:
            self.requests += 1
            self.streams += stream
            key = path.split("?")[0]
            self.by_path[key] = self.by_path.get(key, 0) + 1
            n = self.requests
            fail = n <= self.cfg.fail_first or self.rng.random() < self.cfg.fail_rate
            corrupt = self.rng.random() < self.cfg.malformed_rate
            if fail:
                self.failures += 1
            return n, fail, corrupt

    def stats(self) -> dict:
        with self.lock:
            return {"requests": self.requests, "failures": self.failures, "streams": self.streams,
                    "by_path": dict(self.by_path), "cache_entries": len(self.cache),
                    "cache_reads": self.cache_reads, "cache_writes": self.cache_writes,
                    "config": asdict(self.cfg)}


def approx_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


# ---------------------------------------------------------------- prompt caching
def _text_of(content) -> list[tuple[str, Optional[str]]]:
    """Content (str or list of blocks) -> [(text, cache_ttl or None)], one per block."""
    if isinstance(content, str):
        return [(content, None)]
    out = []
    for b in content or []:
        if not isinstance(b, dict):
            continue
        cc = b.get("cache_control")
        ttl = (cc.get("ttl") or "5m") if isinstance(cc, dict) else None
        text = b.get("text") if b.get("type") == "text" else json.dumps(b, sort_keys=True)
        out.append((text or "", ttl))
    return out


def prompt_segments(flavor: str, body: dict) -> list[tuple[str, Optional[str]]]:
    """The prompt as an ordered list of (segment_text, breakpoint_ttl), in the order the
    provider renders it: tools, then system, then messages."""
    segs: list[tuple[str, Optional[str]]] = []
    if flavor == "anthropic":
        for t in body.get("tools") or []:
            cc = t.get("cache_control") if isinstance(t, dict) else None
            t2 = {k: v for k, v in t.items() if k != "cache_control"} if isinstance(t, dict) else t
            segs.append(("tool:" + json.dumps(t2, sort_keys=True), (cc.get("ttl") or "5m") if cc else None))
        segs += [("system:" + x, ttl) for x, ttl in _text_of(body.get("system") or "")] if body.get("system") else []
        for m in body.get("messages") or []:
            segs += [(f"{m.get('role')}:" + x, ttl) for x, ttl in _text_of(m.get("content"))]
        top = body.get("cache_control")
        if isinstance(top, dict) and segs and segs[-1][1] is None:  # automatic caching
            segs[-1] = (segs[-1][0], top.get("ttl") or "5m")
    elif flavor == "openai":
        for t in body.get("tools") or []:
            segs.append(("tool:" + json.dumps(t, sort_keys=True), None))
        if body.get("instructions"):
            segs.append(("instructions:" + str(body["instructions"]), None))
        inp = body.get("input")
        for m in ([{"role": "user", "content": inp}] if isinstance(inp, str) else inp or []):
            c = m.get("content")
            segs.append((f"{m.get('role')}:" + (c if isinstance(c, str) else json.dumps(c, sort_keys=True)), None))
    else:
        si = body.get("systemInstruction") or {}
        if si:
            segs.append(("system:" + " ".join(p.get("text", "") for p in si.get("parts", [])), None))
        for c in body.get("contents") or []:
            # media parts count by identity (their digest), so two different images never
            # look like the same cached prefix
            segs.append((f"{c.get('role')}:" + " ".join(
                p.get("text", "") if "text" in p or not ({"inlineData", "fileData"} & set(p))
                else json.dumps(p, sort_keys=True) for p in c.get("parts", [])), None))
    return segs


def simulate_cache(state: "State", flavor: str, body: dict, total_tokens: int, delay: float) -> dict:
    """Decide cache reads and writes for one request, update the cache, return usage parts:
    {"read": n, "write": n, "write_1h": n}. `delay` is when the response would start:
    an entry written now is usable only after that (like the real API, where a cache entry
    becomes available only once the first response starts)."""
    cfg = state.cfg
    segs = prompt_segments(flavor, body)
    if not cfg.cache or not segs:
        return {"read": 0, "write": 0, "write_1h": 0}
    cum, hashes, h, n = [], [], hashlib.sha256(), 0
    for text, _ in segs:
        h.update(text.encode() + b"\x00")
        hashes.append(h.hexdigest())
        n += approx_tokens(text)
        cum.append(n)
    scale = cfg.cache_ttl_scale
    now = time.time()
    with state.lock:
        def live(key):
            e = state.cache.get(key)
            return e is not None and e[0] > now and e[2] <= now

        if flavor == "anthropic":
            bps = [i for i, (_, ttl) in enumerate(segs) if ttl]
            hit = -1
            for b in bps:
                for j in range(b, max(-1, b - LOOKBACK), -1):
                    if j > hit and live(hashes[j]):
                        hit = j
                        break
            if hit >= 0:  # a hit refreshes the entry's lifetime at no cost
                exp, ttl_s, ready = state.cache[hashes[hit]]
                state.cache[hashes[hit]] = (now + ttl_s, ttl_s, ready)
                state.cache_reads += 1
            read = cum[hit] if hit >= 0 else 0
            write = write_1h = 0
            prev = hit
            for b in bps:
                if b <= hit or cum[b] < cfg.cache_min_tokens:
                    continue  # too short to cache: silently not cached, like the real API
                ttl_s = TTL_SECONDS.get(segs[b][1], 300.0) * scale
                state.cache[hashes[b]] = (now + ttl_s, ttl_s, now + delay)
                state.cache_writes += 1
                span = cum[b] - (cum[prev] if prev >= 0 else 0)
                write += span
                write_1h += span if segs[b][1] == "1h" else 0
                prev = b
            return {"read": min(read, total_tokens), "write": write, "write_1h": write_1h}

        # OpenAI / Gemini: automatic, every message boundary is a candidate prefix.
        minimum = OPENAI_CACHE_MIN if flavor == "openai" else GEMINI_CACHE_MIN
        hit = max((j for j in range(len(segs)) if live(hashes[j])), default=-1)
        read = cum[hit] if hit >= 0 else 0
        if flavor == "openai":
            read = read // OPENAI_CACHE_STEP * OPENAI_CACHE_STEP
        if read < minimum:
            read = 0
        if read:
            state.cache_reads += 1
        for j in range(len(segs)):
            if cum[j] >= minimum:
                state.cache[hashes[j]] = (now + AUTO_TTL * scale, AUTO_TTL * scale, now + delay)
        return {"read": min(read, total_tokens), "write": 0, "write_1h": 0}


def request_schema(flavor: str, body: dict) -> Optional[dict]:
    """Where each provider puts the JSON Schema for native structured output."""
    if flavor == "anthropic":
        return (((body.get("output_config") or {}).get("format") or {}).get("schema"))
    if flavor == "openai":
        return (((body.get("text") or {}).get("format") or {}).get("schema"))
    return (body.get("generationConfig") or {}).get("responseJsonSchema")


def sample_from_schema(schema: dict, root: Optional[dict] = None):
    """A minimal valid instance: first enum value, min of ranges, one array item."""
    root = root or schema
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        defs = root.get("$defs") or root.get("definitions") or {}
        return sample_from_schema(defs.get(name, {}), root)
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    for key in ("anyOf", "oneOf"):
        if key in schema:
            if any(o.get("type") == "null" for o in schema[key]):
                return None  # nullable: null is always a valid minimal value
            return sample_from_schema(schema[key][0], root)
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "null")
    if t == "object" or "properties" in schema:
        return {k: sample_from_schema(v, root) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [sample_from_schema(schema.get("items", {}), root)]
    if t == "integer":
        return int(schema.get("minimum", 1))
    if t == "number":
        return float(schema.get("minimum", 1))
    if t == "string" and "@" in schema.get("pattern", ""):
        return "user@example.com"
    if t == "boolean":
        return False
    if t == "null":
        return None
    fmt = schema.get("format")
    return {"email": "user@example.com", "date": "2026-01-01", "date-time": "2026-01-01T00:00:00Z",
            "uri": "https://example.com"}.get(fmt, "example")


def apply_json_fault(obj, fault: str, schema: Optional[dict]) -> str:
    """Serialize obj, broken in one specific, realistic way."""
    if fault in ("missing_field", "wrong_type", "bad_enum", "extra_field", "out_of_range") and isinstance(obj, dict):
        obj = dict(obj)
        props = (schema or {}).get("properties", {})
        if fault == "missing_field" and obj:
            def nullable(p):
                return any(o.get("type") == "null" for o in p.get("anyOf", [])) or "null" in (p.get("type") or [])
            key = next((k for k in obj if not nullable(props.get(k, {}))), next(iter(obj)))
            obj.pop(key)
        elif fault == "wrong_type":
            key = next((k for k, v in obj.items() if isinstance(v, (bool, int, float))), None)
            if key is not None:
                obj[key] = "maybe" if isinstance(obj[key], bool) else "three"
            elif obj:
                obj[next(iter(obj))] = 12345
        elif fault == "bad_enum":
            key = next((k for k in obj if "enum" in props.get(k, {})), None)
            if key is None:  # enum may sit inside anyOf
                key = next((k for k in obj if any("enum" in o for o in props.get(k, {}).get("anyOf", []))), None)
            obj[key or next(iter(obj))] = "SUPER_ADMIN"
        elif fault == "extra_field":
            obj["notes"] = "I also added this field."
        elif fault == "out_of_range":
            key = next((k for k, v in obj.items() if isinstance(v, int) and not isinstance(v, bool)), None)
            if key is None:  # integer may sit inside anyOf with null
                key = next((k for k in obj if any(o.get("type") == "integer" for o in props.get(k, {}).get("anyOf", []))), None)
            if key is not None:
                obj[key] = 100000
    text = json.dumps(obj, ensure_ascii=False)
    if fault == "fence":
        return "```json\n" + text + "\n```"
    if fault == "prose":
        return "Sure! Here is the extracted request:\n" + text + "\nLet me know if you need anything else."
    if fault == "truncated":
        return text[: max(1, len(text) // 2)]
    return text


def answer_for(question: str, cfg: MockConfig) -> str:
    if cfg.reply:
        return cfg.reply
    m = re.search(r"<question>(.*?)</question>", question, re.S)  # lesson-1 style prompts
    q = " ".join((m.group(1) if m else question).split())[:80]
    return f"This is a mock answer from mockllm. You asked: {q}"


def make_handler(state: State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "mockllm/1.0"

        def log_message(self, fmt, *args):  # quiet by default
            if getattr(self.server, "verbose", False):
                super().log_message(fmt, *args)

        # ------------------------------------------------ plumbing
        def _send_json(self, status: int, obj, headers: Optional[dict] = None, corrupt: bool = False):
            raw = json.dumps(obj)
            if corrupt:
                raw = raw[: len(raw) // 2]  # cut mid-object: invalid JSON
            data = raw.encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _start_sse(self, headers: dict):
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("cache-control", "no-cache")
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()

        def _event(self, name: Optional[str], obj, corrupt: bool = False) -> bool:
            payload = json.dumps(obj)
            if corrupt:
                payload = payload[: len(payload) // 2]
            chunk = (f"event: {name}\n" if name else "") + f"data: {payload}\n\n"
            try:
                self.wfile.write(chunk.encode())
                self.wfile.flush()
                return True
            except (BrokenPipeError, ConnectionResetError):  # client went away
                return False

        def _read_body(self) -> dict:
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return {"__invalid__": True}

        # ------------------------------------------------ routing
        def do_GET(self):
            if self.path == "/__admin/stats":
                return self._send_json(200, state.stats())
            self._send_json(404, {"error": {"message": "not found"}})

        def do_POST(self):
            body = self._read_body()
            if self.path == "/__admin/config":
                valid = {f.name for f in fields(MockConfig)}
                for k, v in body.items():
                    if k in valid:
                        setattr(state.cfg, k, v)
                if "seed" in body:
                    state.rng.seed(body["seed"])
                return self._send_json(200, asdict(state.cfg))
            if self.path == "/__admin/reset":
                with state.lock:
                    state.reset()
                return self._send_json(200, {"ok": True})

            gem = re.match(r"^/v1beta/models/([^:/]+):(generateContent|streamGenerateContent)", self.path)
            if self.path == "/v1/messages":
                flavor, stream = "anthropic", bool(body.get("stream"))
            elif self.path == "/v1/responses":
                flavor, stream = "openai", bool(body.get("stream"))
            elif gem:
                flavor, stream = "gemini", gem.group(2) == "streamGenerateContent"
                body["model"] = gem.group(1)
            else:
                return self._send_json(404, {"error": {"message": f"unknown path {self.path}"}})

            n, fail, corrupt = state.tick(self.path, stream)
            rid = f"req_mock_{uuid.uuid4().hex[:16]}"
            cfg = state.cfg
            if cfg.latency:
                time.sleep(cfg.latency)

            problem = self._validate(flavor, body)
            media: list = []
            if not problem:
                # Lesson 21: measure and validate images/documents; from here on `body` is
                # the stripped copy (base64 replaced by a digest) for tokens and caching.
                media, body, problem = vision.inspect(flavor, body, body.get("model", "mock-model"))
            if not problem and flavor == "anthropic":
                problem = self._validate_cache(body)
            if not problem:
                problem = tooling.validate(flavor, body)
            if problem:
                return self._error(flavor, problem[0], problem[1], rid)
            if fail:
                return self._error(flavor, cfg.status, f"injected failure on request #{n}", rid)

            question, max_tokens = self._question(flavor, body)
            try:
                with state.lock:
                    tool_plan = tooling.plan(flavor, body, cfg, n, state.rng)
            except (ValueError, KeyError, TypeError) as exc:  # e.g. a broken tool_script
                return self._error(flavor, 400, f"mockllm tool planning failed: {exc}", rid)
            if tool_plan is not None and tool_plan.calls:
                return self._tool_response(flavor, body, rid, stream, tool_plan, corrupt)
            text = tool_plan.text if tool_plan is not None else answer_for(question, cfg)
            if media and tool_plan is None and not cfg.reply:
                text = vision.describe(media, question)
            schema = request_schema(flavor, body)
            base = sample_from_schema(schema) if schema else None
            if base is not None and media:
                base = vision.fill_from_oracle(base, vision.oracle_fields(media))
            if base is None and cfg.reply.strip().startswith("{"):
                try:
                    base = json.loads(cfg.reply)
                except json.JSONDecodeError:
                    base = None
            if base is not None:
                with state.lock:
                    faulty = cfg.json_fault and (n <= cfg.json_fault_first or state.rng.random() < cfg.json_fault_rate)
                text = apply_json_fault(base, cfg.json_fault if faulty else "", schema)
            words = text.split(" ")
            stop = "end"
            if approx_tokens(text) > max_tokens:  # honor the output cap
                words = words[: max(1, max_tokens)]
                text = " ".join(words)
                stop = "max_tokens"
            in_tok = self._in_tokens(flavor, body) + sum(m.tokens for m in media)
            out_tok = approx_tokens(text)
            model = body.get("model", "mock-model")
            # Simulated caching and prefill: only uncached prompt tokens cost time.
            cache = self._cache_and_prefill(flavor, body, in_tok)

            if not stream:
                obj = getattr(self, f"_json_{flavor}")(rid, model, text, stop, in_tok, out_tok, cache)
                return self._send_json(200, obj, self._ok_headers(flavor, rid), corrupt)
            getattr(self, f"_stream_{flavor}")(rid, model, words, stop, in_tok, out_tok, corrupt, cache)

        # ------------------------------------------------ tools (lesson 14)
        def _in_tokens(self, flavor: str, body: dict) -> int:
            segs = prompt_segments(flavor, body)
            n = max(approx_tokens(json.dumps(body)), sum(approx_tokens(t) for t, _ in segs))
            if flavor == "anthropic" and body.get("tools"):
                tc = body.get("tool_choice") if isinstance(body.get("tool_choice"), dict) else {}
                n += tooling.ANTHROPIC_TOOL_PROMPT.get(tc.get("type", "auto"), 286)
            return n

        def _tool_response(self, flavor: str, body: dict, rid: str, stream: bool, p, corrupt: bool):
            tooling.new_ids(flavor, p.calls)
            model = body.get("model", "mock-model")
            in_tok = self._in_tokens(flavor, body)
            out_tok = approx_tokens(p.text) + sum(approx_tokens(tooling.args_text(c)) + 10 for c in p.calls)
            cache = self._cache_and_prefill(flavor, body, in_tok)
            if not stream:
                if flavor == "anthropic":
                    obj = {"id": f"msg_{rid[9:]}", "type": "message", "role": "assistant", "model": model,
                           "content": tooling.anthropic_content(p), "stop_reason": "tool_use",
                           "stop_sequence": None, "usage": self._usage_anthropic(in_tok, out_tok, cache)}
                elif flavor == "openai":
                    obj = {"id": f"resp_{rid[9:]}", "object": "response", "model": model, "status": "completed",
                           "output": tooling.openai_output(p), "usage": self._usage_openai(in_tok, out_tok, cache)}
                else:
                    obj = {"candidates": [{"content": {"role": "model", "parts": tooling.gemini_parts(p)},
                                           "finishReason": "STOP"}],
                           "usageMetadata": self._usage_gemini(in_tok, out_tok, cache),
                           "modelVersion": model, "responseId": rid}
                return self._send_json(200, obj, self._ok_headers(flavor, rid), corrupt)
            getattr(self, f"_tool_stream_{flavor}")(rid, model, p, in_tok, out_tok, cache)

        def _tool_stream_anthropic(self, rid, model, p, i, o, c):
            self._start_sse({"request-id": rid})
            ev = self._event
            ev("message_start", {"type": "message_start", "message": {
                "id": f"msg_{rid[9:]}", "type": "message", "role": "assistant", "model": model,
                "content": [], "stop_reason": None, "usage": self._usage_anthropic(i, 1, c)}})
            idx = 0
            if p.text:
                ev("content_block_start", {"type": "content_block_start", "index": 0,
                                           "content_block": {"type": "text", "text": ""}})
                for k, w in enumerate(p.text.split(" ")):
                    self._pace(k == 0)
                    ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                               "delta": {"type": "text_delta", "text": w if k == 0 else " " + w}})
                ev("content_block_stop", {"type": "content_block_stop", "index": 0})
                idx = 1
            for call in p.calls:
                ev("content_block_start", {"type": "content_block_start", "index": idx, "content_block": {
                    "type": "tool_use", "id": call.id, "name": call.name, "input": {}}})
                for k, piece in enumerate(tooling.chunks(tooling.args_text(call))):
                    fault = self._fault_now(k)
                    if fault == "truncate":
                        return
                    if fault == "error":
                        ev("error", {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
                        return
                    self._pace(k == 0 and idx == 0)
                    ev("content_block_delta", {"type": "content_block_delta", "index": idx,
                                               "delta": {"type": "input_json_delta", "partial_json": piece}})
                ev("content_block_stop", {"type": "content_block_stop", "index": idx})
                idx += 1
            ev("message_delta", {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None},
                                 "usage": {"output_tokens": o}})
            ev("message_stop", {"type": "message_stop"})

        def _tool_stream_openai(self, rid, model, p, i, o, c):
            self._start_sse({"x-request-id": rid})
            seq = 0

            def send(name, obj):
                nonlocal seq
                obj = {"type": name, "sequence_number": seq, **obj}
                seq += 1
                return self._event(name, obj)

            resp = {"id": f"resp_{rid[9:]}", "object": "response", "model": model, "status": "in_progress"}
            send("response.created", {"response": resp})
            output = tooling.openai_output(p)
            for oi, item in enumerate(output):
                if item["type"] == "message":
                    send("response.output_item.added", {"output_index": oi, "item": {**item, "content": []}})
                    send("response.output_text.delta", {"output_index": oi, "content_index": 0,
                                                        "item_id": item["id"], "delta": p.text})
                    send("response.output_item.done", {"output_index": oi, "item": item})
                    continue
                send("response.output_item.added", {"output_index": oi, "item": {**item, "arguments": "",
                                                                                 "status": "in_progress"}})
                for k, piece in enumerate(tooling.chunks(item["arguments"])):
                    if self._fault_now(k) == "truncate":
                        return
                    self._pace(k == 0 and oi == 0)
                    send("response.function_call_arguments.delta", {"output_index": oi, "item_id": item["id"],
                                                                    "delta": piece})
                send("response.function_call_arguments.done", {"output_index": oi, "item_id": item["id"],
                                                               "arguments": item["arguments"]})
                send("response.output_item.done", {"output_index": oi, "item": item})
            send("response.completed", {"response": {**resp, "status": "completed", "output": output,
                                                     "usage": self._usage_openai(i, o, c)}})

        def _tool_stream_gemini(self, rid, model, p, i, o, c):
            self._start_sse({})
            self._pace(True)
            # Gemini streams a functionCall whole, never as argument fragments.
            self._event(None, {"candidates": [{"content": {"role": "model", "parts": tooling.gemini_parts(p)},
                                               "finishReason": "STOP"}],
                               "usageMetadata": self._usage_gemini(i, o, c), "modelVersion": model,
                               "responseId": rid})

        # ------------------------------------------------ helpers
        def _cache_and_prefill(self, flavor: str, body: dict, in_tok: int) -> dict:
            cfg = state.cfg
            # Prefill time depends on the cache outcome, and the cache entry becomes
            # usable only when the response starts; approximate with the worst case.
            delay = in_tok / cfg.prefill_tps if cfg.prefill_tps else 0.0
            cache = simulate_cache(state, flavor, body, in_tok, delay)
            if cfg.prefill_tps:
                time.sleep(max(0, in_tok - cache["read"]) / cfg.prefill_tps)
            return cache

        def _validate_cache(self, body: dict):
            marks = sum(1 for _, ttl in prompt_segments("anthropic", {**body, "cache_control": None}) if ttl)
            top = 1 if isinstance(body.get("cache_control"), dict) else 0
            if marks + top > 4:
                return 400, "A maximum of 4 blocks with cache_control may be provided. Found %d." % (marks + top)
            ttls = [ttl for _, ttl in prompt_segments("anthropic", body) if ttl]
            if "1h" in ttls and "5m" in ttls and ttls.index("5m") < len(ttls) - 1 - ttls[::-1].index("1h"):
                return 400, "cache_control: a ttl='1h' cache entry must not come after a ttl='5m' cache entry"
            return None

        def _validate(self, flavor: str, body: dict):
            if body.get("__invalid__"):
                return 400, "request body is not valid JSON"
            if flavor == "anthropic":
                if not self.headers.get("x-api-key"):
                    return 401, "x-api-key header is required"
                if not self.headers.get("anthropic-version"):
                    return 400, "anthropic-version header is required"
                if "max_tokens" not in body:
                    return 400, "max_tokens: Field required"
                if not body.get("messages"):
                    return 400, "messages: Field required"
                if body["messages"][0].get("role") != "user":
                    return 400, "messages: first message must use the \"user\" role"
                # Reproduces lesson 1: the newest API version dropped sampling parameters.
                if self.headers.get("anthropic-version", "") >= "2026" and "temperature" in body:
                    return 400, "temperature: Extra inputs are not permitted"
            elif flavor == "openai":
                if not (self.headers.get("authorization") or "").startswith("Bearer "):
                    return 401, "missing bearer token"
                if "input" not in body:
                    return 400, "Missing required parameter: 'input'."
            elif flavor == "gemini":
                if not self.headers.get("x-goog-api-key"):
                    return 401, "API key not valid. Please pass a valid API key."
                if not body.get("contents"):
                    return 400, "contents is not specified"
            return None

        def _question(self, flavor: str, body: dict) -> tuple[str, int]:
            if flavor == "anthropic":
                last = body["messages"][-1]["content"]
                if isinstance(last, list):
                    last = " ".join(b.get("text", "") for b in last)
                return last, int(body.get("max_tokens", 1024))
            if flavor == "openai":
                inp = body.get("input")
                last = inp if isinstance(inp, str) else (inp[-1].get("content", "") if inp else "")
                if isinstance(last, list):  # content parts (lesson 21): keep only the text
                    last = " ".join(p.get("text", "") for p in last if isinstance(p, dict))
                return str(last), int(body.get("max_output_tokens") or 1024)
            parts = body["contents"][-1].get("parts", [])
            cap = (body.get("generationConfig") or {}).get("maxOutputTokens", 1024)
            return " ".join(p.get("text", "") for p in parts), int(cap)

        def _ok_headers(self, flavor: str, rid: str) -> dict:
            if flavor == "anthropic":
                return {"request-id": rid,
                        "anthropic-ratelimit-requests-limit": "1000",
                        "anthropic-ratelimit-requests-remaining": "999",
                        "anthropic-ratelimit-output-tokens-limit": "80000"}
            if flavor == "openai":
                return {"x-request-id": rid, "x-ratelimit-limit-requests": "500",
                        "x-ratelimit-remaining-requests": "499"}
            return {}

        def _error(self, flavor: str, status: int, message: str, rid: str):
            a_type, g_status = ERROR_TYPES.get(status, ("api_error", "UNKNOWN"))
            headers = {"request-id": rid, "x-request-id": rid}
            retry_after = state.cfg.retry_after if state.cfg.retry_after is not None else (1 if status == 429 else None)
            if retry_after is not None:
                headers["retry-after"] = str(retry_after)
            if flavor == "anthropic":
                obj = {"type": "error", "error": {"type": a_type, "message": message}, "request_id": rid}
            elif flavor == "openai":
                obj = {"error": {"message": message, "type": a_type, "code": a_type}}
            else:
                obj = {"error": {"code": status, "message": message, "status": g_status}}
            self._send_json(status, obj, headers)

        # ------------------------------------------------ non-streaming bodies
        @staticmethod
        def _usage_anthropic(i, o, c=None):
            c = c or {"read": 0, "write": 0, "write_1h": 0}
            # Like the real API: input_tokens is only the part after the last breakpoint.
            return {"input_tokens": max(0, i - c["read"] - c["write"]), "output_tokens": o,
                    "cache_creation_input_tokens": c["write"], "cache_read_input_tokens": c["read"],
                    "cache_creation": {"ephemeral_5m_input_tokens": c["write"] - c["write_1h"],
                                       "ephemeral_1h_input_tokens": c["write_1h"]}}

        @staticmethod
        def _usage_openai(i, o, c=None):
            u = {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}
            u["input_tokens_details"] = {"cached_tokens": (c or {}).get("read", 0)}
            return u

        @staticmethod
        def _usage_gemini(i, o, c=None, partial_o=None):
            u = {"promptTokenCount": i, "candidatesTokenCount": o if partial_o is None else partial_o,
                 "totalTokenCount": i + o}
            if c and c.get("read"):
                u["cachedContentTokenCount"] = c["read"]
            return u

        def _json_anthropic(self, rid, model, text, stop, i, o, c=None):
            return {"id": f"msg_{rid[9:]}", "type": "message", "role": "assistant", "model": model,
                    "content": [{"type": "text", "text": text}],
                    "stop_reason": "end_turn" if stop == "end" else "max_tokens",
                    "usage": self._usage_anthropic(i, o, c)}

        def _json_openai(self, rid, model, text, stop, i, o, c=None):
            resp = {"id": f"resp_{rid[9:]}", "object": "response", "model": model,
                    "status": "completed" if stop == "end" else "incomplete",
                    "output": [{"type": "message", "role": "assistant",
                                "content": [{"type": "output_text", "text": text}]}],
                    "usage": self._usage_openai(i, o, c)}
            if stop != "end":
                resp["incomplete_details"] = {"reason": "max_output_tokens"}
            return resp

        def _json_gemini(self, rid, model, text, stop, i, o, c=None):
            return {"candidates": [{"content": {"role": "model", "parts": [{"text": text}]},
                                    "finishReason": "STOP" if stop == "end" else "MAX_TOKENS"}],
                    "usageMetadata": self._usage_gemini(i, o, c),
                    "modelVersion": model, "responseId": rid}

        # ------------------------------------------------ streaming bodies
        def _pace(self, first: bool):
            cfg = state.cfg
            if first and cfg.ttft:
                time.sleep(cfg.ttft)
            elif not first and cfg.tps:
                time.sleep(1.0 / cfg.tps)

        def _deltas(self, words):
            """Yield (index, piece); stop early for truncate/error faults (caller checks)."""
            for idx, w in enumerate(words):
                self._pace(idx == 0)
                yield idx, (w if idx == 0 else " " + w)

        def _fault_now(self, idx: int) -> Optional[str]:
            cfg = state.cfg
            if cfg.truncate_after and idx >= cfg.truncate_after:
                return "truncate"
            if cfg.error_after and idx >= cfg.error_after:
                return "error"
            return None

        def _stream_anthropic(self, rid, model, words, stop, i, o, corrupt, c=None):
            self._start_sse({"request-id": rid})
            ev = self._event
            ev("message_start", {"type": "message_start", "message": {
                "id": f"msg_{rid[9:]}", "type": "message", "role": "assistant", "model": model,
                "content": [], "stop_reason": None, "usage": self._usage_anthropic(i, 1, c)}})
            ev("content_block_start", {"type": "content_block_start", "index": 0,
                                       "content_block": {"type": "text", "text": ""}})
            ev("ping", {"type": "ping"})
            for idx, piece in self._deltas(words):
                fault = self._fault_now(idx)
                if fault == "truncate":
                    return
                if fault == "error":
                    ev("error", {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
                    return
                if not ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                                  "delta": {"type": "text_delta", "text": piece}},
                          corrupt and idx == 1):
                    return
            ev("content_block_stop", {"type": "content_block_stop", "index": 0})
            ev("message_delta", {"type": "message_delta",
                                 "delta": {"stop_reason": "end_turn" if stop == "end" else "max_tokens",
                                           "stop_sequence": None},
                                 "usage": {"output_tokens": o}})
            ev("message_stop", {"type": "message_stop"})

        def _stream_openai(self, rid, model, words, stop, i, o, corrupt, c=None):
            self._start_sse({"x-request-id": rid})
            ev = self._event
            resp = {"id": f"resp_{rid[9:]}", "object": "response", "model": model, "status": "in_progress"}
            seq = 0

            def send(name, obj, bad=False):
                nonlocal seq
                obj = {"type": name, "sequence_number": seq, **obj}
                seq += 1
                return ev(name, obj, bad)

            send("response.created", {"response": resp})
            send("response.in_progress", {"response": resp})
            send("response.output_item.added", {"output_index": 0, "item": {"type": "message", "role": "assistant", "content": []}})
            send("response.content_part.added", {"output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}})
            for idx, piece in self._deltas(words):
                fault = self._fault_now(idx)
                if fault == "truncate":
                    return
                if fault == "error":
                    send("error", {"code": "server_error", "message": "The server had an error while processing your request."})
                    return
                if not send("response.output_text.delta", {"output_index": 0, "content_index": 0, "delta": piece},
                            corrupt and idx == 1):
                    return
            text = " ".join(words)
            send("response.output_text.done", {"output_index": 0, "content_index": 0, "text": text})
            final = {**resp, "status": "completed" if stop == "end" else "incomplete",
                     "usage": self._usage_openai(i, o, c)}
            if stop != "end":
                final["incomplete_details"] = {"reason": "max_output_tokens"}
                send("response.incomplete", {"response": final})
            else:
                send("response.completed", {"response": final})

        def _stream_gemini(self, rid, model, words, stop, i, o, corrupt, c=None):
            self._start_sse({})
            done = 0
            for idx, piece in self._deltas(words):
                fault = self._fault_now(idx)
                if fault == "truncate":
                    return
                if fault == "error":
                    self._event(None, {"error": {"code": 503, "message": "The model is overloaded.", "status": "UNAVAILABLE"}})
                    return
                done += 1
                last = idx == len(words) - 1
                cand = {"content": {"role": "model", "parts": [{"text": piece}]}}
                if last:
                    cand["finishReason"] = "STOP" if stop == "end" else "MAX_TOKENS"
                chunk = {"candidates": [cand],
                         # Cumulative, like the real API: the last chunk holds the totals.
                         "usageMetadata": self._usage_gemini(
                             i, o, c, None if last else max(1, round(o * done / len(words)))),
                         "modelVersion": model, "responseId": rid}
                if not self._event(None, chunk, corrupt and idx == 1):
                    return

    return Handler


def start_in_thread(cfg: Optional[MockConfig] = None, host: str = "127.0.0.1", port: int = 0):
    """Start a server on a free port; returns (server, base_url). Call server.shutdown() to stop."""
    state = State(cfg or MockConfig())
    server = ThreadingHTTPServer((host, port), make_handler(state))
    server.daemon_threads = True
    server.state = state
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://{host}:{server.server_address[1]}"


def serve(cfg: MockConfig, host: str = "127.0.0.1", port: int = 8765, verbose: bool = False):
    state = State(cfg)
    server = ThreadingHTTPServer((host, port), make_handler(state))
    server.daemon_threads = True
    server.verbose = verbose
    print(f"mockllm listening on http://{host}:{port}  (Ctrl+C to stop)")
    print(f"faults: {json.dumps({k: v for k, v in asdict(cfg).items() if v})}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

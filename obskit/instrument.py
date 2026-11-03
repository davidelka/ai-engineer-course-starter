"""InstrumentedLLM: OpenTelemetry spans around llmkit calls, from the outside.

    from llmkit import LLM
    from obskit import InstrumentedLLM, setup_tracing
    setup_tracing("acme-answer", jsonl="results/traces.jsonl")
    llm = InstrumentedLLM(LLM("anthropic:claude-haiku-5-5"), prompt_name="rag-answer", prompt_version="v3")
    result = llm.complete("Name two colors.")          # same API, same ChatResult

A wrapper (composition), not a subclass: it works with anything that has
complete(req) -> ChatResult, such as ragkit's offline ExtractiveAnswerer, and it does not
care how llmkit evolves inside (tool calling in lesson 14, for example). Attribute
access falls through to the wrapped object, so llm.model, llm.provider... still work.

One span per LOGICAL call ("chat {model}", kind CLIENT). llmkit's retries happen inside
that call; each one becomes a "retry" event on the span (attempt, error.type, wait_s),
and obskit.attempts is the total. This matches the spec's model of a logical client call.
A retry storm therefore shows up as one long span with several retry events, which is
exactly what you want to see when you open the trace.
"""

from __future__ import annotations

import time
from typing import Any, Iterator, Optional, Union
from urllib.parse import urlparse

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from . import semconv as sc
from .tracing import capturing, get_tracer, mark_error, to_json


def _text_parts(content: Any) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "content": content}]
    return [{"type": "text", "content": getattr(b, "text", str(b))} for b in content or []]


def input_messages(req) -> list[dict]:
    """ChatRequest.messages -> the spec's input message format (role + parts)."""
    return [{"role": m.role, "parts": _text_parts(m.content)} for m in req.messages]


def system_instructions(req) -> list[dict]:
    return _text_parts(req.system) if getattr(req, "system", None) else []


class InstrumentedLLM:
    def __init__(self, llm: Any, *, tracer: Optional[trace.Tracer] = None,
                 capture_content: Optional[bool] = None, prompt_name: Optional[str] = None,
                 prompt_version: Optional[str] = None, conversation_id: Optional[str] = None,
                 extra_attributes: Optional[dict] = None):
        self.inner = llm
        self._tracer = tracer
        self.capture_content = capture_content
        self.prompt_name = prompt_name
        self.prompt_version = prompt_version
        self.conversation_id = conversation_id
        self.extra_attributes = dict(extra_attributes or {})

    def __getattr__(self, name):
        return getattr(self.inner, name)

    @property
    def tracer(self) -> trace.Tracer:
        return self._tracer or get_tracer()

    # ------------------------------------------------------------ helpers
    def _model(self) -> str:
        return str(getattr(self.inner, "model", "unknown"))

    def _provider(self) -> str:
        p = getattr(self.inner, "provider", None)
        name = getattr(p, "name", None) or (p if isinstance(p, str) else None) or "unknown"
        return sc.PROVIDER_NAMES.get(name, name)

    def _request(self, req, kw):
        if isinstance(req, str):
            from llmkit import ChatRequest
            return ChatRequest.from_prompt(req, **{k: v for k, v in kw.items() if k in ChatRequest.__dataclass_fields__})
        return req

    def _start_attrs(self, req, stream: bool) -> dict:
        a = {sc.SPAN_TYPE: "llm", sc.OPERATION: sc.OP_CHAT, sc.PROVIDER: self._provider(),
             sc.REQUEST_MODEL: self._model(), sc.REQUEST_STREAM: bool(stream)}
        if getattr(req, "max_tokens", None):
            a[sc.REQUEST_MAX_TOKENS] = int(req.max_tokens)
        if getattr(req, "effort", None):
            a[sc.REQUEST_REASONING] = str(req.effort)
        if getattr(req, "response_schema", None):
            a[sc.OUTPUT_TYPE] = "json"
        base = getattr(self.inner, "base_url", None)
        if base:
            u = urlparse(base)
            if u.hostname:
                a[sc.SERVER_ADDRESS] = u.hostname
                a[sc.SERVER_PORT] = u.port or (443 if u.scheme == "https" else 80)
        if self.prompt_name:
            a[sc.PROMPT_NAME] = self.prompt_name
        if self.prompt_version:
            a[sc.PROMPT_VERSION] = self.prompt_version
        if self.conversation_id:
            a[sc.CONVERSATION_ID] = self.conversation_id
        a.update(self.extra_attributes)
        if capturing(self.capture_content):
            si = system_instructions(req)
            if si:
                a[sc.SYSTEM_INSTRUCTIONS] = to_json(si)
            a[sc.INPUT_MESSAGES] = to_json(input_messages(req))
        return a

    def _record_result(self, sp, res) -> None:
        u = res.usage
        sp.set_attribute(sc.RESPONSE_MODEL, str(res.model))
        if res.request_id:
            sp.set_attribute(sc.RESPONSE_ID, str(res.request_id))
        finish = sc.FINISH_REASON_MAP.get(res.stop_reason, res.raw_stop_reason or res.stop_reason)
        sp.set_attribute(sc.FINISH_REASONS, [finish])
        sp.set_attribute(sc.USAGE_INPUT, int(u.input_tokens))
        sp.set_attribute(sc.USAGE_OUTPUT, int(u.output_tokens))
        if u.cached_input_tokens:
            sp.set_attribute(sc.USAGE_CACHE_READ, int(u.cached_input_tokens))
        if u.cache_creation_tokens:
            sp.set_attribute(sc.USAGE_CACHE_WRITE, int(u.cache_creation_tokens))
        if getattr(u, "thinking_tokens", 0):
            sp.set_attribute(sc.USAGE_REASONING, int(u.thinking_tokens))
        if res.ttft_s is not None:
            sp.set_attribute(sc.TIME_TO_FIRST_CHUNK, round(float(res.ttft_s), 4))
        if res.cost_usd is not None:
            sp.set_attribute(sc.COST_USD, round(float(res.cost_usd), 8))
        sp.set_attribute(sc.ATTEMPTS, int(getattr(res, "attempts", 1) or 1))
        if getattr(res, "partial", False):
            sp.set_attribute(sc.PARTIAL, True)
        if capturing(self.capture_content):
            parts = [{"type": "text", "content": res.text}] if res.text else []
            for call in getattr(res, "tool_calls", None) or []:  # llmkit tool calling (lesson 14), if present
                parts.append({"type": "tool_call", "id": getattr(call, "id", None),
                              "name": getattr(call, "name", None), "arguments": getattr(call, "arguments", None)})
            sp.set_attribute(sc.OUTPUT_MESSAGES, to_json([{"role": "assistant", "parts": parts, "finish_reason": finish}]))
        if res.stop_reason in ("max_tokens", "refusal"):
            sp.add_event("gen_ai.unusual_finish", {"finish_reason": finish})
        sp.set_status(Status(StatusCode.OK))

    def _hook_retries(self, sp):
        """Chain llmkit's on_retry so every retry becomes a span event. Returns a restore fn."""
        if not hasattr(self.inner, "on_retry"):
            return lambda: None
        old = self.inner.on_retry
        count = {"n": 0}

        def on_retry(attempt, err, wait):
            count["n"] = attempt
            sp.add_event("retry", {"attempt": int(attempt), sc.ERROR_TYPE: str(getattr(err, "kind", "") or type(err).__name__),
                                   "http.response.status_code": int(getattr(err, "status", 0) or 0),
                                   "wait_s": round(float(wait), 3)})
            if old:
                old(attempt, err, wait)
        self.inner.on_retry = on_retry

        def restore():
            self.inner.on_retry = old
            return count["n"]
        return restore

    # ------------------------------------------------------------ API
    def complete(self, req: Union[Any, str], *, stream: bool = False, **kw):
        req = self._request(req, kw)
        name = f"{sc.OP_CHAT} {self._model()}"
        with self.tracer.start_as_current_span(name, kind=SpanKind.CLIENT, attributes=self._start_attrs(req, stream),
                                               record_exception=False, set_status_on_exception=False) as sp:
            restore = self._hook_retries(sp)
            try:
                res = self.inner.complete(req, stream=stream) if stream else self.inner.complete(req)
            except BaseException as exc:
                retries = restore()
                sp.set_attribute(sc.ATTEMPTS, retries + 1)
                mark_error(sp, exc)
                raise
            restore()
            self._record_result(sp, res)
            return res

    def stream(self, req: Union[Any, str], **kw) -> Iterator[Any]:
        """Same events as llmkit's stream(). The span stays open while you iterate and ends
        when the stream ends, fails, or you stop iterating (then it is marked cancelled)."""
        req = self._request(req, kw)
        sp = self.tracer.start_span(f"{sc.OP_CHAT} {self._model()}", kind=SpanKind.CLIENT,
                                    attributes=self._start_attrs(req, True))
        restore = self._hook_retries(sp)
        t0, first, done = time.perf_counter(), None, False
        try:
            for ev in self.inner.stream(req):
                if ev.type == "text" and first is None:
                    first = time.perf_counter() - t0
                    sp.add_event("gen_ai.first_chunk")
                if ev.type == "done" and ev.result is not None:
                    done = True
                    restore()
                    self._record_result(sp, ev.result)
                yield ev
        except GeneratorExit:
            sp.set_attribute("obskit.cancelled", True)
            raise
        except BaseException as exc:
            retries = restore()
            sp.set_attribute(sc.ATTEMPTS, retries + 1)
            if getattr(exc, "partial_text", ""):
                sp.set_attribute(sc.PARTIAL, True)
            mark_error(sp, exc)
            raise
        finally:
            if not done:
                restore()
            if first is not None and sc.TIME_TO_FIRST_CHUNK not in (getattr(sp, "attributes", None) or {}):
                sp.set_attribute(sc.TIME_TO_FIRST_CHUNK, round(first, 4))
            sp.end()

"""Calling llmkit from an async server, three ways.

llmkit.LLM is synchronous (httpx.Client). Inside an async server a blocking call
freezes the event loop: while one request waits 2 seconds for the model, no
other request on that worker makes progress. So we either:

1. AsyncLLM: a real async client (httpx.AsyncClient). It reuses llmkit's
   provider adapters for building requests and parsing replies, so the wire
   format is identical. Waiting costs no thread. Cancelling the task closes the
   HTTP connection, so the upstream stream stops at once.
   Native async streaming is implemented for the Anthropic wire format (which is
   also what `mock:` speaks); other providers stream through the thread bridge.

2. threaded_stream(): run the sync generator in the threadpool, one next() per
   event. Works with any sync library. Two costs: every stream occupies a worker
   thread for its whole life (anyio's default pool has 40), and cancellation is
   not instant: the thread cannot be interrupted, so we wait until its current
   next() returns, then close the generator, which closes the HTTP stream.

3. leaky_stream(): the bug this lesson is about. A producer task reads the
   upstream into an unbounded queue and the response reads from the queue.
   When the client disconnects, the response stops, but nobody cancels the
   producer: the upstream keeps generating (and billing) until it finishes.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import anyio
import httpx

from llmkit import LLM, ChatRequest, ChatResult, LLMError, StreamEvent, Usage
from llmkit.client import DEFAULT_TIMEOUT
from llmkit.pricing import cost_usd
from llmkit.providers.anthropic import AnthropicProvider
from llmkit.providers.base import header, load_json
from llmkit.sse import SSEEvent


@dataclass
class UpstreamStats:
    """What the server knows about its upstream LLM streams (shown at /v1/admin/stats)."""

    opened: int = 0
    finished: int = 0  # reached the provider's end event
    closed_early: int = 0  # we closed it before the end (client left, timeout)
    active: int = 0
    events: int = 0  # text events received from upstream
    by_mode: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"opened": self.opened, "finished": self.finished, "closed_early": self.closed_early,
                "active": self.active, "events": self.events, "by_mode": dict(self.by_mode)}


async def aiter_sse(lines: AsyncIterator[str]) -> AsyncIterator[SSEEvent]:
    """Async twin of llmkit.sse.iter_sse."""
    event: Optional[str] = None
    data: list[str] = []
    async for raw in lines:
        line = raw.rstrip("\r\n")
        if line == "":
            if event is not None or data:
                yield SSEEvent(event, "\n".join(data))
            event, data = None, []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if name == "event":
            event = value
        elif name == "data":
            data.append(value)
    if event is not None or data:
        yield SSEEvent(event, "\n".join(data))


class AsyncLLM:
    """Async counterpart of llmkit.LLM for the server. No retries here on purpose:
    a server under load should fail fast and let the client (who knows its own
    deadline) decide; retry storms from inside a server multiply overload."""

    def __init__(self, spec: str, *, api_key: Optional[str] = None, base_url: Optional[str] = None,
                 timeout: httpx.Timeout = DEFAULT_TIMEOUT, max_connections: int = 200,
                 http: Optional[httpx.AsyncClient] = None):
        # The sync client resolves provider, model, base URL and key exactly like llmkit does.
        self.sync = LLM(spec, api_key=api_key, base_url=base_url)
        self.provider = self.sync.provider
        self.model = self.sync.model
        self.base_url = self.sync.base_url
        self.api_key = self.sync.api_key
        self.spec = spec
        self.http = http or httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=max_connections, max_keepalive_connections=50))

    def _result(self, text: str, raw_stop: str, usage: Usage, rid: Optional[str], t0: float,
                ttft: Optional[float]) -> ChatResult:
        return ChatResult(text=text, stop_reason=self.provider.map_stop(raw_stop), raw_stop_reason=raw_stop,
                          usage=usage, provider=self.provider.name, model=self.model,
                          cost_usd=cost_usd(self.model, usage), latency_s=time.perf_counter() - t0,
                          ttft_s=ttft, request_id=rid)

    def _transport_error(self, exc: Exception) -> LLMError:
        kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
        return LLMError(f"{type(exc).__name__}: {exc}", provider=self.provider.name, kind=kind)

    async def complete(self, req: ChatRequest) -> ChatResult:
        t0 = time.perf_counter()
        call = self.provider.build(req, self.model, self.api_key, stream=False)
        try:
            resp = await self.http.post(self.base_url + call.path, headers=call.headers, json=call.body)
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from None
        if resp.status_code >= 400:
            raise self.provider.error(resp.status_code, resp.text, resp.headers)
        try:
            body = resp.json()
        except json.JSONDecodeError:
            raise LLMError("malformed JSON from provider", provider=self.provider.name,
                           kind="malformed_response") from None
        p = self.provider.parse(body, resp.headers)
        return self._result(p.text, p.raw_stop, p.usage, p.request_id, t0, None)

    async def stream(self, req: ChatRequest) -> AsyncIterator[StreamEvent]:
        if not isinstance(self.provider, AnthropicProvider):
            async for ev in threaded_stream(self.sync, req):
                yield ev
            return
        t0 = time.perf_counter()
        call = self.provider.build(req, self.model, self.api_key, stream=True)
        try:
            async with self.http.stream("POST", self.base_url + call.path, headers=call.headers,
                                        json=call.body) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    raise self.provider.error(resp.status_code, resp.text, resp.headers)
                rid = header(resp.headers, "request-id")
                usage, raw_stop, parts, ttft = Usage(), "", [], None
                async for ev in aiter_sse(resp.aiter_lines()):
                    if ev.event == "ping" or not ev.data:
                        continue
                    data = load_json(ev.data, self.provider.name)
                    kind = ev.event or data.get("type")
                    if kind == "message_start":
                        usage = AnthropicProvider._usage(data["message"].get("usage", {}))
                    elif kind == "content_block_delta":
                        delta = data.get("delta", {})
                        if delta.get("type") == "text_delta":
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            parts.append(delta.get("text", ""))
                            yield StreamEvent("text", delta.get("text", ""))
                    elif kind == "message_delta":
                        raw_stop = data.get("delta", {}).get("stop_reason") or raw_stop
                        usage.output_tokens = (data.get("usage") or {}).get("output_tokens") or usage.output_tokens
                    elif kind == "message_stop":
                        yield StreamEvent("done", result=self._result("".join(parts), raw_stop, usage, rid, t0, ttft))
                        return
                    elif kind == "error":
                        err = data.get("error", {})
                        raise LLMError(err.get("message", "stream error"), provider=self.provider.name,
                                       kind=err.get("type", "api_error"), request_id=rid,
                                       partial_text="".join(parts))
                raise LLMError("stream ended before message_stop", provider=self.provider.name,
                               kind="stream_truncated", request_id=rid, partial_text="".join(parts))
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from None

    async def aclose(self) -> None:
        await self.http.aclose()
        self.sync.close()


_DONE = object()
_BACKGROUND: set = set()


def _next(gen):
    try:
        return next(gen)
    except StopIteration:
        return _DONE


async def threaded_stream(llm: LLM, req: ChatRequest,
                          limiter: Optional[anyio.CapacityLimiter] = None) -> AsyncIterator[StreamEvent]:
    """Drive llmkit's sync stream from async code, one next() per thread hop.

    anyio.to_thread.run_sync is NOT abandoned on cancellation: when the client
    leaves, the await below finishes only when the worker's current next()
    returns (one upstream event later). Then the finally block closes the
    generator in a shielded scope; GeneratorExit runs llmkit's own finally,
    which closes the HTTP response, and the upstream sees the disconnect.
    """
    gen = llm.stream(req)
    try:
        while True:
            ev = await anyio.to_thread.run_sync(_next, gen, limiter=limiter)
            if ev is _DONE:
                return
            yield ev
    finally:
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(gen.close, limiter=limiter)


async def leaky_stream(llm: "AsyncLLM", req: ChatRequest) -> AsyncIterator[StreamEvent]:
    """DON'T DO THIS. Shown in exercise 4 to make the leak measurable.

    The producer task is not tied to the response: on disconnect the consumer
    below is cancelled, the producer is not, and the queue is unbounded, so the
    upstream is read to the end into memory nobody will read."""
    q: asyncio.Queue = asyncio.Queue()  # unbounded: no backpressure either

    async def produce():
        try:
            async for ev in llm.stream(req):
                await q.put(ev)
        except Exception as exc:  # noqa: BLE001
            await q.put(exc)
        await q.put(_DONE)

    task = asyncio.get_running_loop().create_task(produce())  # fire and forget: the bug
    _BACKGROUND.add(task)  # asyncio keeps only weak references to tasks
    task.add_done_callback(_BACKGROUND.discard)
    while True:
        item = await q.get()
        if item is _DONE:
            return
        if isinstance(item, Exception):
            raise item
        yield item

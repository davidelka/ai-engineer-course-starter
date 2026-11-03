"""The one class application code talks to.

    llm = LLM("anthropic:claude-haiku-5-5")
    result = llm.complete("Name two colors.", system="Be brief.")
    for ev in llm.stream("Tell me a story"):
        ...

Switching provider is a change to the model string, nothing else.
"mock:<model>" (or mock-openai:, mock-gemini:) points an adapter at the local
mock server from `python -m mockllm`.
"""

from __future__ import annotations

import json
import os
import time
from typing import Callable, Iterator, Optional, Union

import httpx

from .errors import LLMError
from .pricing import cost_usd
from .providers import PROVIDERS
from .providers.base import StreamEnd, TextDelta, ToolCallDelta, ToolCallDone
from .retry import RetryPolicy, call_with_retry
from .sse import iter_sse
from .types import ChatRequest, ChatResult, StreamEvent, ToolCall, Usage

MOCK_URL = os.environ.get("MOCKLLM_URL", "http://127.0.0.1:8765")

# Short connect timeout; the read timeout is the gap allowed BETWEEN bytes, which
# for streaming means "between events". 60s, not the SDK's 10 minutes.
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)


def parse_spec(spec: str) -> tuple[str, str, Optional[str]]:
    """'anthropic:claude-haiku-5-5' -> ('anthropic', 'claude-haiku-5-5', None).
    'mock-openai:mock-model'     -> ('openai', 'mock-model', MOCK_URL)."""
    provider, sep, model = spec.partition(":")
    if not sep or not model:
        raise ValueError(f"model spec must look like 'provider:model', got {spec!r}")
    base_url = None
    if provider == "mock" or provider.startswith("mock-"):
        provider = provider[5:] or "anthropic"
        base_url = MOCK_URL
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}; choose from {', '.join(PROVIDERS)}")
    return provider, model, base_url


class LLM:
    def __init__(
        self,
        spec: str,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        retry: Optional[RetryPolicy] = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        prices: Optional[dict] = None,
        on_retry: Optional[Callable[[int, LLMError, float], None]] = None,
        http: Optional[httpx.Client] = None,
    ):
        name, self.model, mock_url = parse_spec(spec)
        self.provider = PROVIDERS[name]()
        self.base_url = (base_url or mock_url or self.provider.default_base_url).rstrip("/")
        self.is_mock = mock_url is not None and base_url is None
        self.api_key = api_key or ("mock-key" if mock_url else self._key_from_env())
        self.retry = retry or RetryPolicy()
        self.prices = prices
        self.on_retry = on_retry
        self.http = http or httpx.Client(timeout=timeout)

    def _key_from_env(self) -> str:
        for var in self.provider.key_env:
            if os.environ.get(var):
                return os.environ[var]
        raise LLMError(f"no API key: set {' or '.join(self.provider.key_env)} in .env",
                       provider=self.provider.name, kind="authentication_error")

    # ------------------------------------------------------------ helpers
    def _request(self, req: Union[ChatRequest, str], **kw) -> ChatRequest:
        return ChatRequest.from_prompt(req, **kw) if isinstance(req, str) else req

    def _finish(self, text: str, raw_stop: str, usage: Usage, rid: Optional[str],
                t0: float, ttft: Optional[float], attempts: int, partial: bool = False,
                tool_calls: Optional[list] = None, raw_output=None) -> ChatResult:
        return ChatResult(
            tool_calls=list(tool_calls or []),
            raw_output=raw_output,
            text=text,
            stop_reason=self.provider.map_stop(raw_stop),
            raw_stop_reason=raw_stop,
            usage=usage,
            provider=self.provider.name,
            model=self.model,
            cost_usd=cost_usd(self.model, usage, self.prices),
            latency_s=time.perf_counter() - t0,
            ttft_s=ttft,
            request_id=rid,
            attempts=attempts,
            partial=partial,
        )

    def _transport_error(self, exc: Exception) -> LLMError:
        kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
        return LLMError(f"{type(exc).__name__}: {exc}", provider=self.provider.name, kind=kind)

    # ------------------------------------------------------------ non-streaming
    def _complete_once(self, req: ChatRequest):
        call = self.provider.build(req, self.model, self.api_key, stream=False)
        try:
            resp = self.http.post(self.base_url + call.path, headers=call.headers, json=call.body)
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from None
        if resp.status_code >= 400:
            raise self.provider.error(resp.status_code, resp.text, resp.headers)
        try:
            body = resp.json()
        except json.JSONDecodeError:
            raise LLMError(f"malformed JSON: {resp.text[:120]!r}", provider=self.provider.name,
                           kind="malformed_response") from None
        return self.provider.parse(body, resp.headers)

    def complete(self, req: Union[ChatRequest, str], *, stream: bool = False, **kw) -> ChatResult:
        """One call, with retries. stream=True collects a stream internally, which
        also measures TTFT; a broken stream is retried from scratch, since nothing
        was shown to a user yet."""
        req = self._request(req, **kw)
        t0 = time.perf_counter()
        if stream:
            def once():
                return self._collect_stream(req, time.perf_counter())
            (result, attempts) = call_with_retry(once, self.retry, self.on_retry)
            result.attempts = attempts
            result.latency_s = time.perf_counter() - t0
            return result
        parsed, attempts = call_with_retry(lambda: self._complete_once(req), self.retry, self.on_retry)
        return self._finish(parsed.text, parsed.raw_stop, parsed.usage, parsed.request_id, t0, None, attempts,
                            tool_calls=parsed.tool_calls, raw_output=parsed.raw_output)

    # ------------------------------------------------------------ streaming
    def _open_stream(self, req: ChatRequest):
        call = self.provider.build(req, self.model, self.api_key, stream=True)
        try:
            cm = self.http.stream("POST", self.base_url + call.path, headers=call.headers, json=call.body)
            resp = cm.__enter__()
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from None
        if resp.status_code >= 400:
            resp.read()
            cm.__exit__(None, None, None)
            raise self.provider.error(resp.status_code, resp.text, resp.headers)
        return cm, resp

    def _items(self, resp):
        try:
            yield from self.provider.parse_stream(iter_sse(resp.iter_lines()), resp.headers)
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from None

    def _collect_stream(self, req: ChatRequest, t0: float) -> ChatResult:
        cm, resp = self._open_stream(req)
        parts, ttft = [], None
        try:
            for item in self._items(resp):
                if isinstance(item, TextDelta):
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    parts.append(item.text)
                elif isinstance(item, StreamEnd):
                    return self._finish("".join(parts), item.raw_stop, item.usage, item.request_id,
                                        t0, ttft, 1, tool_calls=item.tool_calls, raw_output=item.raw_output)
        finally:
            cm.__exit__(None, None, None)
        raise LLMError("stream ended unexpectedly", provider=self.provider.name, kind="stream_truncated")

    def stream(self, req: Union[ChatRequest, str], **kw) -> Iterator[StreamEvent]:
        """Yield text as it arrives, then a final 'done' event with the ChatResult.

        Retries happen only BEFORE the first text arrives. After that a failure is
        raised as LLMError with .partial_text, and the caller decides what the user
        sees (restart, or keep the partial answer and mark it)."""
        req = self._request(req, **kw)
        t0 = time.perf_counter()
        attempt = 0
        while True:
            attempt += 1
            parts: list[str] = []
            emitted = False  # anything yielded yet (text or tool-call pieces)?
            ttft = None
            try:
                cm, resp = self._open_stream(req)
                try:
                    for item in self._items(resp):
                        if isinstance(item, TextDelta):
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            parts.append(item.text)
                            emitted = True
                            yield StreamEvent("text", item.text)
                        elif isinstance(item, ToolCallDelta):
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            emitted = True
                            yield StreamEvent("tool_call_delta", item.partial_json,
                                              tool_call=ToolCall(id=item.id, name=item.name))
                        elif isinstance(item, ToolCallDone):
                            if ttft is None:
                                ttft = time.perf_counter() - t0
                            emitted = True
                            yield StreamEvent("tool_call", tool_call=item.call)
                        else:
                            yield StreamEvent("done", result=self._finish(
                                "".join(parts), item.raw_stop, item.usage, item.request_id,
                                t0, ttft, attempt, tool_calls=item.tool_calls, raw_output=item.raw_output))
                            return
                finally:
                    cm.__exit__(None, None, None)
            except LLMError as err:
                if parts or emitted:  # output already shown: do not silently restart
                    err.partial_text = "".join(parts)
                    raise
                decision = self.retry.classify(err)
                if not decision.retry or attempt >= self.retry.max_attempts:
                    raise
                wait = self.retry.delay(attempt - 1, self.retry.base, self.retry.cap,
                                        decision.retry_after, self.retry.rng)
                if self.on_retry:
                    self.on_retry(attempt, err, wait)
                self.retry.sleep(wait)

    def close(self) -> None:
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

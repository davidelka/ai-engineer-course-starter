"""Company Brain API v0.

    POST /v1/answer          JSON in, JSON out (Idempotency-Key supported)
    POST /v1/answer/stream   JSON in, Server-Sent Events out:
                             event: meta   {"id", "model", "citations"}
                             event: token  {"text"}            (many)
                             event: done   {"usage", "cost_usd", "latency_ms", "ttft_ms", "stop_reason"}
                             event: error  {problem+json body} (an error AFTER the 200 was sent)
    GET  /healthz            liveness: the process is up
    GET  /readyz             readiness: send me traffic (false while draining)
    GET  /admin/stats        gate, rate limiter, idempotency and upstream-stream counters

The order of checks on every request is the cheap-to-expensive order:
    auth -> rate limit (per key) -> idempotency -> concurrency gate -> LLM call (with deadline)
Every refusal happens before any money is spent, and before a 200 is sent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Literal, Optional

import anyio
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.sse import format_sse_event
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from llmkit import LLMError

from . import brain
from .async_llm import AsyncLLM, UpstreamStats, leaky_stream, threaded_stream
from .gate import ConcurrencyGate, GateRejected
from .idempotency import IdempotencyStore, fingerprint
from .logs import RequestContextMiddleware, log, setup_logging
from .problems import Problem, problem_response
from .ratelimit import KeyedRateLimiter, ratelimit_headers

API_VERSION = "0.1.0"
StreamMode = Literal["async", "thread", "leaky"]


@dataclass
class Settings:
    model: str = "mock:mock-model"
    base_url: Optional[str] = None  # override the upstream URL (tests point it at a mock on a free port)
    stream_mode: StreamMode = "async"
    max_concurrency: int = 8
    max_queue: int = 16
    queue_timeout: float = 2.0
    rate: float = 2.0  # requests per second per API key (token refill rate)
    burst: float = 5.0  # bucket size
    request_timeout: float = 30.0  # JSON endpoint: whole-request deadline
    first_token_timeout: float = 15.0  # stream: deadline for the first token
    idle_timeout: float = 15.0  # stream: max gap between tokens
    max_tokens_cap: int = 2048
    idempotency_ttl: float = 86_400.0
    # API key -> client id. Dev keys only; real keys come from a secret store (lesson 27).
    api_keys: dict = field(default_factory=lambda: {"dev-key-alice": "alice", "dev-key-bob": "bob"})


# ------------------------------------------------------------------ schemas
class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000, description="A question about Acme")
    max_tokens: int = Field(400, ge=16, le=4096, description="Upper bound on answer length")


class Citation(BaseModel):
    n: int
    doc: str
    section: str


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int


class AnswerResponse(BaseModel):
    id: str
    answer: str
    citations: list[Citation]
    model: str
    stop_reason: str
    usage: UsageOut
    cost_usd: Optional[float]
    latency_ms: int


PROBLEM_RESPONSES = {
    s: {"content": {"application/problem+json": {}}, "description": d}
    for s, d in [(401, "Missing or unknown API key"), (409, "Idempotency-Key in use"),
                 (422, "Invalid body, or Idempotency-Key reused with another body"),
                 (429, "Rate limited or overloaded; see Retry-After"),
                 (502, "Upstream error"), (503, "Upstream overloaded"), (504, "Upstream timeout")]
}


# ------------------------------------------------------------------ helpers
def upstream_problem(err: LLMError) -> Problem:
    """Map a provider failure to OUR contract. The provider's own message goes to the
    log (with the request id), not to the client: it can reveal internals."""
    log("upstream_error", level=logging.WARNING, provider=err.provider, status=err.status, kind=err.kind,
        provider_request_id=err.request_id, message=err.message[:300])
    what = f"status {err.status}" if err.status else err.kind or "error"
    if err.kind == "timeout":
        return Problem("upstream-timeout", "The provider did not answer in time.")
    if err.status in (429, 503, 529) or err.kind in ("overloaded_error", "rate_limit_error"):
        return Problem("upstream-unavailable", f"The provider is overloaded ({what}). Retry later.",
                       retry_after=max(1, math.ceil(err.retry_after or 5)))
    return Problem("upstream-error", f"The provider returned an error ({what}). Quote the request_id.")


def gate_problem(r: GateRejected) -> Problem:
    why = "the wait queue is full" if r.reason == "queue_full" else "no slot freed up in time"
    return Problem("overloaded", f"Server is at capacity: {why}.", retry_after=r.retry_after, reason=r.reason)


class ClientGone(Exception):
    pass


async def run_until_disconnect(request: Request, coro, timeout: float):
    """Await `coro` with a deadline, and cancel it if the client hangs up first.
    Starlette does not cancel a normal (non-streaming) handler on disconnect, so
    without this a client that gave up still costs a full LLM call."""
    task = asyncio.ensure_future(coro)

    async def watch():
        while not await request.is_disconnected():
            await asyncio.sleep(0.2)

    watcher = asyncio.ensure_future(watch())
    try:
        done, _ = await asyncio.wait({task, watcher}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            return task.result()
        if watcher in done:
            raise ClientGone()
        raise Problem("upstream-timeout", f"No answer within {timeout:g}s.")
    finally:
        watcher.cancel()
        if not task.done():
            task.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(task, return_exceptions=True)


class GatedSSE(StreamingResponse):
    """An SSE response that owns a gate slot and its upstream stream.

    Whatever happens (normal end, client disconnect, error, response never
    started), __call__'s finally closes the body generator, which closes the
    upstream stream, and then gives the slot back. Exactly once."""

    media_type = "text/event-stream"

    def __init__(self, content: AsyncIterator[bytes], release: Callable[[], None], **kw):
        super().__init__(content, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                           **kw.pop("headers", {})}, **kw)
        self._release = release

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                await self.body_iterator.aclose()
            self._release()


def sse(event: str, data: dict) -> bytes:
    return format_sse_event(event=event, data_str=json.dumps(data, ensure_ascii=False))


# ------------------------------------------------------------------ app factory
def create_app(settings: Optional[Settings] = None, *, rate_limiter=None, gate=None,
               idempotency=None, llm: Optional[AsyncLLM] = None) -> FastAPI:
    """Build the app. The lab passes its own rate_limiter / gate / idempotency
    objects (from mine.py) to run the service on the student's code."""
    s = settings or Settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.llm = llm if llm is not None else AsyncLLM(s.model, base_url=s.base_url)
        app.state.ready = True
        yield
        app.state.ready = False  # draining: readiness fails, in-flight requests finish
        await app.state.llm.aclose()

    app = FastAPI(title="Company Brain API", version=API_VERSION, lifespan=lifespan,
                  description="Answers questions about Acme with citations. Errors are application/problem+json.")
    app.state.settings = s
    # `is not None`, not `or`: these objects define __len__, so an empty one is falsy.
    app.state.limiter = rate_limiter if rate_limiter is not None else KeyedRateLimiter(s.rate, s.burst)
    app.state.gate = gate if gate is not None else ConcurrencyGate(s.max_concurrency, s.max_queue, s.queue_timeout)
    app.state.idem = idempotency if idempotency is not None else IdempotencyStore(s.idempotency_ttl)
    app.state.upstream = UpstreamStats()
    app.state.ready = False
    app.add_middleware(RequestContextMiddleware)

    # ---------------- error contract
    def rid(request: Request) -> str:
        return request.scope.get("state", {}).get("request_id", "")

    @app.exception_handler(Problem)
    async def _problem(request: Request, p: Problem):
        request.state.log.update(problem=p.slug)
        return problem_response(p, request.url.path, rid(request))

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError):
        errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")}
                  for e in exc.errors()]  # no "input": never echo request content into errors/logs
        p = Problem("validation-error", f"{len(errors)} problem(s) in the request.", errors=errors)
        request.state.log.update(problem=p.slug)
        return problem_response(p, request.url.path, rid(request))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        slug = {404: "not-found", 405: "method-not-allowed"}.get(exc.status_code, "internal-error")
        return problem_response(Problem(slug, str(exc.detail), status=exc.status_code), request.url.path, rid(request))

    @app.exception_handler(Exception)
    async def _crash(request: Request, exc: Exception):
        # The detail never contains the exception text: it may hold secrets or internals.
        return problem_response(Problem("internal-error", "Unexpected error. Quote the request_id when reporting."),
                                request.url.path, rid(request))

    # ---------------- dependencies
    def authenticate(request: Request) -> str:
        auth = request.headers.get("authorization", "")
        key = auth[7:].strip() if auth.lower().startswith("bearer ") else request.headers.get("x-api-key", "")
        client = s.api_keys.get(key)
        if not client:
            raise Problem("unauthenticated", "Send 'Authorization: Bearer <key>'.",
                          headers={"WWW-Authenticate": "Bearer"})
        request.state.log["client"] = client  # the client id, never the key
        return client

    def rate_limited(request: Request, client: str = Depends(authenticate)) -> str:
        d = app.state.limiter.check(client)
        headers = ratelimit_headers("per-key", d)
        request.state.rl_headers = headers
        if not d.allowed:
            wait = d.retry_after
            raise Problem("rate-limited",
                          f"Client '{client}' exceeded {s.rate:g} requests/second (burst {s.burst:g}).",
                          retry_after=max(1, math.ceil(wait)) if math.isfinite(wait) else 3600, headers=headers)
        return client

    router = APIRouter(prefix="/v1", tags=["v1"])

    # ---------------- POST /v1/answer
    @router.post("/answer", response_model=AnswerResponse, responses=PROBLEM_RESPONSES)
    async def answer(body: AnswerRequest, request: Request, client: str = Depends(rate_limited)):
        idem_key = request.headers.get("idempotency-key")
        if idem_key is not None:
            if not 1 <= len(idem_key) <= 255:
                raise Problem("validation-error", "Idempotency-Key must be 1 to 255 characters.")
            b = app.state.idem.begin(client, idem_key, fingerprint(body.model_dump()))
            if b.outcome == "replay":
                request.state.log["outcome"] = "idempotent_replay"
                return JSONResponse(b.response, status_code=b.status,
                                    headers={**b.headers, "Idempotent-Replayed": "true"})
            if b.outcome == "in_progress":
                raise Problem("idempotency-key-in-use", "Wait for the first request to finish, then retry.",
                              retry_after=1)
            if b.outcome == "mismatch":
                raise Problem("idempotency-key-mismatch", "Use a new Idempotency-Key for a different request.")
        try:
            try:
                await app.state.gate.acquire()
            except GateRejected as r:
                raise gate_problem(r) from None
            t0 = time.perf_counter()
            try:
                hits = brain.retrieve(body.question)
                req = brain.build_request(body.question, min(body.max_tokens, s.max_tokens_cap), hits)
                try:
                    result = await run_until_disconnect(request, app.state.llm.complete(req), s.request_timeout)
                except LLMError as err:
                    raise upstream_problem(err) from None
            finally:
                app.state.gate.release(time.perf_counter() - t0)
        except ClientGone:
            if idem_key:
                app.state.idem.abandon(client, idem_key)
            request.state.log["outcome"] = "client_disconnected"
            return Response(status_code=499)  # nginx's code for "client closed request"; nobody reads it
        except BaseException:
            if idem_key:
                app.state.idem.abandon(client, idem_key)  # let the client's retry run for real
            raise
        payload = AnswerResponse(
            id="ans_" + uuid.uuid4().hex[:16], answer=result.text, citations=brain.citations(hits),
            model=result.model, stop_reason=result.stop_reason,
            usage=UsageOut(input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens),
            cost_usd=result.cost_usd, latency_ms=round(result.latency_s * 1000)).model_dump()
        headers = dict(request.state.rl_headers)
        if idem_key:
            app.state.idem.complete(client, idem_key, 200, payload)
        request.state.log.update(outcome="ok", output_tokens=result.usage.output_tokens)
        return JSONResponse(payload, headers=headers)

    # ---------------- POST /v1/answer/stream
    @router.post("/answer/stream", responses={200: {"content": {"text/event-stream": {}}}, **PROBLEM_RESPONSES})
    async def answer_stream(body: AnswerRequest, request: Request, client: str = Depends(rate_limited)):
        gate: ConcurrencyGate = app.state.gate
        try:
            await gate.acquire()
        except GateRejected as r:
            raise gate_problem(r) from None
        t_admit = time.perf_counter()
        released = False

        def release():
            nonlocal released
            if not released:
                released = True
                gate.release(time.perf_counter() - t_admit)

        try:
            hits = brain.retrieve(body.question)
            req = brain.build_request(body.question, min(body.max_tokens, s.max_tokens_cap), hits)
            log = request.state.log
            up: UpstreamStats = app.state.upstream
            answer_id = "ans_" + uuid.uuid4().hex[:16]
            request_id = rid(request)
            mode = s.stream_mode
            llm_ = app.state.llm

            async def events() -> AsyncIterator[bytes]:
                yield sse("meta", {"id": answer_id, "model": llm_.model, "citations": brain.citations(hits)})
                if mode == "thread":
                    it = threaded_stream(llm_.sync, req)
                elif mode == "leaky":
                    it = leaky_stream(llm_, req)
                else:
                    it = llm_.stream(req)
                up.opened += 1
                up.active += 1
                up.by_mode[mode] = up.by_mode.get(mode, 0) + 1
                finished, n, t0 = False, 0, time.perf_counter()
                log.update(outcome="client_disconnected", stream_mode=mode)
                try:
                    while True:
                        try:
                            ev = await asyncio.wait_for(
                                it.__anext__(), s.first_token_timeout if n == 0 else s.idle_timeout)
                        except StopAsyncIteration:
                            break
                        if ev.type == "text":
                            n += 1
                            up.events += 1
                            if n == 1:
                                log["ttft_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                            yield sse("token", {"text": ev.text})
                        else:
                            r = ev.result
                            finished = True
                            log.update(outcome="ok", output_tokens=r.usage.output_tokens)
                            yield sse("done", {"stop_reason": r.stop_reason, "cost_usd": r.cost_usd,
                                               "usage": {"input_tokens": r.usage.input_tokens,
                                                         "output_tokens": r.usage.output_tokens},
                                               "latency_ms": round(r.latency_s * 1000),
                                               "ttft_ms": round((r.ttft_s or 0) * 1000)})
                            break
                except asyncio.TimeoutError:
                    log["outcome"] = "upstream_timeout"
                    p = Problem("upstream-timeout", "The model stopped sending tokens.")
                    yield sse("error", p.body(request.url.path, request_id))
                except LLMError as err:
                    log["outcome"] = "upstream_error"
                    yield sse("error", upstream_problem(err).body(request.url.path, request_id))
                finally:
                    with anyio.CancelScope(shield=True):
                        await it.aclose()  # closes the upstream HTTP stream (except in leaky mode)
                    up.active -= 1
                    if finished:
                        up.finished += 1
                    else:
                        up.closed_early += 1
                    log["tokens_sent"] = n

            return GatedSSE(events(), release, headers=dict(request.state.rl_headers))
        except BaseException:
            release()
            raise

    app.include_router(router)

    # ---------------- operations
    @app.get("/healthz", tags=["ops"])
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz():
        # Readiness is about THIS process: never call the paid LLM from a probe that runs every few seconds.
        if not app.state.ready:
            raise Problem("not-ready", "Starting up or draining.")
        return {"ready": True, "model": s.model, "stream_mode": s.stream_mode}

    @app.get("/admin/stats", tags=["ops"])
    async def stats():
        return {"version": API_VERSION, "gate": app.state.gate.stats() if hasattr(app.state.gate, "stats") else {},
                "rate_limited_keys": len(app.state.limiter) if hasattr(app.state.limiter, "__len__") else None,
                "idempotency_entries": len(app.state.idem) if hasattr(app.state.idem, "__len__") else None,
                "upstream": app.state.upstream.as_dict(),
                "threads": {"limit": anyio.to_thread.current_default_thread_limiter().total_tokens,
                            "busy": anyio.to_thread.current_default_thread_limiter().borrowed_tokens}}

    return app

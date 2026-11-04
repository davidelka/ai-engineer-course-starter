"""Company Brain mini API: the service lesson 27 puts in a container and deploys.

Shaped like the lesson 26 service (servekit), so either can be deployed with the same
Dockerfile, compose file and Terraform:

  GET  /healthz            liveness: the process is up (no dependencies checked)
  GET  /readyz             readiness: config is valid; mock mode: mockllm answers; live mode: a key is
                           loaded (the provider itself is NOT probed, on purpose)
  POST /v1/answer          {"question": "..."} -> {"answer": "...", "model": ..., "cost_usd": ...}
  POST /v1/answer/stream   the same, as Server-Sent Events: event text ... event done

Logs are one JSON object per line on stdout: that is what `docker logs` and CloudWatch
(the awslogs driver) collect, and what Logs Insights can query.

Run locally without Docker:
    PYTHONPATH=.:labs/27-deployment/app uvicorn service.main:app --port 8000
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from llmkit import LLM, LLMError

from .settings import Settings

log = logging.getLogger("company_brain")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": round(record.created, 3), "level": record.levelname.lower(), "msg": record.getMessage()}
        out.update(getattr(record, "fields", {}))
        return json.dumps(out, ensure_ascii=False)


def setup_logging() -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    log.handlers[:] = [h]
    log.setLevel(logging.INFO)
    log.propagate = False


def jlog(msg: str, **fields) -> None:
    log.info(msg, extra={"fields": fields})


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4096)


class AnswerResponse(BaseModel):
    answer: str
    model: str
    provider: str
    stop_reason: str
    input_tokens: int
    output_tokens: int
    cost_usd: Optional[float]
    latency_s: float
    request_id: str


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(settings: Optional[Settings] = None, llm: Optional[LLM] = None) -> FastAPI:
    settings = settings or Settings.from_env()  # a bad config crashes at startup: fail fast
    setup_logging()
    if llm is None:
        base = settings.mockllm_url if settings.is_mock else None
        llm = LLM(settings.llm_model, api_key=settings.api_key, base_url=base)
    app = FastAPI(title="Company Brain mini API", version=settings.app_version)
    app.state.settings, app.state.llm = settings, llm
    jlog("startup", **settings.describe())

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        request.state.rid = rid
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        if request.url.path not in ("/healthz",):  # health checks every few seconds would drown the logs
            jlog("request", rid=rid, method=request.method, path=request.url.path,
                 status=response.status_code, ms=round((time.perf_counter() - t0) * 1000, 1))
        return response

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": settings.app_version}

    @app.get("/readyz")
    def readyz():
        if settings.is_mock:
            try:
                httpx.get(settings.mockllm_url + "/__admin/stats", timeout=1.0).raise_for_status()
            except httpx.HTTPError as exc:
                return JSONResponse({"status": "not_ready", "reason": f"mockllm unreachable: {type(exc).__name__}"},
                                    status_code=503)
        elif not settings.api_key:
            return JSONResponse({"status": "not_ready", "reason": "no API key"}, status_code=503)
        # On purpose, readiness does NOT call the paid API. Cost: the ALB checks /readyz every 15 seconds
        # from at least 2 nodes, ~345k paid calls a month per task (~520k with ECS's /healthz too, if
        # that called the model). And in ECS a failed ALB check replaces the task, so a provider outage
        # would make ECS replace every task in a loop.
        return {"status": "ready", "model": settings.llm_model, "key_source": settings.key_source}

    @app.post("/v1/answer", response_model=AnswerResponse)
    def answer(body: AnswerRequest, request: Request):
        # a plain `def`: FastAPI runs it in a thread pool, so the blocking HTTP call
        # to the model does not freeze the event loop for other requests
        try:
            r = llm.complete(body.question, system=settings.system_prompt,
                             max_tokens=body.max_tokens or settings.max_tokens)
        except LLMError as err:
            jlog("llm_error", rid=request.state.rid, kind=err.kind, status=getattr(err, "status", None))
            return JSONResponse({"error": err.kind or "llm_error", "request_id": request.state.rid}, status_code=502)
        jlog("answer", rid=request.state.rid, model=r.model, in_tok=r.usage.input_tokens,
             out_tok=r.usage.output_tokens, cost_usd=r.cost_usd, llm_s=round(r.latency_s, 3))
        return AnswerResponse(answer=r.text, model=r.model, provider=r.provider, stop_reason=r.stop_reason,
                              input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens,
                              cost_usd=r.cost_usd, latency_s=round(r.latency_s, 3), request_id=request.state.rid)

    @app.post("/v1/answer/stream")
    def answer_stream(body: AnswerRequest, request: Request):
        rid = request.state.rid

        def events():
            try:
                for ev in llm.stream(body.question, system=settings.system_prompt,
                                     max_tokens=body.max_tokens or settings.max_tokens):
                    if ev.type == "text":
                        yield _sse("text", {"text": ev.text})
                    else:
                        r = ev.result
                        jlog("answer_stream", rid=rid, model=r.model, out_tok=r.usage.output_tokens,
                             cost_usd=r.cost_usd, ttft_s=r.ttft_s)
                        yield _sse("done", {"model": r.model, "stop_reason": r.stop_reason, "cost_usd": r.cost_usd,
                                            "output_tokens": r.usage.output_tokens, "request_id": rid})
            except LLMError as err:
                jlog("llm_error", rid=rid, kind=err.kind, partial=bool(getattr(err, "partial_text", "")))
                yield _sse("error", {"error": err.kind or "llm_error", "request_id": rid})

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"cache-control": "no-cache", "x-accel-buffering": "no"})

    return app


app = create_app()

"""The Company Brain HTTP API and its single-page UI.

    python -m cbrain serve                    # http://127.0.0.1:8000  (BRAIN_DEMO_KEYS=1 for the user picker)

Auth: every endpoint except /healthz, /readyz and the UI page needs an API key
(Authorization: Bearer <key> or X-API-Key). The key gives a Principal (auth.py); roles open endpoints,
the directory (via flowkit) gives authority over a specific request.

    POST /ask                      {question, stream=true}   SSE: intent, [guard], route, sources, token..., answer, done
                                   (an access request gets intent + confirm{preview, confirm_token} instead of an answer)
    POST /requests/preview         {text}            what filing would do + a single-use confirm_token
    POST /requests                 {text, confirm_token, stream=false}   start the workflow (SSE progress with stream)
    GET  /requests                 my requests (security/admin: ?all=1 for every request)
    GET  /requests/{id}            status, policy reasons, decision, notifications, audit (404 if not yours to see)
    GET  /approvals                requests waiting for ME (manager/security roles)
    POST /approvals/{id}           {decision: approve|reject, comment}   resume the paused workflow
    POST /admin/seed               demo requests in a fresh deployment (admin; the one writer process does it)
    GET  /metrics/slo              SLO report + cost per request type from this process's traces (admin)
    GET  /api/me                   who am I (and, with demo keys, the demo users for the picker)
    GET  /healthz, /readyz

Errors are application/problem+json (servekit.problems, RFC 9457). Streams run the brain's generator
in ONE worker thread and hand events to the event loop through a queue: the knowledge path keeps
per-request state in contextvars and OpenTelemetry context, which must not hop between threads
(Starlette's default iterate_in_threadpool would run every next() on a different thread).
"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from servekit.problems import PROBLEM_CONTENT_TYPE

from .auth import presented_key
from .brain import Brain

UI = Path(__file__).resolve().parent / "ui" / "index.html"


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    stream: bool = True


class PreviewBody(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


class FileBody(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    confirm_token: str = Field(min_length=8, max_length=200)
    stream: bool = False


class DecisionBody(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str = Field(default="", max_length=1000)


def problem(status: int, slug: str, title: str, detail: str = "") -> JSONResponse:
    return JSONResponse({"type": f"https://acme.example/problems/{slug}", "title": title, "status": status,
                         "detail": detail}, status_code=status, media_type=PROBLEM_CONTENT_TYPE)


def sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n".encode("utf-8")


_END = object()


def threaded(gen_fn: Callable[[], Iterator[dict]]):
    """Run a sync event generator to completion in one thread; yield its events asynchronously."""
    q: "queue.Queue[Any]" = queue.Queue(maxsize=256)

    def work():
        try:
            for ev in gen_fn():
                q.put(ev)
        except Exception as exc:  # noqa: BLE001  (an error after the stream started is an event)
            q.put({"event": "error", "data": {"detail": f"{type(exc).__name__}: {exc}"}})
        finally:
            q.put(_END)

    threading.Thread(target=work, daemon=True).start()

    async def agen():
        loop = asyncio.get_running_loop()
        while True:
            ev = await loop.run_in_executor(None, q.get)
            if ev is _END:
                break
            yield sse(ev["event"], ev["data"])
    return agen()


def collect(gen_fn: Callable[[], Iterator[dict]]) -> list[dict]:
    out: list[dict] = []
    t = threading.Thread(target=lambda: out.extend(gen_fn()))
    t.start()
    t.join()
    return out


def create_app(brain: Optional[Brain] = None) -> FastAPI:
    b = brain or Brain.from_env()
    app = FastAPI(title="Company Brain", version="1.0.0", description="Acme's Company Brain (course project F1)")
    app.state.brain = b

    def who(request: Request):
        return b.keys.lookup(presented_key(dict(request.headers)))

    def need(request: Request, *roles: str):
        p = who(request)
        if p is None:
            return None, problem(401, "unauthenticated", "Missing or unknown API key",
                                 "Send Authorization: Bearer <key> (or X-API-Key).")
        if roles and not p.has(*roles):
            return None, problem(403, "forbidden", "Not allowed for your role", f"Needs one of: {', '.join(roles)}.")
        return p, None

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(UI, media_type="text/html; charset=utf-8")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/readyz")
    def readyz():
        r = b.ready()
        return JSONResponse(r, status_code=200 if r["ready"] else 503)

    @app.get("/api/me")
    def me(request: Request):
        p, err = need(request)
        out: dict = {"demo_keys": b.keys.demo}
        if err:
            if b.keys.demo:   # the picker needs the list before anyone is logged in
                out["users"] = [u.public() for u in b.users.values()]
                return JSONResponse(out, status_code=401)
            return err
        out["me"] = p.public()
        if b.keys.demo:
            out["users"] = [u.public() for u in b.users.values()]
        return out

    @app.post("/ask")
    def ask(body: AskBody, request: Request):
        p, err = need(request)
        if err:
            return err
        gen = lambda: b.ask_events(p, body.question)  # noqa: E731
        if body.stream:
            return StreamingResponse(threaded(gen), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        events = collect(gen)
        return {"events": events}

    @app.post("/requests/preview")
    def preview(body: PreviewBody, request: Request):
        p, err = need(request)
        if err:
            return err
        return collect(lambda: [b.preview(p, body.text)])[0]

    @app.post("/requests")
    def file_request(body: FileBody, request: Request):
        p, err = need(request)
        if err:
            return err
        if not b.check_token(p, body.text, body.confirm_token):
            return problem(409, "confirmation-required", "Confirm the preview first",
                           "Missing, expired, reused or mismatched confirmation token. Preview the request again.")
        token = b.confirm.approve(b._call(p, body.text))   # re-issue internally: check() consumed the user's token
        gen = lambda: b.file_request_events(p, body.text, token)  # noqa: E731
        if body.stream:
            return StreamingResponse(threaded(gen), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
        events = collect(gen)
        summary = next((e["data"] for e in events if e["event"] == "summary"), None)
        return JSONResponse({"summary": summary, "events": events}, status_code=201)

    @app.get("/requests")
    def list_requests(request: Request, all: int = 0):
        p, err = need(request)
        if err:
            return err
        if all and not p.has("security", "admin"):
            return problem(403, "forbidden", "Not allowed for your role", "Only security and admin see every request.")
        rows = b.requests.threads(None if all else p.email)
        return {"requests": [{**r, **{k: v for k, v in b.requests.status(r["thread_id"]).items()
                                      if k in ("status", "route", "request_id", "gate")}} for r in rows]}

    @app.get("/requests/{tid}")
    def get_request(tid: str, request: Request):
        p, err = need(request)
        if err:
            return err
        if not b.requests.can_view(p, tid):
            return problem(404, "not-found", "Not found", f"No request {tid} that you may see.")
        return b.requests.status(tid)

    @app.get("/approvals")
    def approvals(request: Request):
        p, err = need(request, "manager", "security")
        if err:
            return err
        return {"pending": b.requests.inbox(p)}

    @app.post("/approvals/{tid}")
    def decide(tid: str, body: DecisionBody, request: Request):
        p, err = need(request, "manager", "security")
        if err:
            return err
        if not b.requests.can_view(p, tid):
            return problem(404, "not-found", "Not found", f"No request {tid} that you may see.")
        res = collect(lambda: [b.decide(p, tid, body.decision, body.comment)])[0]
        if not res["ok"]:
            return problem(403 if "forbidden" in (res["error"] or "") else 409, "decision-refused",
                           "The decision was not accepted", res["error"] or "")
        return res["summary"]

    @app.post("/admin/seed")
    def admin_seed(request: Request):
        p, err = need(request, "admin")
        if err:
            return err
        from .seed import seed
        return collect(lambda: [seed(b)])[0]

    @app.get("/metrics/slo")
    def metrics(request: Request):
        p, err = need(request, "admin")
        if err:
            return err
        from .obs import slo_report
        return slo_report(b.spans())

    return app


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(create_app(), host=host, port=port, log_level="info")

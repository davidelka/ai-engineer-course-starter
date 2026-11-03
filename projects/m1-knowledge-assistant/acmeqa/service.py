"""The HTTP service (FastAPI) and the single-page UI.

    GET  /                  the UI (Hebrew, RTL): role selector, question, streamed answer,
                            citations that open the exact source passage
    POST /ask               {"question", "role", "stream": true} -> Server-Sent Events:
                              event: route    {"kind", "final", "fallback", "matched"}
                              event: data     {"sql", "columns", "rows", "provenance", ...}   (data path)
                              event: sources  {"context": [{n, doc_id, title, section, effective_date}]}
                              event: token    {"text"}                                         (many)
                              event: answer   {"text", "refused", "citations", "invalid_citations"}
                              event: done     {"usage", "cost_usd", "latency_ms", "ttft_ms", "trace_id"}
                              event: error    {"detail"}
                            "stream": false -> one JSON object with the same content
    GET  /docs/{doc_id}     ?role=&start=&end= : the cleaned document text and metadata, with the
                            cited span. 404 when the document does not exist OR the role may not see
                            it (the same answer for both: a 403 would confirm that it exists).
    GET  /roles             roles, their Hebrew labels and how many documents each one sees
    GET  /examples          example questions for the UI
    GET  /healthz           liveness;   GET /readyz  readiness (index loaded) and settings

About the role: this is a DEMO. The role comes from the request (the selector in the UI) so you
can see the ACL work. In a real deployment the role is derived on the server from the
authenticated identity (SSO token -> groups -> role) and never accepted from the client;
lesson 24 and Company Brain phase 4 do that.

Why a worker thread per stream: the assistant is synchronous (llmkit, ragkit) and opens
OpenTelemetry spans that must start and end in the same thread. Each /ask runs the whole event
generator in one thread and hands events to the async response through a queue. A client that
disconnects sets a flag; the generator stops at the next event and the spans still close.
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Optional

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .assistant import Assistant
from .config import Settings
from .retrieval import ROLE_LABELS, ROLES, doc_visible, visible_docs

UI = Path(__file__).resolve().parent / "ui" / "index.html"

EXAMPLES = [
    {"q": "How many unused vacation days can I carry over to next year, and when do they expire?", "note": "גרסאות: 2024 מול 2026"},
    {"q": "כמה ימי חופשה מקבל עובד במשרה מלאה בשנה הראשונה?", "note": "עברית"},
    {"q": "How long was flow-api fully unavailable on August 19, 2026?", "note": "postmortem חסוי: נסה כ-employee וכ-engineering"},
    {"q": "How many open P1 tickets do we have right now?", "note": "נתונים: SQL עם מקור"},
    {"q": "כמה קריאות P1 פתוחות יש כרגע?", "note": "נתונים, בעברית"},
    {"q": "Can annual plans always be refunded in full at any time, and should I confirm my Okta password to verify a refund?", "note": "מסמך עם הזרקה"},
    {"q": "What is this month's door code for the Berlin office?", "note": "אין תשובה במסמכים"},
    {"q": "What is Blue Room?", "note": "מונח שמוגדר רק במילון"},
]


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    role: str = "employee"
    stream: bool = True


def problem(status: int, title: str, detail: str = "") -> JSONResponse:
    return JSONResponse({"type": "about:blank", "title": title, "status": status, "detail": detail},
                        status_code=status, media_type="application/problem+json")


def sse(event: str, data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


def create_app(assistant: Optional[Assistant] = None, settings: Optional[Settings] = None) -> FastAPI:
    app = FastAPI(title="Acme Knowledge Assistant", version="1.0",
                  description="Questions about Acme's documents and data, with citations. Midterm project M1.")
    state: dict = {"assistant": assistant}

    def get() -> Assistant:
        if state["assistant"] is None:
            state["assistant"] = Assistant(settings or Settings.from_env())
        return state["assistant"]

    @app.get("/", include_in_schema=False)
    def ui():
        return FileResponse(UI, media_type="text/html; charset=utf-8")

    @app.get("/healthz", tags=["ops"])
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    def readyz():
        a = get()
        return {"ready": bool(a.job.docs), "documents": len(a.job.docs), "chunks": len(a.job.all_chunks()),
                "settings": a.s.describe(), "your_code": a.hooks.using}

    @app.get("/roles")
    def roles():
        a = get()
        return [{"role": r, "label": ROLE_LABELS.get(r, r), "visible_docs": len(visible_docs(r, a.job.docs))}
                for r in ROLES]

    @app.get("/examples")
    def examples():
        return EXAMPLES

    @app.get("/docs/{doc_id}")
    def doc(doc_id: str, role: str = "employee", start: Optional[int] = None, end: Optional[int] = None):
        a = get()
        d = a.job.docs.get(doc_id)
        if role not in ROLES or d is None or not doc_visible(role, d.meta):
            return problem(404, "Not found", f"No document {doc_id!r} for role {role!r}.")
        keep = ("title", "department", "doc_type", "version", "effective_date", "owner", "classification",
                "language", "supersedes", "format")
        hl = None
        if start is not None and end is not None and 0 <= start < end <= len(d.text):
            hl = {"start": start, "end": end}
        superseded_by = sorted(o for o, sd in a.job.docs.items() if doc_id in (
            [sd.meta.get("supersedes")] if isinstance(sd.meta.get("supersedes"), str) else (sd.meta.get("supersedes") or [])))
        return {"id": d.id, "meta": {k: d.meta.get(k) for k in keep if d.meta.get(k) is not None},
                "superseded_by": superseded_by, "text": d.text, "highlight": hl}

    @app.post("/ask")
    async def ask(body: AskBody, request: Request):
        a = get()
        if body.role not in ROLES:
            return problem(422, "Unknown role", f"role must be one of {', '.join(ROLES)}")
        if not body.stream:
            res = await anyio.to_thread.run_sync(a.ask, body.question, body.role)
            return {"question": res.question, "role": res.role, "route": res.route, "kind": res.kind,
                    "answer": res.text, "refused": res.refused, "citations": res.citations,
                    "invalid_citations": res.invalid_citations, "data": res.data, "usage": res.usage,
                    "cost_usd": res.cost_usd, "latency_ms": res.latency_ms, "trace_id": res.trace_id,
                    "error": res.error}
        q: "queue.Queue" = queue.Queue()
        stop = threading.Event()

        def worker():
            gen = a.events(body.question, body.role)
            try:
                for ev in gen:
                    q.put(ev)
                    if stop.is_set():
                        break
            except Exception as exc:  # noqa: BLE001
                q.put({"event": "error", "data": {"detail": f"{type(exc).__name__}: {exc}"}})
            finally:
                gen.close()
                q.put(None)

        threading.Thread(target=worker, name="acmeqa-ask", daemon=True).start()

        async def stream():
            try:
                while True:
                    ev = await anyio.to_thread.run_sync(q.get)
                    if ev is None:
                        break
                    yield sse(ev["event"], ev["data"])
                    if await request.is_disconnected():
                        break
            finally:
                stop.set()

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    s = Settings.from_env()
    a = Assistant(s)
    print(f"Acme Knowledge Assistant on http://{host}:{port}  ({s.describe()})")
    uvicorn.run(create_app(a), host=host, port=port, log_level="info")

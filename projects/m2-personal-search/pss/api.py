"""The local web UI: FastAPI on 127.0.0.1, one HTML page, five JSON endpoints.

    python -m pss serve                    # http://127.0.0.1:8765

Local-only on purpose, and enforced in three places:
- it binds to 127.0.0.1 by default (`serve --host 0.0.0.0` refuses unless --allow-remote);
- every request must carry a Host header of localhost/127.0.0.1 (a malicious web page cannot
  reach it through DNS rebinding: its requests carry the attacker's host name);
- /api/file serves ONLY files that are in the index manifest, by id. There is no path
  parameter, so "../../.ssh/id_rsa" is just an unknown id (404).

Endpoints: GET /api/status, GET /api/search?q=&mode=&k=, POST /api/ask {q, cloud, dry_run, mode},
GET /api/file/{id}, GET /api/egress, POST /api/reindex.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from . import hooks
from .answer import OllamaError, ask
from .privacy import EgressLog, PrivacyError

WEB = Path(__file__).resolve().parent / "web" / "index.html"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "testserver"}


class AskBody(BaseModel):
    q: str
    cloud: bool = False
    dry_run: bool = False
    mode: str = "hybrid"


def create_app(index, *, llm: Any = None, cloud_llm: Any = None) -> FastAPI:
    app = FastAPI(title="Personal Smart Search", docs_url=None, redoc_url=None, openapi_url=None)
    state = {"llm": llm}

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].lower()
        if host not in LOCAL_HOSTS:
            return JSONResponse({"detail": "this server answers only on localhost"}, status_code=403)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    def home():
        return HTMLResponse(WEB.read_text(encoding="utf-8"))

    @app.get("/api/status")
    def status():
        s = index.s
        return {"stats": index.stats(), "local_model": s.local_model,
                "privacy": {"cloud_enabled": s.cloud.enabled, "cloud_model": s.cloud.model,
                            "never_send": s.cloud.never_send, "redact": s.cloud.redact,
                            "excluded_patterns": s.exclude},
                "egress": EgressLog(s.egress_log).summary(), "dups": index.dups,
                "notices": hooks.notices()}

    @app.get("/api/search")
    def search(q: str, mode: str = "hybrid", k: int = 10):
        if mode not in ("bm25", "dense", "hybrid"):
            raise HTTPException(422, "mode must be bm25, dense or hybrid")
        return index.search(q, mode=mode, k=max(1, min(k, 50))).to_dict()

    @app.post("/api/ask")
    def ask_ep(body: AskBody):
        try:
            a = ask(index, body.q, llm=None if body.cloud else state["llm"], cloud=body.cloud,
                    dry_run=body.dry_run, mode=body.mode, cloud_llm=cloud_llm)
        except PrivacyError as exc:
            raise HTTPException(403, str(exc))
        except OllamaError as exc:
            raise HTTPException(503, str(exc))
        return a.to_dict()

    @app.get("/api/file/{fid:path}")
    def file(fid: str):
        p = index.file_path(fid)
        if p is None or not p.exists():
            raise HTTPException(404, "not an indexed file")
        media = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if media.startswith("text/html"):
            media = "text/plain"          # never render a saved web page (and its scripts) on localhost
        return FileResponse(p, media_type=media, content_disposition_type="inline", filename=p.name)

    @app.get("/api/egress")
    def egress(limit: int = 50):
        return {"summary": EgressLog(index.s.egress_log).summary(),
                "entries": EgressLog(index.s.egress_log).entries()[-limit:]}

    @app.post("/api/reindex")
    def reindex():
        rep = index.sync()
        return {"summary": rep.summary(), "warnings": rep.warnings}

    return app


def serve(index, host: str = "127.0.0.1", port: int = 8765, *, allow_remote: bool = False) -> None:
    import uvicorn

    if host not in ("127.0.0.1", "localhost", "::1") and not allow_remote:
        raise SystemExit("refusing to listen on a non-local address: this UI shows your private files. "
                         "Use --allow-remote only behind your own authentication.")
    uvicorn.run(create_app(index), host=host, port=port, log_level="warning")

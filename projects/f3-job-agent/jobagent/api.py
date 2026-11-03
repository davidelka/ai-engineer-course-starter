"""Admin API (FastAPI): look at runs and jobs, read and change preferences, trigger a run.

    GET  /healthz               liveness: the process answers (never touches the model)
    GET  /readyz                readiness: the state file opens and the preferences parse
    GET  /runs                  latest runs (slot, status, counts, cost)
    GET  /runs/{run_id}         one run, with the digest text
    GET  /runs/{run_id}/report  the HTML report of that run
    GET  /jobs?tier=&category=&limit=
    GET  /preferences           the current preferences (JSON)
    PUT  /preferences           replace them: validated by the Pydantic model before saving
    POST /runs                  run a slot now ({"slot": "auto" | "<key>", "force": false})

Writes (PUT /preferences, POST /runs) need the header X-Admin-Token equal to ADMIN_TOKEN from
the environment; with no ADMIN_TOKEN set, writes are refused. Errors use problem+json
(servekit.problems, lesson 26). The compose file binds the port to 127.0.0.1 only: this is a
personal admin tool, not a public service.
"""

from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ValidationError

from servekit.problems import Problem, problem_response

from .config import Settings
from .prefs import Preferences, load_prefs, save_prefs
from .store import Store


class RunRequest(BaseModel):
    slot: str = "auto"
    force: bool = False


def create_app(settings: Optional[Settings] = None, *, store: Optional[Store] = None) -> FastAPI:
    s = settings or Settings.from_env()
    st = store or Store(s.state_path)
    app = FastAPI(title="Job agent admin", version="1.0.0")

    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem):
        return problem_response(exc, instance=str(request.url.path))

    def require_admin(token: Optional[str]) -> None:
        expected = os.environ.get("ADMIN_TOKEN", "")
        if not expected:
            raise Problem("forbidden", "writes are disabled: set ADMIN_TOKEN", status=403)
        if not token or not hmac.compare_digest(token, expected):
            raise Problem("unauthorized", "missing or wrong X-Admin-Token", status=401)

    @app.get("/healthz", tags=["ops"])
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    def readyz():
        try:
            st.db.execute("SELECT 1").fetchone()
            load_prefs(s.prefs_path)
        except Exception as exc:
            return JSONResponse({"status": "not ready", "detail": type(exc).__name__}, status_code=503)
        return {"status": "ready", "last_done": st.last_done()}

    @app.get("/runs", tags=["runs"])
    def runs(limit: int = Query(20, ge=1, le=200)):
        return [{k: v for k, v in r.items() if k != "digest"} for r in st.runs(limit)]

    @app.get("/runs/{run_id}", tags=["runs"])
    def run(run_id: str):
        r = st.run(run_id)
        if not r:
            raise Problem("not-found", f"no run {run_id}", status=404)
        return r

    @app.get("/runs/{run_id}/report", tags=["runs"], response_class=HTMLResponse)
    def report(run_id: str):
        r = st.run(run_id)
        if not r or not r.get("report_path"):
            raise Problem("not-found", f"no report for {run_id}", status=404)
        path = Path(r["report_path"]).resolve()
        if s.results_dir.resolve() not in path.parents:  # only files the agent wrote
            raise Problem("not-found", "report outside the results folder", status=404)
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.get("/jobs", tags=["jobs"])
    def jobs(tier: Optional[str] = Query(None, pattern="^(match|maybe|skip)$"), category: Optional[str] = None,
             limit: int = Query(50, ge=1, le=500)):
        return st.jobs(tier=tier, category=category, limit=limit)

    @app.get("/preferences", tags=["preferences"])
    def get_prefs():
        return load_prefs(s.prefs_path).model_dump()

    @app.put("/preferences", tags=["preferences"])
    def put_prefs(body: dict, x_admin_token: Optional[str] = Header(None)):
        require_admin(x_admin_token)
        try:
            prefs = Preferences.model_validate(body)
        except ValidationError as exc:
            raise Problem("validation-error", "preferences do not validate", status=422,
                          errors=[{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()[:10]])
        save_prefs(prefs, s.prefs_path)
        return {"saved": True}

    @app.post("/runs", tags=["runs"], status_code=202)
    def trigger(req: RunRequest, x_admin_token: Optional[str] = Header(None)):
        require_admin(x_admin_token)
        from datetime import datetime

        from . import schedule
        from .__main__ import build_pipeline, pick_hooks

        slot = req.slot
        if slot == "auto":
            slot = schedule.due_slot(datetime.now(schedule.TZ), st.done_slots())
            if slot is None:
                return {"skipped": True, "reason": "nothing due"}
        res = build_pipeline(s, pick_hooks(True), store=st).run(slot, force=req.force)
        return {"slot": slot, "skipped": res.skipped, "new_jobs": len(res.new_jobs),
                "matches": len(res.digest.matches) if res.digest else 0, "cost_usd": res.cost_usd, "error": res.error}

    return app

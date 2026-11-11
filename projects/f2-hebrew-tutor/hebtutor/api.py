"""The tutor API (FastAPI): API-first, so the client's React PWA can call it, plus a one-page demo.

Auth (three kinds of caller, three headers):
    X-Admin-Token     ADMIN_TOKEN from the environment: create classes, approve/reject content
    X-Teacher-Token   returned once when a class is created: dashboard, submit content
    X-Student-Token   returned once when a student joins with the class code + a nickname

    GET  /healthz                               liveness (never touches the model)
    GET  /readyz                                the database opens and the corpus is loaded
    GET  /scenarios?level=A1                    scenario list (Arabic + Hebrew titles, map position)
    POST /admin/classes        {name}           -> {class_code, teacher_token}             (admin)
    POST /students/join        {class_code, nickname, addressing}  -> {student_id, student_token}
    POST /sessions             {scenario_id, level?}               -> opening line          (student)
    POST /sessions/{id}/turns  {text}           one assessed turn (JSON)                    (student)
    POST /sessions/{id}/turns/stream {text}     the same as Server-Sent Events:
                                                event: sentence {text} ... event: assessment {...}
    POST /sessions/{id}/practice                "say this phrase": the next audio turn gets speaking feedback
    POST /sessions/{id}/turns/audio  multipart: file (webm/wav/mp4), say (offline simulation only)
    POST /sessions/{id}/turns/image  multipart: file (jpeg/png), text
    GET  /vocab/review                          due cards (SM-2)                            (student)
    POST /vocab/review         {vocab_id, quality 0..5}                                    (student)
    GET  /progress                              points, level, per-scenario progress        (student)
    POST /teacher/content      {kind, scenario, level, he, ar, transliteration}             (teacher)
    GET  /teacher/content?status=pending                                                   (teacher or admin)
    POST /teacher/content/{id}/approve | /reject  {note}                                    (admin)
    GET  /teacher/dashboard                     students, top errors, safety events         (teacher)
    GET  /                                      the demo page (Arabic UI, Hebrew practice)

Errors are application/problem+json (servekit.problems, lesson 26).
"""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from servekit.problems import Problem, problem_response

from .service import ServiceError, TutorService

WEB = Path(__file__).resolve().parent / "web"
MAX_AUDIO = 5 * 1024 * 1024  # about 5 minutes of opus; a turn is a few seconds
MAX_IMAGE = 8 * 1024 * 1024


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class JoinIn(BaseModel):
    class_code: str
    nickname: str
    addressing: Literal["m", "f"] = "m"


class SessionIn(BaseModel):
    scenario_id: str
    level: Optional[Literal["A1", "A2", "B1"]] = None


class TurnIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ReviewIn(BaseModel):
    vocab_id: str
    quality: int = Field(ge=0, le=5)


class ContentIn(BaseModel):
    kind: Literal["vocab", "phrase"] = "vocab"
    scenario: str
    level: str
    he: str = Field(max_length=200)
    ar: str = Field(max_length=200)
    transliteration: str = Field(default="", max_length=200)


class DecisionIn(BaseModel):
    note: str = Field(default="", max_length=300)


def create_app(service: Optional[TutorService] = None) -> FastAPI:
    svc = service or TutorService()
    svc.load_approved()
    app = FastAPI(title="Spoken Hebrew Tutor API", version="1.0.0")
    app.state.svc = svc

    @app.exception_handler(Problem)
    async def _problem(request: Request, exc: Problem):
        return problem_response(exc, instance=str(request.url.path))

    @app.exception_handler(ServiceError)
    async def _service(request: Request, exc: ServiceError):
        return problem_response(Problem(exc.title, exc.detail, status=exc.status), instance=str(request.url.path))

    # ------------------------------------------------------------ auth helpers
    def admin(token: Optional[str]) -> None:
        expected = os.environ.get("ADMIN_TOKEN", "")
        if not expected:
            raise Problem("forbidden", "admin writes are disabled: set ADMIN_TOKEN", status=403)
        if not token or not hmac.compare_digest(token, expected):
            raise Problem("unauthorized", "missing or wrong X-Admin-Token", status=401)

    def teacher(token: Optional[str]) -> dict:
        c = svc.store.class_by_teacher(token or "")
        if not c:
            raise Problem("unauthorized", "missing or wrong X-Teacher-Token", status=401)
        return c

    def student(token: Optional[str]) -> dict:
        s = svc.store.student_by_token(token or "")
        if not s:
            raise Problem("unauthorized", "missing or wrong X-Student-Token", status=401)
        return s

    # ------------------------------------------------------------ ops
    @app.get("/healthz", tags=["ops"])
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    def readyz():
        svc.store._one("SELECT 1 AS ok")
        return {"status": "ready", "content": svc.content.stats(), "tutor": svc.s.tutor, "stt": svc.s.stt,
                "tts": svc.s.tts}

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def demo():
        return HTMLResponse((WEB / "index.html").read_text(encoding="utf-8"))

    # ------------------------------------------------------------ content
    @app.get("/scenarios", tags=["content"])
    def scenarios(level: Optional[Literal["A1", "A2", "B1"]] = None):
        return [s.public(level if level in s.levels else None) for s in svc.content.scenarios.values()
                if level is None or level in s.levels]

    # ------------------------------------------------------------ classes and students
    @app.post("/admin/classes", tags=["admin"], status_code=201)
    def create_class(body: ClassIn, x_admin_token: Optional[str] = Header(None)):
        admin(x_admin_token)
        return svc.create_class(body.name)

    @app.post("/students/join", tags=["students"], status_code=201)
    def join(body: JoinIn):
        return svc.join(body.class_code, body.nickname, body.addressing)

    # ------------------------------------------------------------ sessions
    @app.post("/sessions", tags=["sessions"], status_code=201)
    def start(body: SessionIn, x_student_token: Optional[str] = Header(None)):
        return svc.start_session(student(x_student_token), body.scenario_id, body.level)

    @app.post("/sessions/{session_id}/turns", tags=["sessions"])
    def turn(session_id: str, body: TurnIn, x_student_token: Optional[str] = Header(None)):
        return svc.text_turn(student(x_student_token), session_id, body.text)

    @app.post("/sessions/{session_id}/turns/stream", tags=["sessions"])
    def turn_stream(session_id: str, body: TurnIn, x_student_token: Optional[str] = Header(None)):
        st = student(x_student_token)
        svc._load(st, session_id)  # 404 before the stream starts, not inside it

        def events():
            try:
                for ev, data in svc.stream_text_turn(st, session_id, body.text):
                    yield f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            except Exception as exc:  # the status line is already sent: report inside the stream
                yield f"event: error\ndata: {json.dumps({'error': type(exc).__name__})}\n\n"
            yield "event: done\ndata: {}\n\n"
        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/sessions/{session_id}/practice", tags=["sessions"])
    def practice(session_id: str, x_student_token: Optional[str] = Header(None)):
        return svc.practice(student(x_student_token), session_id)

    @app.post("/sessions/{session_id}/turns/audio", tags=["sessions"])
    async def turn_audio(session_id: str, file: UploadFile = File(...), say: Optional[str] = Form(None),
                         x_student_token: Optional[str] = Header(None)):
        st = student(x_student_token)
        data = await file.read()
        if len(data) > MAX_AUDIO:
            raise Problem("payload-too-large", "audio above 5 MB", status=413)
        return svc.audio_turn(st, session_id, data, filename=file.filename or "audio.webm", say=say)

    @app.post("/sessions/{session_id}/turns/image", tags=["sessions"])
    async def turn_image(session_id: str, file: UploadFile = File(...), text: str = Form(""),
                         x_student_token: Optional[str] = Header(None)):
        st = student(x_student_token)
        data = await file.read()
        if len(data) > MAX_IMAGE:
            raise Problem("payload-too-large", "image above 8 MB", status=413)
        return svc.image_turn(st, session_id, data, text)

    # ------------------------------------------------------------ learner
    @app.get("/vocab/review", tags=["learner"])
    def due(x_student_token: Optional[str] = Header(None)):
        return svc.due(student(x_student_token))

    @app.post("/vocab/review", tags=["learner"])
    def review(body: ReviewIn, x_student_token: Optional[str] = Header(None)):
        return svc.review(student(x_student_token), body.vocab_id, body.quality)

    @app.get("/progress", tags=["learner"])
    def progress(x_student_token: Optional[str] = Header(None)):
        return svc.progress(student(x_student_token))

    # ------------------------------------------------------------ teachers and admins
    @app.post("/teacher/content", tags=["teacher"], status_code=201)
    def submit(body: ContentIn, x_teacher_token: Optional[str] = Header(None)):
        c = teacher(x_teacher_token)
        return svc.submit(c["code"], body.model_dump())

    @app.get("/teacher/content", tags=["teacher"])
    def list_content(status: Optional[Literal["pending", "approved", "rejected"]] = Query(None),
                     x_teacher_token: Optional[str] = Header(None), x_admin_token: Optional[str] = Header(None)):
        if x_admin_token:
            admin(x_admin_token)
            return svc.store.submissions(status)
        c = teacher(x_teacher_token)
        return [r for r in svc.store.submissions(status) if r["class_code"] == c["code"]]

    @app.post("/teacher/content/{sub_id}/approve", tags=["admin"])
    def approve(sub_id: str, body: DecisionIn = DecisionIn(), x_admin_token: Optional[str] = Header(None)):
        admin(x_admin_token)
        return svc.decide(sub_id, True, body.note)

    @app.post("/teacher/content/{sub_id}/reject", tags=["admin"])
    def reject(sub_id: str, body: DecisionIn = DecisionIn(), x_admin_token: Optional[str] = Header(None)):
        admin(x_admin_token)
        return svc.decide(sub_id, False, body.note)

    @app.get("/teacher/dashboard", tags=["teacher"])
    def dashboard(x_teacher_token: Optional[str] = Header(None)):
        c = teacher(x_teacher_token)
        return svc.store.dashboard(c["code"])

    return app

"""Request IDs and one structured (JSON) log line per request.

Pure ASGI middleware, not Starlette's BaseHTTPMiddleware. Starlette's docs list
its limitation (changes to contextvars don't propagate upward) and recommend
pure ASGI middleware instead. BaseHTTPMiddleware also re-wraps the response body
in its own stream; a pure ASGI middleware only watches the messages go by, so
SSE and disconnect handling behave exactly as they would without it.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import time
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

logger = logging.getLogger("servekit")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": round(record.created, 3), "level": record.levelname.lower(), "msg": record.getMessage(),
               "request_id": getattr(record, "request_id", None) or request_id_var.get()}
        out.update(getattr(record, "fields", {}) or {})
        return json.dumps(out, ensure_ascii=False)


def setup_logging(level: int = logging.INFO, stream=sys.stderr) -> None:
    if any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        return
    h = logging.StreamHandler(stream)
    h.setFormatter(JsonFormatter())
    logger.addHandler(h)
    logger.setLevel(level)
    logger.propagate = False


def log(msg: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, msg, extra={"fields": fields})


class RequestContextMiddleware:
    """Assigns a request id (or accepts a safe one from X-Request-ID), returns it
    in the response header, and logs method, path, status, duration and whatever
    the handler put into request.state.log (client, outcome, ttft_ms, ...)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if SAFE_ID.match(incoming) else uuid.uuid4().hex
        state = scope.setdefault("state", {})
        state["request_id"] = rid
        state["log"] = {}
        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        status = {"code": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(b"x-request-id", rid.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status["code"] = status["code"] or 500
            raise
        finally:
            fields = {"method": scope.get("method"), "path": scope.get("path"), "status": status["code"],
                      "duration_ms": round((time.perf_counter() - t0) * 1000, 1), **state.get("log", {})}
            if scope.get("path") not in ("/healthz", "/readyz"):
                logger.info("request", extra={"request_id": rid, "fields": fields})
            request_id_var.reset(token)

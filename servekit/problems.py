"""Error contract: every error response is application/problem+json (RFC 9457).

    {"type": "https://acme.example/problems/rate-limited",
     "title": "Too many requests",
     "status": 429,
     "detail": "API key 'alice' exceeded 2 requests/second (burst 5).",
     "instance": "/v1/answer",
     "request_id": "6f1c...",
     "retry_after": 1}

`type` is a stable identifier a client can switch on; `title` is fixed per type;
`detail` is for humans and changes per occurrence. Extra members (request_id,
retry_after, errors) are allowed by the RFC and documented per type.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi.responses import JSONResponse

PROBLEM_BASE = "https://acme.example/problems/"
PROBLEM_CONTENT_TYPE = "application/problem+json"

# type slug -> (status, title). The catalog IS the contract: clients code against these.
CATALOG: dict[str, tuple[int, str]] = {
    "validation-error": (422, "Request body is not valid"),
    "unauthenticated": (401, "Missing or unknown API key"),
    "rate-limited": (429, "Too many requests"),
    "overloaded": (429, "Server is at capacity"),
    "idempotency-key-in-use": (409, "A request with this Idempotency-Key is still running"),
    "idempotency-key-mismatch": (422, "Idempotency-Key was reused with a different body"),
    "upstream-timeout": (504, "The language model did not answer in time"),
    "upstream-unavailable": (503, "The language model provider is overloaded"),
    "upstream-error": (502, "The language model provider returned an error"),
    "not-found": (404, "Not found"),
    "method-not-allowed": (405, "Method not allowed"),
    "not-ready": (503, "Service is not ready"),
    "internal-error": (500, "Internal server error"),
}


class Problem(Exception):
    """Raise anywhere in a handler; the app turns it into a problem+json response."""

    def __init__(self, slug: str, detail: str = "", *, status: Optional[int] = None,
                 retry_after: Optional[int] = None, headers: Optional[dict] = None, **extra: Any):
        default_status, title = CATALOG.get(slug, (500, slug.replace("-", " ").capitalize()))
        super().__init__(detail or title)
        self.slug = slug
        self.status = status or default_status
        self.title = title
        self.detail = detail
        self.retry_after = retry_after
        self.headers = dict(headers or {})
        self.extra = extra

    def body(self, instance: str = "", request_id: str = "") -> dict:
        out: dict[str, Any] = {"type": PROBLEM_BASE + self.slug, "title": self.title,
                               "status": self.status}
        if self.detail:
            out["detail"] = self.detail
        if instance:
            out["instance"] = instance
        if request_id:
            out["request_id"] = request_id
        if self.retry_after is not None:
            out["retry_after"] = self.retry_after
        out.update(self.extra)
        return out


def problem_response(p: Problem, instance: str = "", request_id: str = "") -> JSONResponse:
    headers = dict(p.headers)
    if p.retry_after is not None:
        headers["Retry-After"] = str(int(p.retry_after))
    return JSONResponse(p.body(instance, request_id), status_code=p.status, headers=headers,
                        media_type=PROBLEM_CONTENT_TYPE)

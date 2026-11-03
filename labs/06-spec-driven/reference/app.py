"""Reference implementation of SPEC-006 (spec/access-requests.spec.md).

This is the "known good" app the acceptance tests and the contract are checked against
offline. In exercise 6 Claude Code writes its own version in impl/ from the spec alone;
do not show it this file.

    python labs/06-spec-driven/serve.py --app reference     # run it on :8000 and try it with curl
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import Body, Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, ConfigDict, Field

try:  # imported as a package (reference.app) or as a module next to its siblings
    from .routing import route_for
    from .store import Store
except ImportError:  # pragma: no cover
    from routing import route_for  # type: ignore
    from store import Store  # type: ignore

audit = logging.getLogger("access_api.audit")

AccessLevel = Literal["read", "standard", "write", "admin"]
Route = Literal["auto_approve", "needs_manager", "needs_security"]
Status = Literal["pending", "approved"]
Role = Literal["employee", "manager", "security"]
ROLES = ("employee", "manager", "security")
ALLOWED = {"needs_manager": {"manager", "security"}, "needs_security": {"security"}}  # REQ-8


# ---------------------------------------------------------------- models (mirror spec/openapi.yaml)
class NewAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # AC-1.2: a "requester" in the body is a 422
    tool: str = Field(min_length=1, max_length=100)
    access_level: AccessLevel
    justification: str = Field(min_length=10, max_length=500)
    production: bool = False
    customer_data: bool = False
    financial_data: bool = False
    external_sharing: bool = False


class AccessRequest(BaseModel):
    id: str
    requester: str
    tool: str
    access_level: AccessLevel
    justification: str
    production: bool
    customer_data: bool
    financial_data: bool
    external_sharing: bool
    route: Route
    status: Status
    created_at: datetime
    decided_by: Optional[str]
    decided_at: Optional[datetime]


class AccessRequestList(BaseModel):
    items: list[AccessRequest]
    total: int


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: Optional[str] = Field(None, max_length=500)


class ErrorDetail(BaseModel):
    code: Literal["validation_error", "unauthenticated", "forbidden", "not_found", "conflict"]
    message: str


class ErrorBody(BaseModel):
    error: ErrorDetail


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def err(status: int):
    return {status: {"model": ErrorBody}}


# ---------------------------------------------------------------- identity (REQ-3)
class Caller(BaseModel):
    actor: str
    role: Role


def caller(x_actor: Optional[str] = Header(None, alias="X-Actor"),
           x_role: Optional[str] = Header(None, alias="X-Role")) -> Caller:
    # Found by the contract test (check: negative data accepted): the contract says 3 to 254
    # characters, the first version only checked for "@". The spec now says it too (REQ-3).
    if not x_actor or "@" not in x_actor or not 3 <= len(x_actor) <= 254:
        raise ApiError(401, "unauthenticated", "X-Actor header must be an email address of 3 to 254 characters")
    if x_role not in ROLES:
        raise ApiError(401, "unauthenticated", "X-Role header must be employee, manager or security")
    return Caller(actor=x_actor, role=x_role)


def now() -> datetime:
    return datetime.now(timezone.utc)


def log_change(request_id: str, actor: str, before: Optional[str], after: str) -> None:  # REQ-11
    audit.info(json.dumps({"request_id": request_id, "actor": actor, "from_status": before, "to_status": after}))


# ---------------------------------------------------------------- app
def create_app() -> FastAPI:
    app = FastAPI(title="Company Brain access-request API", version="1.0.0")
    store = Store()  # each app starts empty (spec section 5)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):  # REQ-2: our shape, not FastAPI's
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_error", "message": f"{where}: {first.get('msg', 'invalid input')}"}})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        # Found by the contract test (check: undocumented status code): a body that is not even
        # decodable (e.g. invalid UTF-8) makes FastAPI answer 400 "There was an error parsing the
        # body". The contract has no 400, and REQ-2 says invalid input is 422.
        if exc.status_code == 400:
            return JSONResponse(status_code=422, content={"error": {
                "code": "validation_error", "message": f"body: {exc.detail}"}})
        headers = dict(exc.headers or {})
        # Found by the contract test (check ST205, Allow header mismatch): when GET and POST of
        # one path are separate routes, Starlette's 405 lists only one route's methods in Allow.
        if exc.status_code == 405:
            methods = {m for r in app.routes if isinstance(r, APIRoute) and r.path_regex.match(request.url.path)
                       for m in r.methods}
            headers["Allow"] = ", ".join(sorted(methods))
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)

    common = {**err(401), **err(422)}

    @app.post("/access-requests", status_code=201, response_model=AccessRequest, responses=common)
    def create(body: NewAccessRequest, who: Caller = Depends(caller)):
        flags = {k: getattr(body, k) for k in ("production", "customer_data", "financial_data", "external_sharing")}
        route = route_for(body.tool, body.access_level, flags)
        created = now()
        auto = route == "auto_approve"
        item = {**body.model_dump(), "id": store.new_id(), "requester": who.actor, "route": route,
                "status": "approved" if auto else "pending", "created_at": created,
                "decided_by": "system" if auto else None, "decided_at": created if auto else None}
        store.add(item)
        log_change(item["id"], "system" if auto else who.actor, None, item["status"])
        return item

    @app.get("/access-requests", response_model=AccessRequestList, responses=common)
    def list_requests(status: Optional[Status] = None, limit: int = Query(20, ge=1, le=100),
                      who: Caller = Depends(caller)):
        items, total = store.list(status, limit)
        return {"items": items, "total": total}

    @app.get("/access-requests/{request_id}", response_model=AccessRequest, responses={**common, **err(404)})
    def get_one(request_id: str, who: Caller = Depends(caller)):
        item = store.get(request_id)
        if item is None:
            raise ApiError(404, "not_found", f"no access request {request_id}")
        return item

    @app.post("/access-requests/{request_id}/approve", response_model=AccessRequest,
              responses={**common, **err(403), **err(404), **err(409)})
    def approve(request_id: str, decision: Optional[Decision] = Body(None), who: Caller = Depends(caller)):
        item = store.get(request_id)
        if item is None:  # REQ-7
            raise ApiError(404, "not_found", f"no access request {request_id}")
        if item["status"] != "pending":  # REQ-10, checked before authority
            raise ApiError(409, "conflict", f"request is already {item['status']}")
        if who.role not in ALLOWED[item["route"]]:  # REQ-9
            raise ApiError(403, "forbidden", f"role {who.role} cannot approve {item['route']} requests")
        if who.actor.lower() == item["requester"].lower():  # REQ-9, separation of duties
            raise ApiError(403, "forbidden", "you cannot approve your own request")
        updated = store.update(request_id, status="approved", decided_by=who.actor, decided_at=now())
        log_change(request_id, who.actor, "pending", "approved")
        return updated

    return app

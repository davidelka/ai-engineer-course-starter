"""Acme access-request service.

Run locally:  make run   (uvicorn app.main:app --reload)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.models import AccessRequest, AccessRequestIn, Route, Status
from app.policy import route as choose_route
from app.store import RequestStore

app = FastAPI(title="Acme Access Requests", version="0.3.0")
store = RequestStore()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/requests", response_model=AccessRequest, status_code=201)
def create_request(body: AccessRequestIn) -> AccessRequest:
    return store.add(body, choose_route(body))


@app.get("/requests/{request_id}", response_model=AccessRequest)
def get_request(request_id: str) -> AccessRequest:
    item = store.get(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"request {request_id} not found")
    return item


@app.get("/requests", response_model=list[AccessRequest])
def list_requests(status: Status | None = None, route: Route | None = None) -> list[AccessRequest]:
    return store.list(status=status, route=route)

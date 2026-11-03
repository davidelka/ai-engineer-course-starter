"""REQ-1, REQ-2, REQ-3, REQ-5, REQ-11: creating requests."""

import json
import logging
import re

import pytest
from acc_helpers import EMPLOYEE, H, body, create


@pytest.mark.req("REQ-1")
def test_create_returns_201_with_id_and_requester(client):
    r = client.post("/access-requests", json=body(), headers=EMPLOYEE, expect_valid_request=True)
    assert r.status_code == 201
    data = r.json()
    assert re.fullmatch(r"ar_[0-9a-z]+", data["id"])
    assert data["requester"] == "dana@acme.example"


@pytest.mark.req("REQ-1", "REQ-2")
def test_requester_cannot_come_from_the_body(client):
    r = client.post("/access-requests", json=body(requester="ceo@acme.example"), headers=EMPLOYEE)
    assert r.status_code == 422


@pytest.mark.req("REQ-1", "REQ-7")
def test_stored_request_equals_the_201_body(client):
    created = create(client)
    r = client.get(f"/access-requests/{created['id']}", headers=EMPLOYEE)
    assert r.status_code == 200
    assert r.json() == created


@pytest.mark.req("REQ-2")
@pytest.mark.parametrize("bad", [
    {"tool": "Jira", "access_level": "read"},                                     # no justification
    {"tool": "Jira", "access_level": "superuser", "justification": "x" * 20},     # not in the enum
    {"tool": "Jira", "access_level": "read", "justification": "too short"},       # 9 characters
])
def test_invalid_body_is_422_and_nothing_is_stored(client, bad):
    before = client.get("/access-requests", headers=EMPLOYEE).json()["total"]
    r = client.post("/access-requests", json=bad, headers=EMPLOYEE)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert client.get("/access-requests", headers=EMPLOYEE).json()["total"] == before


@pytest.mark.req("REQ-3")
def test_missing_actor_is_401(client):
    r = client.post("/access-requests", json=body(), headers={"X-Role": "employee"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.req("REQ-3")
@pytest.mark.parametrize("headers", [H(role="admin"), {"X-Actor": "dana@acme.example"}, H(actor="dana")])
def test_bad_identity_is_401_on_list(client, headers):
    r = client.get("/access-requests", headers=headers)
    assert r.status_code == 401


@pytest.mark.req("REQ-5")
def test_auto_approve_is_approved_by_system_at_creation(client):
    data = create(client)
    assert data["route"] == "auto_approve"
    assert data["status"] == "approved"
    assert data["decided_by"] == "system"
    assert data["decided_at"] == data["created_at"]


@pytest.mark.req("REQ-5")
def test_other_routes_start_pending(client):
    data = create(client, tool="Notion", access_level="standard")
    assert data["route"] == "needs_manager"
    assert data["status"] == "pending"
    assert data["decided_by"] is None and data["decided_at"] is None


def audit_records(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "access_api.audit"]


@pytest.mark.req("REQ-11")
def test_creation_writes_one_audit_record(client, caplog):
    caplog.set_level(logging.INFO, logger="access_api.audit")
    data = create(client)
    recs = audit_records(caplog)
    assert recs == [{"request_id": data["id"], "actor": "system", "from_status": None, "to_status": "approved"}]

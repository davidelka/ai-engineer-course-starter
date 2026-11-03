"""Hidden acceptance tests for task "feature": POST /requests/{id}/decision.

The task prompt (tasks.py) states every rule checked here, so a correct implementation
of the prompt passes without guessing.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app, store


@pytest.fixture
def client():
    store.clear()
    return TestClient(app)


def create(client, **kw):
    b = {"requester_email": "dana@acme.example", "tool": "Notion", "access_level": "standard", "reason": "acceptance test"}
    b.update(kw)
    r = client.post("/requests", json=b)
    assert r.status_code == 201
    return r.json()


def decide(client, rid, decision="approve", approver="manager@acme.example", comment=None):
    payload = {"decision": decision, "approver_email": approver}
    if comment is not None:
        payload["comment"] = comment
    return client.post(f"/requests/{rid}/decision", json=payload)


def test_approve_pending_manager_request(client):
    rid = create(client)["id"]
    r = decide(client, rid, comment="ok for Q3")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"
    assert data["decided_by"] == "manager@acme.example"
    assert data["decided_at"]
    assert client.get(f"/requests/{rid}").json()["status"] == "approved"


def test_deny(client):
    rid = create(client)["id"]
    r = decide(client, rid, decision="deny")
    assert r.status_code == 200
    assert r.json()["status"] == "denied"


def test_unknown_request_404(client):
    assert decide(client, "req-9999").status_code == 404


def test_second_decision_409(client):
    rid = create(client)["id"]
    assert decide(client, rid).status_code == 200
    assert decide(client, rid, decision="deny").status_code == 409


def test_auto_approved_request_409(client):
    rid = create(client, tool="Jira", access_level="read")["id"]
    assert decide(client, rid).status_code == 409


def test_security_track_403(client):
    rid = create(client, tool="AWS", access_level="read")["id"]
    assert decide(client, rid).status_code == 403


def test_self_approval_403(client):
    rid = create(client)["id"]
    assert decide(client, rid, approver="dana@acme.example").status_code == 403


def test_bad_decision_value_422(client):
    rid = create(client)["id"]
    assert decide(client, rid, decision="maybe").status_code == 422


def test_existing_endpoints_still_work(client):
    create(client)
    assert client.get("/health").json() == {"status": "ok"}
    assert len(client.get("/requests", params={"status": "pending"}).json()) == 1

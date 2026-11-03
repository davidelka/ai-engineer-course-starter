"""REQ-8, REQ-9, REQ-11: approvals.

Exercise 3: the traceability matrix shows that one requirement about approvals has no test.
Find it, write the test here with the right marker, and run the matrix again.
"""

import json
import logging

import pytest
from acc_helpers import EMPLOYEE, MANAGER, SECURITY, H, create


def manager_track(client):
    return create(client, tool="Notion", access_level="standard")  # needs_manager


def security_track(client, headers=None):
    return create(client, headers=headers, tool="Slack", access_level="admin")  # needs_security


class TestAuthority:
    @pytest.mark.req("REQ-8")
    def test_manager_approves_manager_track(self, client):
        req = manager_track(client)
        r = client.post(f"/access-requests/{req['id']}/approve", headers=MANAGER, json={"note": "ok"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "approved"
        assert data["decided_by"] == "mike@acme.example"
        assert data["decided_at"] is not None

    @pytest.mark.req("REQ-8")
    def test_security_approves_security_track(self, client):
        req = security_track(client)
        r = client.post(f"/access-requests/{req['id']}/approve", headers=SECURITY)
        assert r.status_code == 200

    @pytest.mark.req("REQ-8")
    def test_security_may_approve_manager_track(self, client):
        req = manager_track(client)
        r = client.post(f"/access-requests/{req['id']}/approve", headers=SECURITY)
        assert r.status_code == 200


@pytest.mark.req("REQ-9")
class TestForbidden:
    def test_manager_cannot_approve_security_track(self, client):
        req = security_track(client)
        r = client.post(f"/access-requests/{req['id']}/approve", headers=MANAGER)
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "forbidden"
        after = client.get(f"/access-requests/{req['id']}", headers=EMPLOYEE).json()
        assert after["status"] == "pending"

    def test_employee_cannot_approve(self, client):
        req = manager_track(client)
        r = client.post(f"/access-requests/{req['id']}/approve", headers=EMPLOYEE)
        assert r.status_code == 403

    def test_nobody_approves_their_own_request(self, client):
        req = security_track(client, headers=SECURITY)
        r = client.post(f"/access-requests/{req['id']}/approve", headers=SECURITY)
        assert r.status_code == 403


@pytest.mark.req("REQ-11")
def test_approval_writes_one_audit_record(client, caplog):
    req = manager_track(client)
    caplog.set_level(logging.INFO, logger="access_api.audit")
    caplog.clear()
    client.post(f"/access-requests/{req['id']}/approve", headers=H("mike@acme.example", "manager"))
    recs = [json.loads(r.getMessage()) for r in caplog.records if r.name == "access_api.audit"]
    assert recs == [{"request_id": req["id"], "actor": "mike@acme.example",
                     "from_status": "pending", "to_status": "approved"}]

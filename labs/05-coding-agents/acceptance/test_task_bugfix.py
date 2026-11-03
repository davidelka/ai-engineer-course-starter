"""Hidden acceptance tests for task "bugfix" (ACME-142). The agent never sees this file.

score_run.py runs it with the workspace as the working directory and on sys.path.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app, store


@pytest.fixture
def client():
    store.clear()
    return TestClient(app)


def body(**kw):
    b = {"requester_email": "dana@acme.example", "tool": "Jira", "access_level": "read", "reason": "acceptance test"}
    b.update(kw)
    return b


@pytest.mark.parametrize(
    "fields,expected",
    [
        # the reported bug and its siblings: sensitive flags on an approved tool
        ({"tool": "Slack", "access_level": "read", "customer_data": True}, "needs_security"),
        ({"tool": "Jira", "access_level": "standard", "financial_data": True}, "needs_security"),
        ({"tool": "Confluence", "access_level": "read", "production": True}, "needs_security"),
        ({"tool": "Google Workspace", "access_level": "standard", "external_sharing": True}, "needs_security"),
        # behaviour that must not change
        ({"tool": "Slack", "access_level": "read"}, "auto_approve"),
        ({"tool": "Figma", "access_level": "standard"}, "auto_approve"),
        ({"tool": "GitHub", "access_level": "write"}, "needs_manager"),
        ({"tool": "Notion", "access_level": "standard"}, "needs_manager"),
        ({"tool": "Figma", "access_level": "admin"}, "needs_security"),
        ({"tool": "NetSuite", "access_level": "read"}, "needs_security"),
        ({"tool": "kubernetes", "access_level": "read"}, "needs_security"),
    ],
)
def test_route_via_api(client, fields, expected):
    r = client.post("/requests", json=body(**fields))
    assert r.status_code == 201
    assert r.json()["route"] == expected


def test_sensitive_request_is_pending_not_approved(client):
    r = client.post("/requests", json=body(tool="Slack", customer_data=True))
    assert r.json()["status"] == "pending"

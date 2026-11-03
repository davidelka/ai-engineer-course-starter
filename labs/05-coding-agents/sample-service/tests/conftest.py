import pytest
from fastapi.testclient import TestClient

from app.main import app, store


@pytest.fixture
def client():
    store.clear()
    return TestClient(app)


def make_request(**overrides) -> dict:
    """A valid request body; override any field."""
    body = {
        "requester_email": "dana@acme.example",
        "tool": "Jira",
        "access_level": "read",
        "reason": "Need to follow the Q3 roadmap tickets",
    }
    body.update(overrides)
    return body

"""Shared helpers for the acceptance tests (identity headers, a valid body, create)."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
CONTRACT = LAB / "spec" / "openapi.yaml"
APPS = {"reference": "reference.app:create_app", "impl": "impl.app:create_app"}


def load_factory():
    target = APPS.get(os.environ.get("ACCESS_APP", "reference"), os.environ.get("ACCESS_APP"))
    module, _, attr = target.partition(":")
    try:
        return getattr(importlib.import_module(module), attr or "create_app")
    except (ImportError, AttributeError) as exc:
        pytest.exit(f"cannot load the app {target!r}: {exc}", returncode=4)


def H(actor: str = "dana@acme.example", role: str = "employee") -> dict:
    """Identity headers set by the gateway (REQ-3)."""
    return {"X-Actor": actor, "X-Role": role}


EMPLOYEE = H()
MANAGER = H("mike@acme.example", "manager")
MANAGER2 = H("maya@acme.example", "manager")
SECURITY = H("sec@acme.example", "security")


def body(**overrides) -> dict:
    b = {"tool": "Jira", "access_level": "read", "justification": "Need to read the Platform sprint board."}
    b.update(overrides)
    return b


def create(client, headers=None, **overrides) -> dict:
    r = client.post("/access-requests", json=body(**overrides), headers=headers or EMPLOYEE,
                    expect_valid_request=True)
    assert r.status_code == 201, r.text
    return r.json()

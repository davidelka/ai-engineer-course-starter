"""Acceptance tests for SPEC-006. They run against whichever app ACCESS_APP names:

    ACCESS_APP=reference   reference/app.py (default; known good)
    ACCESS_APP=impl        impl/app.py      (what Claude Code wrote in exercise 6)
    ACCESS_APP=pkg.mod:fn  any importable factory that returns a FastAPI app

Every request made through the `client` fixture is validated against spec/openapi.yaml by
openapi-core, so an example test that gets a response the contract does not allow fails
with ContractViolation even when the assertion in the test itself would pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]

from acc_helpers import CONTRACT, load_factory  # noqa: E402
from spectools.contract import ContractClient  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "req(*ids): the spec requirements this test checks (traceability)")


@pytest.fixture(scope="session")
def factory():
    return load_factory()


@pytest.fixture
def app(factory):
    return factory()  # a fresh app, so a fresh empty store, for every test


@pytest.fixture
def client(app):
    return ContractClient(app, CONTRACT)

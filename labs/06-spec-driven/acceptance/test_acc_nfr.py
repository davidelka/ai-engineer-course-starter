"""NFR-1 latency and NFR-2 contract conformance."""

import os
import statistics
import time

import pytest
from acc_helpers import CONTRACT, EMPLOYEE, body, load_factory
from hypothesis import HealthCheck, settings

from spectools.contract import contract_schema


def p95(xs):
    return statistics.quantiles(xs, n=20)[-1]


@pytest.mark.req("NFR-1")
def test_p95_latency_with_1000_stored(client):
    http = client.http  # plain TestClient: we time the app, not the contract validator
    for i in range(1000):
        http.post("/access-requests", json=body(justification=f"Bulk request number {i:04d}"), headers=EMPLOYEE)
    creates, lists = [], []
    for i in range(200):
        t = time.perf_counter()
        http.post("/access-requests", json=body(), headers=EMPLOYEE)
        creates.append(time.perf_counter() - t)
        t = time.perf_counter()
        http.get("/access-requests", headers=EMPLOYEE)
        lists.append(time.perf_counter() - t)
    print(f"\np95 create {p95(creates) * 1000:.1f} ms, p95 list {p95(lists) * 1000:.1f} ms")
    assert p95(creates) <= 0.050
    assert p95(lists) <= 0.050


# NFR-2: Schemathesis generates requests from the contract FILE and sends them to the app
# in-process. Fixed seed (derandomize) so CI is stable; CONTRACT_RANDOM=1 explores new inputs.
EXAMPLES = int(os.environ.get("CONTRACT_EXAMPLES", "100"))
RANDOM = os.environ.get("CONTRACT_RANDOM") == "1"


def _schema():
    return contract_schema(CONTRACT, load_factory()())


schema = _schema()


@pytest.mark.req("NFR-2")
@schema.parametrize()
@settings(max_examples=EXAMPLES, deadline=None, derandomize=not RANDOM,
          suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
def test_contract(case):
    case.call_and_validate()

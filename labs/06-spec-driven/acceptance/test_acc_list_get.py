"""REQ-6 and REQ-7: listing and getting requests."""

import pytest
from acc_helpers import EMPLOYEE, SECURITY, create


@pytest.mark.req("REQ-6")
def test_newest_first(client):
    a, b, c = (create(client, justification=f"Request number {i} for the board") for i in range(3))
    ids = [x["id"] for x in client.get("/access-requests", headers=EMPLOYEE).json()["items"]]
    assert ids == [c["id"], b["id"], a["id"]]


@pytest.mark.req("REQ-6")
def test_default_limit_is_20_and_total_counts_all(client):
    for _ in range(25):
        create(client)
    data = client.get("/access-requests", headers=EMPLOYEE).json()
    assert len(data["items"]) == 20
    assert data["total"] == 25


@pytest.mark.req("REQ-6")
def test_status_filter(client):
    create(client)  # approved (auto)
    p1 = create(client, tool="Notion", access_level="standard")
    p2 = create(client, tool="Slack", access_level="admin")
    data = client.get("/access-requests?status=pending", headers=EMPLOYEE).json()
    assert {x["id"] for x in data["items"]} == {p1["id"], p2["id"]}
    assert data["total"] == 2


@pytest.mark.req("REQ-6", "REQ-2")
@pytest.mark.parametrize("limit", [0, 101])
def test_limit_out_of_range_is_422(client, limit):
    r = client.get(f"/access-requests?limit={limit}", headers=EMPLOYEE)
    assert r.status_code == 422


@pytest.mark.req("REQ-7")
def test_unknown_id_is_404(client):
    r = client.get("/access-requests/ar_doesnotexist", headers=EMPLOYEE)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


@pytest.mark.req("REQ-7")
def test_approving_unknown_id_is_404(client):
    r = client.post("/access-requests/ar_doesnotexist/approve", headers=SECURITY)
    assert r.status_code == 404

from tests.conftest import make_request


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_auto_approved(client):
    r = client.post("/requests", json=make_request())
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "req-0001"
    assert body["route"] == "auto_approve"
    assert body["status"] == "approved"


def test_create_needs_manager_is_pending(client):
    body = client.post("/requests", json=make_request(tool="Notion", access_level="standard")).json()
    assert body["route"] == "needs_manager"
    assert body["status"] == "pending"


def test_get_and_404(client):
    rid = client.post("/requests", json=make_request()).json()["id"]
    assert client.get(f"/requests/{rid}").json()["id"] == rid
    assert client.get("/requests/req-9999").status_code == 404


def test_list_filters(client):
    client.post("/requests", json=make_request())
    client.post("/requests", json=make_request(tool="AWS"))
    assert len(client.get("/requests").json()) == 2
    assert [r["tool"] for r in client.get("/requests", params={"route": "needs_security"}).json()] == ["AWS"]
    assert len(client.get("/requests", params={"status": "pending"}).json()) == 1


def test_validation(client):
    assert client.post("/requests", json=make_request(requester_email="not-an-email")).status_code == 422
    assert client.post("/requests", json=make_request(access_level="owner")).status_code == 422
    assert client.post("/requests", json=make_request(duration_days=400)).status_code == 422
    assert client.post("/requests", json=make_request(unknown_field=1)).status_code == 422

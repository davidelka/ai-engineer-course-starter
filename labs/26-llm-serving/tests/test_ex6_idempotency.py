"""Exercise 6: Idempotency-Key for POST /v1/answer."""

import hashlib
import json

from fastapi.testclient import TestClient

from mine import IdempotencyStore, fingerprint


def test_fingerprint_is_canonical_sha256():
    body = {"question": "שלום", "max_tokens": 100}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert fingerprint(body) == hashlib.sha256(canon.encode("utf-8")).hexdigest()
    assert fingerprint({"b": 1, "a": 2}) == fingerprint({"a": 2, "b": 1})
    assert fingerprint({"a": 1}) != fingerprint({"a": "1"})


def test_new_then_in_progress_then_replay():
    st = IdempotencyStore(ttl=60, clock=lambda: 0.0)
    fp = fingerprint({"q": 1})
    assert st.begin("alice", "k1", fp).outcome == "new"
    assert st.begin("alice", "k1", fp).outcome == "in_progress"
    st.complete("alice", "k1", 200, {"answer": "14 days"}, {"X-Test": "1"})
    b = st.begin("alice", "k1", fp)
    assert (b.outcome, b.status, b.response, b.headers) == ("replay", 200, {"answer": "14 days"}, {"X-Test": "1"})
    assert len(st) == 1


def test_mismatch_and_scope():
    st = IdempotencyStore(ttl=60, clock=lambda: 0.0)
    st.begin("alice", "k1", fingerprint({"q": 1}))
    assert st.begin("alice", "k1", fingerprint({"q": 2})).outcome == "mismatch"
    assert st.begin("bob", "k1", fingerprint({"q": 2})).outcome == "new"  # bob's k1 is another key


def test_expiry_and_abandon():
    t = [0.0]
    st = IdempotencyStore(ttl=10, clock=lambda: t[0])
    fp = fingerprint({"q": 1})
    st.begin("alice", "k1", fp)
    st.complete("alice", "k1", 200, {"a": 1})
    t[0] = 9.99
    assert st.begin("alice", "k1", fp).outcome == "replay"
    t[0] = 10.0
    assert st.begin("alice", "k1", fp).outcome == "new"  # expired: as if never seen
    st.abandon("alice", "k1")
    assert st.begin("alice", "k1", fp).outcome == "new"
    st.complete("nobody", "zzz", 200, {})  # unknown key: no error, nothing stored
    assert st.begin("nobody", "zzz", fp).outcome == "new"


def test_the_service_replays_with_your_store(mock):
    import servekit.app as appmod
    from servekit.app import Settings, create_app

    server, url = mock
    original = appmod.fingerprint
    appmod.fingerprint = fingerprint
    try:
        app = create_app(Settings(base_url=url), idempotency=IdempotencyStore())
        with TestClient(app) as c:
            h = {"Authorization": "Bearer dev-key-alice", "Idempotency-Key": "order-42"}
            r1 = c.post("/v1/answer", json={"question": "vacation"}, headers=h)
            r2 = c.post("/v1/answer", json={"question": "vacation"}, headers=h)
            assert r1.status_code == r2.status_code == 200
            assert r2.json() == r1.json() and r2.headers.get("idempotent-replayed") == "true"
            assert server.state.requests == 1, "the replay must not call the LLM again"
            r3 = c.post("/v1/answer", json={"question": "something else"}, headers=h)
            assert r3.status_code == 422
    finally:
        appmod.fingerprint = original

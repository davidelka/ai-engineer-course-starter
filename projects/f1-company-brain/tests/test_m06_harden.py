"""Milestone 6: harden_route, suspicious request text never auto-approves (mine.harden_route)."""
import copy

from _impl import mine

POL = {"route": "auto_approve", "reasons": ["approved tool", "basic seat"], "system": "zoom", "known_system": True}


def test_clean_text_unchanged_copy():
    out = mine.harden_route(POL, [])
    assert out["route"] == "auto_approve" and out["hardened"] is False
    assert out["reasons"] == POL["reasons"] and out["system"] == "zoom"
    assert out is not POL


def test_flagged_auto_approve_goes_to_manager():
    out = mine.harden_route(POL, ["ignore_instructions", "addresses_ai"])
    assert out["route"] == "needs_manager" and out["hardened"] is True
    assert out["reasons"][:2] == POL["reasons"]
    assert out["reasons"][-1] == "suspicious request text (ignore_instructions, addresses_ai): never auto-approved"
    assert out["known_system"] is True


def test_stricter_routes_keep_route_but_explain():
    for route in ("needs_manager", "needs_security"):
        out = mine.harden_route({**POL, "route": route}, ["fake_authority"])
        assert out["route"] == route and out["hardened"] is True
        assert "fake_authority" in out["reasons"][-1]


def test_unknown_route_fails_closed():
    for pol in ({**POL, "route": "yolo"}, {"reasons": []}):
        out = mine.harden_route(pol, [])
        assert out["route"] == "needs_security" and out["hardened"] is True
        assert "failing closed" in out["reasons"][-1]


def test_never_mutates():
    before = copy.deepcopy(POL)
    mine.harden_route(POL, ["x"])
    assert POL == before

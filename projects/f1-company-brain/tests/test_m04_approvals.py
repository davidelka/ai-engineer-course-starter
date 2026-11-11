"""Milestone 4: approvals_for, the approvals inbox (mine.approvals_for)."""
import copy

from cbrain.auth import Principal

from _impl import mine


def P(eid, security=False):
    roles = {"employee", "security"} if security else {"employee", "manager"}
    return Principal(id=str(eid), email=f"{eid}@acme.example", name=str(eid), employee_id=eid,
                     roles=frozenset(roles), acl_role="employee")


ITEMS = [
    {"thread_id": "t1", "gate": "manager", "employee_id": "E016", "requester_id": "E016", "manager_id": "E005",
     "created_at": "2026-11-02T09:00:00+00:00"},
    {"thread_id": "t2", "gate": "security", "employee_id": "E015", "requester_id": "E015", "manager_id": "E009",
     "created_at": "2026-11-01T09:00:00+00:00"},
    {"thread_id": "t3", "gate": "manager", "employee_id": "E017", "requester_id": "E017", "manager_id": "E016",
     "created_at": "2026-11-02T08:00:00+00:00"},
    {"thread_id": "t4", "gate": "manager", "employee_id": "E030", "requester_id": "E017", "manager_id": "E005",
     "created_at": "2026-10-30T08:00:00+00:00"},
    {"thread_id": "t5", "gate": "security", "employee_id": "E062", "requester_id": "E062", "manager_id": "E002",
     "created_at": "2026-10-29T08:00:00+00:00"},
]


def ids(xs):
    return [x["thread_id"] for x in xs]


def test_manager_sees_only_direct_reports_manager_gate():
    assert ids(mine.approvals_for(P("E005"), ITEMS)) == ["t4", "t1"]      # oldest first
    assert ids(mine.approvals_for(P("E016"), ITEMS)) == ["t3"]            # Dana: Avital's request, not her own
    assert ids(mine.approvals_for(P("E009"), ITEMS)) == []                # Tomer's is a SECURITY gate


def test_security_sees_both_gates_but_never_their_own():
    assert ids(mine.approvals_for(P("E062", security=True), ITEMS)) == ["t4", "t2", "t3", "t1"]
    assert ids(mine.approvals_for(P("E063", security=True), ITEMS)) == ["t5", "t4", "t2", "t3", "t1"]


def test_requester_is_excluded_too():
    # Avital (E017) filed t4 for Sapir; even as a security member she may not decide it
    assert "t4" not in ids(mine.approvals_for(P("E017", security=True), ITEMS))


def test_no_employee_id_no_authority():
    ops = Principal(id="ops", email="ops@acme.example", name="ops", employee_id=None,
                    roles=frozenset({"admin"}), acl_role="employee")
    assert mine.approvals_for(ops, ITEMS) == []


def test_does_not_mutate_input():
    before = copy.deepcopy(ITEMS)
    mine.approvals_for(P("E062", security=True), ITEMS)
    assert ITEMS == before

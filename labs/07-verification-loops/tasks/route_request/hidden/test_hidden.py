import pytest
from hypothesis import given
from hypothesis import strategies as st

from solution import route_request

FLAGS = ["customer_data", "financial_data", "production", "external_sharing"]
RANK = {"auto_approve": 0, "needs_manager": 1, "needs_security": 2}
tools = st.sampled_from(["Jira", "jira", " SLACK ", "Notion", "AWS Console", "Figma", "  Zoom ", "NetSuite",
                         "google workspace", "Miro"])
levels = st.sampled_from(["read", "standard", "write", "paid_seat", "admin", "READ", " Admin ", "Paid_Seat"])
flags = st.fixed_dictionaries({k: st.booleans() for k in FLAGS})


@given(tools, levels, flags, st.sampled_from(FLAGS))
def test_a_risk_flag_always_means_security(tool, level, fl, extra):
    before = route_request(tool, level, **fl)
    after = route_request(tool, level, **{**fl, extra: True})
    assert after == "needs_security" and RANK[after] >= RANK[before], (
        f"route_request({tool!r}, {level!r}, {fl}) = {before}, and with {extra}=True it is {after}")


@given(tools, flags)
def test_admin_always_security(tool, fl):
    got = route_request(tool, "admin", **fl)
    assert got == "needs_security", f"route_request({tool!r}, 'admin', {fl}) = {got}"


@given(tools, levels, flags)
def test_case_and_spaces_do_not_matter(tool, level, fl):
    a = route_request(tool, level, **fl)
    b = route_request(f" {tool.upper()} ", level.lower().strip(), **fl)
    assert a == b, f"{tool!r}/{level!r} gives {a} but {tool.upper()!r}/{level.lower().strip()!r} gives {b}"


@given(st.text(max_size=12).filter(lambda s: s.strip().lower() not in
                                   {"read", "standard", "write", "paid_seat", "admin"}))
def test_unknown_access_raises(level):
    with pytest.raises(ValueError):
        route_request("Jira", level)


@pytest.mark.parametrize("tool", ["Jira", "Confluence", "Slack", "Google Workspace", "Zoom", "Miro", "Figma", "GitHub"])
@pytest.mark.parametrize("level", ["read", "standard"])
def test_approved_read_or_standard_is_auto(tool, level):
    got = route_request(tool, level)
    assert got == "auto_approve", f"route_request({tool!r}, {level!r}) = {got}"

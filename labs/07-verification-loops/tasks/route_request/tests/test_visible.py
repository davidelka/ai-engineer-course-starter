import pytest

from solution import route_request


def test_jira_read_is_auto():
    assert route_request("Jira", "read") == "auto_approve"


def test_case_and_spaces_in_tool():
    assert route_request("  SLACK ", "standard") == "auto_approve"


def test_unknown_tool_needs_manager():
    assert route_request("Notion", "read") == "needs_manager"


def test_write_needs_manager():
    assert route_request("GitHub", "write") == "needs_manager"


def test_paid_seat_needs_manager():
    assert route_request("Figma", "paid_seat") == "needs_manager"


def test_admin_needs_security():
    assert route_request("Jira", "admin") == "needs_security"


def test_financial_data_needs_security():
    assert route_request("Confluence", "read", financial_data=True) == "needs_security"


def test_production_needs_security():
    assert route_request("Notion", "write", production=True) == "needs_security"


def test_external_sharing_needs_security():
    assert route_request("Google Workspace", "read", external_sharing=True) == "needs_security"


def test_unknown_access_rejected():
    with pytest.raises(ValueError):
        route_request("Jira", "owner")

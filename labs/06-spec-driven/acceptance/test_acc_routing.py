"""REQ-4: routing by Acme SaaS access policy v2.1. One case per acceptance criterion."""

import pytest
from acc_helpers import create


@pytest.mark.req("REQ-4")
@pytest.mark.parametrize("ac,overrides,route", [
    ("AC-4.1", {"tool": "Jira", "access_level": "read"}, "auto_approve"),
    ("AC-4.2", {"tool": "Slack", "access_level": "admin"}, "needs_security"),
    ("AC-4.3", {"tool": "Confluence", "access_level": "read", "customer_data": True}, "needs_security"),
    ("AC-4.4", {"tool": "Notion", "access_level": "standard"}, "needs_manager"),
    ("AC-4.5", {"tool": "GitHub", "access_level": "write"}, "needs_manager"),
    ("AC-4.6", {"tool": "Figma", "access_level": "standard"}, "needs_manager"),
    ("AC-4.7", {"tool": "  aws ", "access_level": "read"}, "needs_security"),
    ("strictest wins", {"tool": "Notion", "access_level": "write", "financial_data": True}, "needs_security"),
    ("case-insensitive", {"tool": "google WORKSPACE", "access_level": "standard"}, "auto_approve"),
])
def test_route(client, ac, overrides, route):
    assert create(client, **overrides)["route"] == route, ac

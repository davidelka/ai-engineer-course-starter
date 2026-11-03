import pytest

from app.models import AccessRequestIn
from app.policy import route
from tests.conftest import make_request


def req(**kw) -> AccessRequestIn:
    return AccessRequestIn(**make_request(**kw))


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({"tool": "Jira", "access_level": "read"}, "auto_approve"),
        ({"tool": "Google  Workspace", "access_level": "standard"}, "auto_approve"),
        ({"tool": "GitHub", "access_level": "write"}, "needs_manager"),
        ({"tool": "Notion", "access_level": "standard"}, "needs_manager"),
        ({"tool": "AWS", "access_level": "read"}, "needs_security"),
        ({"tool": "NetSuite", "access_level": "read"}, "needs_security"),
        ({"tool": "Figma", "access_level": "admin"}, "needs_security"),
        ({"tool": "Notion", "access_level": "write", "external_sharing": True}, "needs_security"),
    ],
)
def test_route(fields, expected):
    assert route(req(**fields)) == expected

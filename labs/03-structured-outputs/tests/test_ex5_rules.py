"""Exercise 5: rules the schema cannot express."""

import pytest
from pydantic import ValidationError

from mine import MyAccessRequest

BASE = dict(requester_name="Dana", requester_email="dana@acme.example", tool="Jira", resource=None,
            access_level="read", production=False, customer_data=False, financial_data=False,
            external_sharing=False, duration_days=None, justification=None, reason="r", route="auto_approve")


def make(**kw):
    return MyAccessRequest.model_validate({**BASE, **kw})


def test_valid_request_passes():
    assert make().route == "auto_approve"


def test_email_is_normalized():
    assert make(requester_email="  YAEL.BAR@ACME.EXAMPLE ").requester_email == "yael.bar@acme.example"


def test_email_may_be_null():
    assert make(requester_email=None).requester_email is None


@pytest.mark.parametrize("trigger", [
    dict(access_level="admin"), dict(production=True), dict(customer_data=True),
    dict(financial_data=True), dict(external_sharing=True),
])
@pytest.mark.parametrize("route", ["auto_approve", "needs_manager"])
def test_security_triggers_force_needs_security(trigger, route):
    kw = {**trigger, "route": route}  # rule 2 is checked before rule 3, so its message wins
    with pytest.raises(ValidationError) as e:
        make(**kw)
    assert "needs_security" in str(e.value)


@pytest.mark.parametrize("trigger", [
    dict(access_level="admin"), dict(production=True), dict(customer_data=True),
    dict(financial_data=True), dict(external_sharing=True),
])
def test_security_triggers_accept_needs_security(trigger):
    assert make(**trigger, route="needs_security").route == "needs_security"


def test_auto_approve_needs_low_access():
    with pytest.raises(ValidationError):
        make(access_level="write", route="auto_approve")
    assert make(access_level="write", route="needs_manager").route == "needs_manager"
    assert make(access_level="standard", route="auto_approve").route == "auto_approve"

"""Exercise 8: PII redaction for logs."""

import pytest

import mine


@pytest.mark.parametrize("value,ok", [
    ("123456782", True), ("123456789", False), ("000000018", True), ("18", True),
    ("12345678-2", True), ("039337423", True), ("039337424", False),
    ("000000000", False), ("", False), ("12a456782", False), ("1234567890", False), ("1-2", False),
])
def test_israeli_id_checksum(value, ok):
    assert mine.is_valid_israeli_id(value) is ok


def test_redacts_valid_id_but_not_order_numbers():
    line = "user id=123456782 opened order 123456789 at 10:02"
    assert mine.redact_pii(line) == "user id=[IL_ID] opened order 123456789 at 10:02"


def test_id_with_dash_and_not_inside_longer_numbers():
    assert mine.redact_pii("ID 12345678-2.") == "ID [IL_ID]."
    assert mine.redact_pii("ref 91234567823 end") == "ref 91234567823 end"


@pytest.mark.parametrize("email", ["dana.levi@acme.example", "x+tag@mail.co.il", "Markus_B@northwind-integrations.example"])
def test_emails(email):
    assert mine.redact_pii(f"from <{email}> ok") == "from <[EMAIL]> ok"


@pytest.mark.parametrize("phone", ["050-1234567", "03-5550199", "+972-3-555-0199", "+972 54 123 4567", "0541234567", "054 123 4567"])
def test_phones(phone):
    assert mine.redact_pii(f"call {phone} now") == "call [PHONE] now"


def test_not_phones():
    for s in ("build 2026-10-31", "port 8080", "1234567", "version 3.14.15"):
        assert mine.redact_pii(s) == s


def test_full_log_line():
    line = ('2026-10-31T10:02:11Z INFO ask user=dana.levi@acme.example q="my ID is 039337423, '
            'call me on 052-7654321 about invoice 123456789"')
    assert mine.redact_pii(line) == ('2026-10-31T10:02:11Z INFO ask user=[EMAIL] q="my ID is [IL_ID], '
                                     'call me on [PHONE] about invoice 123456789"')


def test_hebrew_text_around_pii():
    assert mine.redact_pii("ת.ז. 123456782, טלפון 050-1234567") == "ת.ז. [IL_ID], טלפון [PHONE]"

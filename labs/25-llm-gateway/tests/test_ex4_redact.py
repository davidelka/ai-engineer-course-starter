"""Exercise 4: redact emails, Israeli phone numbers and Israeli IDs before forwarding."""

import hashlib

import pytest

import mine


# ---------------------------------------------------------------- the ID check digit
@pytest.mark.parametrize("digits,ok", [
    ("123456782", True), ("000000018", True), ("039337423", True),
    ("123456789", False), ("000000019", False),
    ("12345678", False), ("1234567820", False), ("12345678a", False), ("", False),
])
def test_israeli_id_check_digit(digits, ok):
    assert mine.israeli_id_valid(digits) is ok


# ---------------------------------------------------------------- each type
def test_email():
    r = mine.redact("please add dana.levi@acme.example to Jira")
    assert r.text == "please add [EMAIL_1] to Jira"
    assert [f.type for f in r.findings] == ["email"]


@pytest.mark.parametrize("phone", ["054-1234567", "0541234567", "054-123-4567", "+972-54-123-4567",
                                   "+972 54 1234567", "03-5550199", "+972-3-555-0199", "077-1234567"])
def test_phone_formats(phone):
    r = mine.redact(f"call me at {phone} tomorrow", ["phone_il"])
    assert r.text == "call me at [PHONE_IL_1] tomorrow", phone


@pytest.mark.parametrize("text", ["order 2026-11-01", "build 12345678", "ticket ACME-1234567",
                                  "version 1.106.6", "x0541234567890"])
def test_things_that_are_not_phones(text):
    assert mine.redact(text, ["phone_il"]).text == text


def test_valid_id_is_redacted_invalid_one_is_not():
    r = mine.redact("ID 123456782, invoice 123456789")
    assert r.text == "ID [IL_ID_1], invoice 123456789"


def test_ten_digits_is_not_an_id():
    assert mine.redact("account 1234567820", ["il_id"]).text == "account 1234567820"


# ---------------------------------------------------------------- numbering and identity
def test_same_value_same_placeholder_and_per_type_numbering():
    r = mine.redact("a@x.io wrote to b@y.io; cc A@X.io. Phone 0541234567 or +972-54-123-4567.")
    assert r.text == "[EMAIL_1] wrote to [EMAIL_2]; cc [EMAIL_1]. Phone [PHONE_IL_1] or [PHONE_IL_1]."


def test_findings_have_original_offsets_sorted():
    text = "id 123456782 mail a@x.io"
    r = mine.redact(text)
    assert [(f.type, text[f.start:f.end]) for f in r.findings] == [("il_id", "123456782"), ("email", "a@x.io")]
    assert [f.placeholder for f in r.findings] == ["[IL_ID_1]", "[EMAIL_1]"]


def test_fingerprint_is_salted_hash_of_normalized_value_never_the_value():
    r = mine.redact("A@X.io", salt="s3")
    f = r.findings[0]
    assert f.fingerprint == hashlib.sha256(b"s3a@x.io").hexdigest()[:12]
    assert "a@x.io" not in repr(f).lower()


def test_phone_fingerprint_uses_normalized_digits():
    a = mine.redact("+972-54-123-4567").findings[0].fingerprint
    b = mine.redact("0541234567").findings[0].fingerprint
    assert a == b == hashlib.sha256(b"0541234567").hexdigest()[:12]


# ---------------------------------------------------------------- priority and types
def test_email_wins_over_digits_inside_it():
    r = mine.redact("user123456782@acme.example")
    assert r.text == "[EMAIL_1]" and len(r.findings) == 1


def test_landline_without_separators_is_a_phone_not_an_id():
    # 035550193 is BOTH a Tel Aviv landline without separators and a valid ID number.
    assert mine.israeli_id_valid("035550193")
    r = mine.redact("office 035550193")
    assert r.text == "office [PHONE_IL_1]"


def test_priority_does_not_depend_on_the_order_of_types():
    r = mine.redact("user123456782@acme.example", ["il_id", "email"])
    assert r.text == "[EMAIL_1]"


def test_only_requested_types():
    r = mine.redact("a@x.io 0541234567 123456782", ["il_id"])
    assert r.text == "a@x.io 0541234567 [IL_ID_1]"
    assert r.counts == {"il_id": 1}


def test_unknown_type_is_an_error():
    with pytest.raises(ValueError):
        mine.redact("x", ["credit_card"])


def test_counts_per_type():
    r = mine.redact("a@x.io a@x.io b@x.io 0541234567")
    assert r.counts == {"email": 3, "phone_il": 1}


def test_no_pii_no_change():
    r = mine.redact("Can I get read access to Confluence?")
    assert r.text == "Can I get read access to Confluence?" and r.findings == []


# ---------------------------------------------------------------- one numbering per request
def test_known_dict_shares_numbering_across_messages():
    known = {}
    r1 = mine.redact("from a@x.io", known=known)
    r2 = mine.redact("to b@x.io and back to a@x.io", known=known)
    assert r1.text == "from [EMAIL_1]"
    assert r2.text == "to [EMAIL_2] and back to [EMAIL_1]"
    assert known[("email", "b@x.io")] == "[EMAIL_2]"

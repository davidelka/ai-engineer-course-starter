"""Exercise 4: PII redaction (emails, Israeli phones, Israeli IDs) for span attributes."""

import json

import pytest

from mine import israeli_id_valid, redact_attributes, redact_text


@pytest.mark.parametrize("s,ok", [("123456782", True), ("000000018", True), ("123456789", False),
                                  ("12345678", False), ("1234567820", False), ("12345678a", False)])
def test_id_check_digit(s, ok):
    assert israeli_id_valid(s) is ok


def test_email():
    out, n = redact_text("write to dana.levi@acme.example today")
    assert out == "write to [EMAIL] today" and n == 1


@pytest.mark.parametrize("phone", ["052-1234567", "0521234567", "052-123-4567", "03-1234567", "+972-52-123-4567",
                                   "+972 54 765 4321", "077 123 4567"])
def test_phones(phone):
    out, n = redact_text(f"call {phone} now")
    assert out == "call [PHONE] now" and n == 1


def test_valid_id_is_redacted_invalid_is_kept():
    out, n = redact_text("ID 123456782, order 123456789")
    assert out == "ID [IL_ID], order 123456789" and n == 1


def test_ids_inside_longer_numbers_are_kept():
    out, n = redact_text("invoice 1234567820 and 91234567821")
    assert n == 0 and out == "invoice 1234567820 and 91234567821"


def test_everything_together_and_empty():
    out, n = redact_text("Dana, 123456782, 054-7654321, dana@gmail.com")
    assert out == "Dana, [IL_ID], [PHONE], [EMAIL]" and n == 3
    assert redact_text("") == ("", 0)


def test_attributes_new_dict_lists_json_and_skip():
    msgs = json.dumps([{"role": "user", "parts": [{"type": "text", "content": "my id is 123456782"}]}])
    attrs = {"gen_ai.input.messages": msgs, "tags": ["dana@gmail.com", "ok"], "n": 3, "flag": True,
             "obskit.user.id": "dana@gmail.com"}
    before = dict(attrs)
    out, n = redact_attributes(attrs, skip=["obskit.user.id"])
    assert attrs == before, "redact_attributes must not modify its input"
    assert n == 2
    assert json.loads(out["gen_ai.input.messages"])[0]["parts"][0]["content"] == "my id is [IL_ID]"
    assert out["tags"] == ["[EMAIL]", "ok"] and out["n"] == 3 and out["flag"] is True
    assert out["obskit.user.id"] == "dana@gmail.com"
    t, _ = redact_attributes({"t": ("a@b.co",)})
    assert t["t"] == ("[EMAIL]",)


def test_works_inside_the_otel_processor():
    """Your redact_text plugged into obskit's RedactingSpanProcessor, end to end."""
    pytest.importorskip("opentelemetry.sdk")
    from obskit import setup_tracing, span
    tr = setup_tracing("t", memory=True, redact=redact_text)
    with span("x", attributes={"q": "phone 052-1234567"}) as sp:
        sp.add_event("note", {"who": "a@b.co"})
    tr.shutdown()
    s = tr.memory.spans[0]
    assert s["attributes"]["q"] == "phone [PHONE]" and s["events"][0]["attributes"]["who"] == "[EMAIL]"
    assert s["attributes"]["obskit.redacted"] == 2

"""M8: what is masked before anything goes to a cloud model (mine.redact_for_cloud)."""

from mine import redact_for_cloud


def test_each_label():
    text = ("IBAN IL62 0108 0000 0009 9999 999, card 4111 1111 1111 1111, ID 000000018, "
            "mail dana@example.com, phone 050-555-0142, account 12-345-678901.")
    out, counts = redact_for_cloud(text)
    assert out == ("IBAN [IBAN], card [CARD], ID [IL_ID], mail [EMAIL], phone [PHONE], "
                   "account [BANK_ACCOUNT].")
    assert counts == {"IBAN": 1, "CARD": 1, "IL_ID": 1, "EMAIL": 1, "PHONE": 1, "BANK_ACCOUNT": 1}


def test_card_needs_luhn():
    out, counts = redact_for_cloud("order 4111 1111 1111 1112 shipped")
    assert out == "order 4111 1111 1111 1112 shipped" and counts == {}


def test_card_with_dashes_and_iban_without_spaces():
    out, counts = redact_for_cloud("5500-0000-0000-0004 and IL620108000000099999999")
    assert out == "[CARD] and [IBAN]" and counts == {"CARD": 1, "IBAN": 1}


def test_clean_text_and_templates_untouched():
    for t in ["דמי שכירות 4,200 ש\"ח עד ה-5 לחודש", "account XX-XXX-XXXXXX", "flight FE 701 at 06:10",
              "2026-12-03 16:15"]:
        assert redact_for_cloud(t) == (t, {})


def test_counts_only_new_placeholders():
    out, counts = redact_for_cloud("already [PHONE] here, new 052-555-0101")
    assert out == "already [PHONE] here, new [PHONE]" and counts == {"PHONE": 1}


def test_hebrew_context():
    out, counts = redact_for_cloud("אפשר לחזור אליי ב-050-555-0199 או במייל david@example.org")
    assert "[PHONE]" in out and "[EMAIL]" in out and counts == {"PHONE": 1, "EMAIL": 1}

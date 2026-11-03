"""HTML: keep the content, drop the page chrome (nav, cookie banner, breadcrumbs, sidebar, footer).

Two extractors:
- "rules" (default): BeautifulSoup. Drops non-content tags and elements whose class/id/role
  says they are chrome, picks <main>/<article>/role=main when present, and turns the rest
  into markdown-ish text: <h2> -> '## ', <li> -> '- ', <tr> -> 'a | b | c'. Transparent and
  predictable: you can read exactly why something was dropped.
- "trafilatura": the widely used main-content extractor (pip install trafilatura). Better
  on arbitrary web pages it has never seen; less predictable on a known intranet template.

naive_text() is the "before" picture: every text node in the page, which is what a
`soup.get_text()` one-liner indexes.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import LoadResult, table_rows_to_text

DROP_TAGS = ("script", "style", "noscript", "template", "svg", "form", "nav", "header",
             "footer", "aside", "button", "iframe", "input", "select", "head")
CHROME_RE = re.compile(r"cookie|consent|banner|breadcrumb|sidebar|side-bar|menu|navbar|"
                       r"nav-|footer|share|social|advert|promo|skip-link", re.I)
BLOCKS = {"p", "div", "section", "article", "main", "li", "ul", "ol", "table", "pre",
          "blockquote", "dl", "dt", "dd", "figure", "figcaption", "h1", "h2", "h3", "h4",
          "h5", "h6", "body", "tr", "td", "th", "thead", "tbody"}


def _soup(html: str):
    from bs4 import BeautifulSoup

    try:
        return BeautifulSoup(html, "lxml")
    except Exception:  # lxml not installed
        return BeautifulSoup(html, "html.parser")


def naive_text(html: str) -> str:
    soup = _soup(html)
    for t in soup(["script", "style"]):
        t.decompose()
    return soup.get_text("\n")


def _is_chrome(el) -> bool:
    attrs = getattr(el, "attrs", None) or {}
    label = " ".join([attrs.get("id", "") or "", " ".join(attrs.get("class", []) or []),
                      attrs.get("role", "") or ""])
    if attrs.get("role") in ("navigation", "banner", "contentinfo", "complementary"):
        return True
    return bool(label.strip()) and bool(CHROME_RE.search(label))


def _inline(el) -> str:
    return " ".join(el.get_text().split())


def _walk(el, out: list[str], list_depth: int = 0) -> None:
    from bs4 import NavigableString, Tag

    for child in el.children:
        if isinstance(child, NavigableString):
            if child.__class__.__name__ in ("Comment", "Doctype", "CData", "ProcessingInstruction"):
                continue
            s = " ".join(str(child).split())
            if s:
                out.append(s)
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name
        if re.fullmatch(r"h[1-6]", name):
            out.append("#" * int(name[1]) + " " + _inline(child))
        elif name in ("ul", "ol"):
            _list(child, out, list_depth)
        elif name == "table":
            rows = [[_inline(c) for c in tr.find_all(["td", "th"])] for tr in child.find_all("tr")]
            out.append(table_rows_to_text(rows))
        elif name == "pre":
            out.append("```\n" + child.get_text().strip("\n") + "\n```")
        elif name == "br":
            continue
        elif name in ("p", "blockquote", "dt", "dd", "figcaption") or not (
                set(c.name for c in child.find_all(True)) & BLOCKS):
            text = _inline(child)
            if text:
                out.append(text)
        else:
            _walk(child, out, list_depth)


def _list(lst, out: list[str], depth: int) -> None:
    for i, li in enumerate(lst.find_all("li", recursive=False), 1):
        nested = [n.extract() for n in li.find_all(["ul", "ol"], recursive=False)]
        marker = f"{i}." if lst.name == "ol" else "-"
        text = _inline(li)
        if text:
            out.append("  " * depth + f"{marker} {text}")
        for n in nested:
            _list(n, out, depth + 1)


LIST_ITEM_RE = re.compile(r"^\s*(-|\d+\.) ")


def join_blocks(blocks: list[str]) -> str:
    """Blank line between blocks, single newline between consecutive list items."""
    out = ""
    prev = None
    for b in (x for x in blocks if x.strip()):
        if prev is not None:
            out += "\n" if LIST_ITEM_RE.match(b) and LIST_ITEM_RE.match(prev) else "\n\n"
        out += b
        prev = b
    return out


def extract_rules(html: str) -> tuple[str, dict, list[str]]:
    soup = _soup(html)
    meta: dict = {}
    if soup.title and soup.title.string:
        meta["html_title"] = " ".join(soup.title.string.split())
    root_html = soup.find("html")
    if root_html is not None:
        if root_html.get("lang"):
            meta["language"] = root_html.get("lang").split("-")[0]
        if root_html.get("dir"):
            meta["dir"] = root_html.get("dir")
    removed: list[str] = []
    for t in soup.find_all(DROP_TAGS):
        if t.name not in ("head",):
            txt = _inline(t)
            if txt:
                removed.append(f"<{t.name}> {txt[:120]}")
        t.decompose()
    for t in list(soup.find_all(True)):
        if getattr(t, "decomposed", False):
            continue
        if t.name not in ("html", "body", "main", "article") and _is_chrome(t):
            txt = _inline(t)
            if txt:
                removed.append(f"<{t.name} {t.get('class') or t.get('id')}> {txt[:120]}")
            t.decompose()
    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.body or soup
    out: list[str] = []
    _walk(main, out)
    return join_blocks(out), meta, removed


def extract_trafilatura(html: str) -> str:
    import trafilatura

    return trafilatura.extract(html, output_format="markdown", include_tables=True,
                               include_comments=False, favor_precision=True) or ""


def load_html(path: Path, data: bytes, *, extractor: str = "rules") -> LoadResult:
    html = data.decode("utf-8", errors="replace")
    if extractor == "trafilatura":
        text, meta, removed = extract_trafilatura(html), {}, []
    else:
        text, meta, removed = extract_rules(html)
    if "title" not in meta:
        m = re.search(r"^# (.+)$", text, re.M)
        if m:
            meta["title"] = m.group(1).strip()
    return LoadResult(text=text, meta=meta, raw_text=naive_text(html), removed=removed)

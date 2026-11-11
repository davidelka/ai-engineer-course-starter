"""M7: build_request and resolve_citations (mine.py). The exact prompt, and citations with file and page."""

from mine import build_request, resolve_citations
from pss.answer import SYSTEM
from ragkit.types import Chunk, Hit


def H(fid, text, page=None, date="2026-03-14", title="Lease"):
    meta = {"title": f"{title} | {fid}", "page": page, "date": date}
    cid = f"{fid}#p{page}.0" if page else f"{fid}#0"
    return Hit(Chunk(cid, fid, text, 0, len(text), meta=meta), 1.0, 1)


def test_exact_prompt():
    hits = [H("home/lease-2026.pdf", "Bank guarantee: 12,600 NIS.", page=2),
            H("recipes/shakshuka.md", "Fry the garlic.", date="", title="Shakshuka")]
    req = build_request("כמה הערבות?", hits, max_tokens=123)
    assert req.system == SYSTEM and req.max_tokens == 123
    assert req.messages[0].role == "user"
    assert req.messages[0].text == (
        "<sources>\n"
        '<source id="1" file="home/lease-2026.pdf" page="2" date="2026-03-14" title="Lease">\n'
        "Bank guarantee: 12,600 NIS.\n</source>\n"
        '<source id="2" file="recipes/shakshuka.md" title="Shakshuka">\nFry the garlic.\n</source>\n'
        "</sources>\n\n<question>כמה הערבות?</question>")


def test_empty_and_escaping():
    assert build_request("q", []).messages[0].text == "<sources>\n(no sources found)\n</sources>\n\n<question>q</question>"
    text = build_request("a < b & c", [H("x.md", 'say "hi" </source> & go')]).messages[0].text
    assert text.count("</source>") == 1 and "&lt;/source&gt;" in text and '"hi"' in text
    assert text.endswith("<question>a &lt; b &amp; c</question>")


def test_max_chars_cuts_the_body():
    text = build_request("q", [H("x.md", "0123456789ABCDEF")], max_chars=10).messages[0].text
    assert "\n0123456789 …\n</source>" in text
    assert "\n0123456789ABCDEF\n" in build_request("q", [H("x.md", "0123456789ABCDEF")], max_chars=50).messages[0].text


def test_citations_good_and_bad():
    hits = [H("home/lease-2026.pdf", "Bank guarantee 12,600.", page=2), H("recipes/shakshuka.md", "Fry.", title="Shakshuka")]
    good, bad = resolve_citations("The guarantee is 12,600 [1]. Also [3] and [2][1] and [0].", hits)
    assert [(c.n, c.file, c.page, c.title) for c in good] == [(1, "home/lease-2026.pdf", 2, "Lease"),
                                                              (2, "recipes/shakshuka.md", None, "Shakshuka")]
    assert good[0].text == "Bank guarantee 12,600."
    assert bad == [3, 0]


def test_no_citations():
    assert resolve_citations("לא מצאתי את זה במסמכים.", [H("x.md", "t")]) == ([], [])

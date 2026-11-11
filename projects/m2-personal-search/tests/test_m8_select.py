"""M8: select_for_cloud (mine.py). Protected folders never leave the machine."""

from mine import select_for_cloud
from ragkit.types import Chunk, Hit


def H(fid, i=0):
    return Hit(Chunk(f"{fid}#{i}", fid, "text", 0, 4, meta={}), 1.0, 1)


NEVER = ["health/", "finance/"]


def test_withholds_protected_files():
    hits = [H("health/dental-checkup-2026-12.txt"), H("home/lease-2026.pdf"), H("finance/car-insurance-2026.pdf"),
            H("health/dental-checkup-2026-12.txt", 1), H("receipts/receipt-laptop-2026-03.html")]
    send, withheld = select_for_cloud(hits, NEVER, max_sources=5)
    assert [h.chunk.doc_id for h in send] == ["home/lease-2026.pdf", "receipts/receipt-laptop-2026-03.html"]
    assert withheld == ["finance/car-insurance-2026.pdf", "health/dental-checkup-2026-12.txt"]


def test_max_sources_after_withholding():
    hits = [H("health/a.txt"), H("home/a.md"), H("home/b.md"), H("home/c.md")]
    send, withheld = select_for_cloud(hits, NEVER, max_sources=2)
    assert [h.chunk.doc_id for h in send] == ["home/a.md", "home/b.md"] and withheld == ["health/a.txt"]


def test_uses_exclude_semantics():
    hits = [H("kids/private/diary.md"), H("kids/report.md"), H("notes/salary.KEY")]
    send, withheld = select_for_cloud(hits, ["private/", "*.key"], max_sources=5)
    assert [h.chunk.doc_id for h in send] == ["kids/report.md"]
    assert withheld == ["kids/private/diary.md", "notes/salary.KEY"]          # case-insensitive, any component


def test_nothing_protected():
    hits = [H("home/a.md")]
    assert select_for_cloud(hits, [], max_sources=3) == (hits, [])

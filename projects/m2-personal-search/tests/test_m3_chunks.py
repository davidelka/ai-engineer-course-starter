"""M3: file_to_chunks (mine.file_to_chunks). Chunks must remember their file and page."""

from pathlib import Path

from mine import file_to_chunks
from pss.extract import Extracted, Unit
from pss.scan import FileEntry
from ragkit.chunking import make_chunker

CHUNKER = make_chunker("recursive:20:0", tokenizer="approx")      # small chunks, so a page splits


def words(n, tag):
    return " ".join(f"{tag}{i}." for i in range(n))


def entry(fid):
    root = Path("/tmp/sample")
    return FileEntry(id=fid, path=root / fid, root=root, size=10, mtime=0.0, ext=Path(fid).suffix)


def ex(fid, units, fmt="pdf"):
    return Extracted(id=fid, title="Lease", format=fmt, language="he", date="2026-03-01",
                     date_source="filename", units=units)


def test_pdf_pages_keep_their_page():
    chunks = file_to_chunks(ex("home/lease-2026.pdf", [Unit(1, words(30, "a")), Unit(2, words(30, "b"))]),
                            entry("home/lease-2026.pdf"), CHUNKER)
    assert len(chunks) >= 4
    pages = [c.meta["page"] for c in chunks]
    assert pages == sorted(pages) and set(pages) == {1, 2}
    first_p2 = next(c for c in chunks if c.meta["page"] == 2)
    assert first_p2.id == "home/lease-2026.pdf#p2.0"                     # the chunker's index inside the page
    assert chunks[0].id == "home/lease-2026.pdf#p1.0"
    assert [c.index for c in chunks] == list(range(len(chunks)))           # renumbered across the file


def test_meta_and_title():
    c = file_to_chunks(ex("home/lease-2026.pdf", [Unit(1, "short page")]), entry("home/lease-2026.pdf"), CHUNKER)[0]
    assert c.doc_id == "home/lease-2026.pdf"
    assert c.meta["title"] == "Lease | home/lease-2026.pdf"
    for k, v in {"file": "home/lease-2026.pdf", "folder": "home", "date": "2026-03-01", "page": 1,
                 "format": "pdf", "language": "he"}.items():
        assert c.meta[k] == v, k
    assert c.meta["source_path"].endswith("home/lease-2026.pdf")


def test_no_pages():
    chunks = file_to_chunks(ex("recipes/shakshuka.md", [Unit(None, words(30, "c"))], fmt="md"),
                            entry("recipes/shakshuka.md"), CHUNKER)
    assert chunks[0].id == "recipes/shakshuka.md#0" and chunks[1].id == "recipes/shakshuka.md#1"
    assert all(c.meta["page"] is None for c in chunks)


def test_blank_units_are_skipped():
    chunks = file_to_chunks(ex("scans/note.pdf", [Unit(1, "   \n "), Unit(2, "real text")]), entry("scans/note.pdf"), CHUNKER)
    assert [c.meta["page"] for c in chunks] == [2] and chunks[0].index == 0

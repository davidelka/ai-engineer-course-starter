"""M2: the first privacy boundary (mine.is_excluded)."""

import pytest

from mine import is_excluded
from pss.config import DEFAULT_EXCLUDES


@pytest.mark.parametrize("path,pattern", [
    (".env", ".*"),
    (".git/config", ".*"),
    ("notes/.obsidian/workspace.json", ".*"),
    ("private/passwords-DO-NOT-INDEX.txt", "private/"),
    ("work/Private/salary.pdf", "private/"),          # case-insensitive
    ("keys/server.key", "*.key"),
    ("misc/my-passwords.txt", "*password*"),
    ("node_modules/x", "node_modules/"),               # the scanner's folder probe
])
def test_default_excludes(path, pattern):
    assert is_excluded(path, DEFAULT_EXCLUDES) == pattern


@pytest.mark.parametrize("path", [
    "home/lease-2026.pdf", "kids/school-trip-permission-2026-11.docx", "notes/private.txt",
    "courses/ai-engineer-rag-notes.md", "receipts/receipt-laptop-2026-03.html",
])
def test_normal_files_are_not_excluded(path):
    assert is_excluded(path, DEFAULT_EXCLUDES) is None


def test_first_matching_pattern_is_returned():
    assert is_excluded("private/a.key", ["*.key", "private/"]) == "*.key"
    assert is_excluded("private/a.key", ["private/", "*.key"]) == "private/"


def test_path_patterns_with_slash():
    pats = ["finance/*.pdf", "kids/**/report*"]
    assert is_excluded("finance/car-insurance-2026.pdf", pats) == "finance/*.pdf"
    assert is_excluded("finance/2026/car.pdf", pats) is None           # * does not cross /
    assert is_excluded("kids/report-noa.pdf", pats) == "kids/**/report*"  # ** = zero folders
    assert is_excluded("kids/2026/t1/report-noa.pdf", pats) == "kids/**/report*"
    assert is_excluded("home/kids/report.pdf", pats) is None           # anchored at the start
    assert is_excluded("finance/car.pdf", ["/finance/*.pdf"]) == "/finance/*.pdf"


def test_folder_pattern_does_not_match_the_file_name():
    assert is_excluded("notes/private", ["private/"]) is None
    assert is_excluded("private/notes.md", ["private/"]) == "private/"


def test_dot_slash_comments_and_blank_patterns():
    assert is_excluded("./home/.hidden.md", ["", "# comment", ".*"]) == ".*"
    assert is_excluded("./home/a.md", ["", "# *.md"]) is None


def test_sample_scan_skips_private_and_hidden():
    from pss.config import SAMPLE
    from pss.scan import scan

    rep = scan(SAMPLE, DEFAULT_EXCLUDES, is_excluded_fn=is_excluded)
    ids = {f.id for f in rep.files}
    assert not any(i.startswith(("private/", ".cache/")) for i in ids)
    assert "home/lease-2026.pdf" in ids and len(ids) == 43

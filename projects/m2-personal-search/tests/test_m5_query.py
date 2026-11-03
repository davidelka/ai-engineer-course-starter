"""M5: filters inside the query (mine.parse_query)."""

import pytest

from mine import parse_query


def test_example_from_the_docstring():
    p = parse_query('type:pdf,doc folder:"kids/" after:2026-06 טיול שנתי')
    assert p.text == "טיול שנתי"
    assert p.filters == {"type": ["pdf", "docx"], "folder": ["kids"], "after": "2026-06-01"}
    assert p.warnings == []


def test_plain_query_has_no_filters():
    p = parse_query("  ערבות   בנקאית ")
    assert p.text == "ערבות בנקאית" and p.filters == {} and p.warnings == []


def test_hebrew_keys_and_values():
    p = parse_query("סוג:pdf תיקייה:home שפה:עברית אחרי:2026 אחריות")
    assert p.text == "אחריות"
    assert p.filters == {"type": ["pdf"], "folder": ["home"], "lang": "he", "after": "2026-01-01"}


def test_before_and_full_dates():
    p = parse_query("before:2026-11-18 after:2026-1 appointment")
    assert p.filters == {"before": "2026-11-18", "after": "2026-01-01"} and p.text == "appointment"


def test_bad_date_stays_in_text_with_a_warning():
    p = parse_query("after:yesterday receipt")
    assert "after" not in p.filters and p.text == "after:yesterday receipt" and len(p.warnings) == 1


def test_unknown_keys_are_text():
    p = parse_query("תור בשעה 10:40 see http://example.com")
    assert p.filters == {} and p.text == "תור בשעה 10:40 see http://example.com"


def test_unknown_type_and_language_warn():
    p = parse_query("type:pptx,scan lang:fr x")
    assert p.filters == {"type": ["image"]} and len(p.warnings) == 2 and p.text == "x"


def test_type_list_without_duplicates_and_folder_list():
    p = parse_query("type:doc,docx,word folder:Kids,/health/")
    assert p.filters == {"type": ["docx"], "folder": ["kids", "health"]} and p.text == ""


@pytest.mark.parametrize("q,expected", [
    ("type:pdf אחריות", ["home/fridge-warranty-2026-03.pdf"]),
    ("folder:receipts after:2026-06", ["receipts/receipt-pharmacy-2026-08.txt", "receipts/receipt-supermarket-2026-10.html"]),
])
def test_filters_work_in_the_index(q, expected, sample_index):
    got = [f for f, _ in sample_index.rank_files(q, mode="bm25", depth=5)]
    assert sorted(got) == sorted(expected)


@pytest.fixture(scope="module")
def sample_index(tmp_path_factory):
    from pss.evaluate import build_index, eval_settings

    idx, _ = build_index(eval_settings(index_dir=str(tmp_path_factory.mktemp("idx"))))
    return idx

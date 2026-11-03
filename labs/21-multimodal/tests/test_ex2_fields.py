"""Exercise 2: field-level scoring of an extraction (mine.normalize_field, mine.field_accuracy)."""

import json
from pathlib import Path

import pytest

import mine
from acme_vision import KINDS, Receipt

GOLD = json.loads((Path(__file__).resolve().parents[1] / "data" / "gold.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("value,expected", [
    (345.4, 345.4), ("345.40", 345.4), ("₪345.40", 345.4), ("NIS 1,345.40", 1345.4), ("345.40 ils", 345.4),
    ("$ 85", 85.0), (52.686, 52.69), (None, None), ("about three hundred", "about three hundred"),
])
def test_money(value, expected):
    assert mine.normalize_field(value, "money") == expected


@pytest.mark.parametrize("value,expected", [
    ("2026-10-14", "2026-10-14"), ("14/10/2026", "2026-10-14"), ("14.10.2026", "2026-10-14"),
    ("4-1-2026", "2026-01-04"), ("Oct 14, 2026", "2026-10-14"), ("October 14 2026", "2026-10-14"),
    ("14 Oct 2026", "2026-10-14"), ("2026-14-10", "2026-14-10"), ("yesterday", "yesterday"), (None, None),
])
def test_date(value, expected):
    assert mine.normalize_field(value, "date") == expected


def test_int_text_code_list():
    assert mine.normalize_field("5", "int") == 5 and mine.normalize_field(4.6, "int") == 5
    assert mine.normalize_field("1,200", "int") == 1200
    assert mine.normalize_field("  Cafe   NOIR. ", "text") == "cafe noir"
    assert mine.normalize_field("SPW-4013 ", "code") == "SPW-4013"
    assert mine.normalize_field("spw-4013", "code") != "SPW-4013"
    assert mine.normalize_field(["Cancel", " retry"], "list") == ["cancel", "retry"]
    assert mine.normalize_field(None, "list") is None and mine.normalize_field(None, "text") is None


def test_field_accuracy_perfect_and_formatting_only():
    gold = GOLD["receipt"]
    pred = dict(gold, total="₪345.40", date="14/10/2026", merchant="CAFE NOIR")
    rep = mine.field_accuracy(pred, gold, KINDS["receipt"])
    assert rep.accuracy == 1.0 and rep.mismatches == []
    assert list(rep.correct) == list(KINDS["receipt"])  # in the order of kinds


def test_field_accuracy_counts_errors_and_keeps_originals():
    gold = GOLD["receipt"]
    pred = dict(gold, total=346.4, vat=None, item_lines=8)
    rep = mine.field_accuracy(pred, gold, KINDS["receipt"])
    assert rep.accuracy == pytest.approx(8 / 11)
    assert ("total", 346.4, 345.4) in rep.mismatches and ("vat", None, 52.69) in rep.mismatches
    assert rep.correct["merchant"] and not rep.correct["item_lines"]


def test_field_accuracy_pydantic_missing_and_none():
    gold = GOLD["receipt"]
    rep = mine.field_accuracy(Receipt(**gold), gold, KINDS["receipt"])
    assert rep.accuracy == 1.0
    partial = {k: v for k, v in gold.items() if k != "card_last4"}
    rep = mine.field_accuracy(partial, gold, KINDS["receipt"])
    assert rep.correct["card_last4"] is False
    rep = mine.field_accuracy(None, gold, KINDS["receipt"])
    assert rep.accuracy == 0.0 and len(rep.mismatches) == len(KINDS["receipt"])
    # None in gold and missing in pred agree
    assert mine.field_accuracy({}, {"tip": None}, {"tip": "money"}).accuracy == 1.0


def test_lists_ignore_order_and_case():
    gold = GOLD["whiteboard"]
    pred = dict(gold, components=list(reversed([c.upper() for c in gold["components"]])))
    assert mine.field_accuracy(pred, gold, KINDS["whiteboard"]).accuracy == 1.0

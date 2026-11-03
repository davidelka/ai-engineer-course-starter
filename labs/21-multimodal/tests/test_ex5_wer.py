"""Exercise 5: Hebrew normalization and word error rate (mine.normalize_hebrew, mine.wer)."""

import pytest

import mine


@pytest.mark.parametrize("raw,norm", [
    ("שָׁלוֹם, עוֹלָם!", "שלומ עולמ"),
    ('צה"ל', "צהל"),
    ("צה״ל", "צהל"),
    ("ג'ירפה", "גירפה"),
    ("ג׳ירפה", "גירפה"),
    ("בית־ספר", "בית ספר"),
    ("בית-ספר", "בית ספר"),
    ("‏שלום‎   World", "שלומ world"),
    ("יש 3 ילדים.", "יש 3 ילדימ"),
    ("(מלך) ... ספר?", "מלכ ספר"),
    ("וכו'", "וכו"),
    ("", ""),
])
def test_normalize(raw, norm):
    assert mine.normalize_hebrew(raw) == norm


def test_finals_flag():
    assert mine.normalize_hebrew("מלך", finals=False) == "מלך"
    assert mine.normalize_hebrew("ירושלים") == mine.normalize_hebrew("ירושלימ")


def test_wer_basic_counts():
    r = mine.wer("a b c d", "a x c d", normalize=None)
    assert (r.rate, r.substitutions, r.deletions, r.insertions) == (0.25, 1, 0, 0)
    assert (r.ref_len, r.hyp_len) == (4, 4)
    r = mine.wer("a b c", "a b c d e", normalize=None)
    assert (r.insertions, r.rate) == (2, pytest.approx(2 / 3))
    r = mine.wer("a b c", "", normalize=None)
    assert (r.deletions, r.rate) == (3, 1.0)


def test_wer_ops_and_tie_breaking():
    r = mine.wer("a b", "a c", normalize=None)
    assert r.ops == [("ok", "a", "a"), ("sub", "b", "c")]
    r = mine.wer("a b c", "a c", normalize=None)
    assert r.ops == [("ok", "a", "a"), ("del", "b", ""), ("ok", "c", "c")]
    r = mine.wer("a c", "a b c", normalize=None)
    assert r.ops == [("ok", "a", "a"), ("ins", "", "b"), ("ok", "c", "c")]


def test_wer_edge_cases():
    assert mine.wer("", "").rate == 0.0
    assert mine.wer("", "שלום").rate == 1.0
    assert mine.wer("שלום", "שלום שלום שלום").rate == 2.0


def test_wer_hebrew_normalization_matters():
    assert mine.wer("שָׁלוֹם, עוֹלָם", "שלום עולם").rate == 0.0
    assert mine.wer("שלום עולם", "שלום, עולם", normalize=None).rate == 0.5
    r = mine.wer("פתח את הספר בפרק שלוש", "פתח את הספר בברק שלוש")
    assert (r.substitutions, r.rate) == (1, 0.2)


def test_agrees_with_jiwer_when_installed():
    jiwer = pytest.importorskip("jiwer")
    pairs = [("אני רוצה לקנות כרטיס לאוטובוס", "אני רוצה כרטיס חדש לאוטובוס"),
             ("שלום מה שלומך היום", "שלום מה שלומכם"), ("a b c d e f", "a c d x e f g")]
    for ref, hyp in pairs:
        assert mine.wer(ref, hyp, normalize=None).rate == pytest.approx(jiwer.wer(ref, hyp))

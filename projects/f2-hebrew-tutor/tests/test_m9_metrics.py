"""M9: correction_metrics (mine.py). Did the tutor find the error the label says is there?"""

from hebtutor.hooks import load_mine

mine = load_mine()


def P(t, corrected):
    return {"error_type": t, "corrected": corrected, "original": "x", "explanation_ar": "x"}


def G(t, must=None):
    return {"error_type": t, "must_contain": must, "safety_flag": "none"}


ROWS = [
    {"pred": P("gender", "אני רוצה"), "gold": G("gender", "רוצה")},          # hit
    {"pred": P("gender", "אני רוצה"), "gold": G("tense", "רציתי")},           # wrong type
    {"pred": None, "gold": G("gender", "גרה")},                               # missed
    {"pred": P("word_order", "אני הולך"), "gold": G(None)},                   # correction on a correct sentence
    {"pred": P("tense", "אכלתי"), "gold": G("tense", "אכלתי")},               # hit
    {"pred": P("tense", "אוכל"), "gold": G("tense", "אכלתי")},                # right type, wrong fix
    {"pred": None, "gold": G(None)},
]


def test_counts():
    m = mine.correction_metrics(ROWS)
    assert m["tp"] == 2 and m["predicted"] == 5 and m["gold_errors"] == 5
    assert m["false_positive_on_correct"] == 1
    assert m["hits"] == [True, False, False, False, True, False, False]


def test_per_type_sorted():
    m = mine.correction_metrics(ROWS)
    assert m["per_type"] == {"gender": [1, 2], "tense": [1, 3]}
    assert list(m["per_type"]) == ["gender", "tense"]


def test_must_contain_none_means_any_fix():
    m = mine.correction_metrics([{"pred": P("gender", "x"), "gold": G("gender", None)}])
    assert m["tp"] == 1 and m["hits"] == [True]


def test_empty():
    assert mine.correction_metrics([]) == {"tp": 0, "predicted": 0, "gold_errors": 0, "false_positive_on_correct": 0,
                                           "per_type": {}, "hits": []}

"""Exercise 2: a rubric scorer without an LLM."""

import pytest

from mine import score_answer, term_in

Q = {
    "id": "t-1",
    "rubric": [
        {"id": "r1", "point": "recall", "weight": 2, "concepts": [["recall@k", "recall"], ["golden set", "גולדן"]], "need": 2},
        {"id": "r2", "point": "hybrid", "weight": 1, "concepts": [["hybrid", "BM25"]]},
        {"id": "r3", "point": "rerank", "concepts": ["reranker"]},  # string group, default weight 1
    ],
}


# ---------------------------------------------------------------- term_in
@pytest.mark.parametrize("text,term", [
    ("We use a RAG pipeline", "rag"),
    ("trade-off between cost and latency", "trade off"),
    ("I measured recall@5 on the set", "recall"),
    ("we compared embeddings", "embedding"),
    ("והאמבדינג נשמר במאגר", "אמבדינג"),
    ("calibration against human labels", "calibrat*"),
    ("accuracy went up 20%", "%"),
    ("LLM_as_judge", "llm as judge"),
])
def test_term_found(text, term):
    assert term_in(text, term)


@pytest.mark.parametrize("text,term", [
    ("drag and drop", "rag"),
    ("we evaluate weekly", "eval"),
    ("tokenizers2", "tokenizer"),
    ("no calibration here", "calibrated"),
])
def test_term_not_found(text, term):
    assert not term_in(text, term)


# ---------------------------------------------------------------- score_answer
GOOD = ("I would build a golden set and measure recall@5, because retrieval fails silently. "
        "Then add hybrid search with BM25, but it costs latency, so I measure the gain. "
        "For example, a reranker on the top 50 improved precision by 12% in my project. "
        "This is the order I would follow, and each step is checked against the same set so "
        "that a change that helps one category and hurts another is visible immediately.")


def test_full_answer_covers_everything():
    r = score_answer(GOOD, Q)
    assert r["covered"] == ["r1", "r2", "r3"] and r["missing"] == []
    assert r["coverage"] == 1.0
    assert r["checks"] == {"length_ok": True, "tradeoff": True, "concrete": True, "measurement": True}
    assert r["score"] == 100
    assert r["words"] == len(GOOD.split())


def test_need_two_groups():
    # "recall" alone matches one of the two groups of r1, which needs 2
    r = score_answer("recall matters. hybrid search helps too.", Q)
    assert r["covered"] == ["r2"] and r["missing"] == ["r1", "r3"]
    assert r["coverage"] == round(1 / 4, 3)
    assert r["hits"]["r1"] == ["recall"]
    assert r["hits"]["r3"] == []


def test_hits_report_first_matching_term_of_each_group():
    r = score_answer("recall@k on a golden set, plus BM25", Q)
    assert r["hits"]["r1"] == ["recall@k", "golden set"]
    assert r["hits"]["r2"] == ["BM25"]


def test_score_formula():
    text = "reranker"  # covers r3 only (weight 1 of 4); 1 word -> length fails; no structure
    r = score_answer(text, Q)
    assert r["coverage"] == 0.25
    assert r["checks"] == {"length_ok": False, "tradeoff": False, "concrete": False, "measurement": False}
    assert r["score"] == round(100 * (0.75 * 0.25))


def test_length_limits_are_parameters():
    r = score_answer("reranker " * 10, Q, min_words=5, max_words=20)
    assert r["checks"]["length_ok"] is True
    r = score_answer("reranker " * 30, Q, min_words=5, max_words=20)
    assert r["checks"]["length_ok"] is False


def test_hebrew_answer_with_english_terms():
    he = ("הייתי בונה גולדן סט ומודד recall, ואחר כך מוסיף חיפוש hybrid. "
          "החיסרון: latency גבוה יותר, למשל 200ms.")
    r = score_answer(he, Q)
    assert "r1" in r["covered"] and "r2" in r["covered"]
    assert r["checks"]["tradeoff"] and r["checks"]["concrete"] and r["checks"]["measurement"]


def test_empty_rubric_raises():
    with pytest.raises(ValueError):
        score_answer("anything", {"rubric": []})
    with pytest.raises(ValueError):
        score_answer("anything", {"rubric": [{"id": "r1", "point": "x", "weight": 0, "concepts": [["x"]]}]})


def test_keyword_salad_shows_the_limit():
    """Not a bug to fix: a list of buzzwords scores well here. That is why the LLM
    grader (exercise 4) requires a quote per rubric point."""
    salad = "recall golden set hybrid BM25 reranker"
    assert score_answer(salad, Q)["coverage"] == 1.0


def test_reference_answers_from_the_bank_score_high():
    from interviewkit.bank import load_bank
    bank = load_bank()
    low = [q["id"] for q in bank if score_answer(q["answer"], q)["coverage"] < 1.0]
    assert not low, f"reference answers that miss rubric points with your scorer: {low}"

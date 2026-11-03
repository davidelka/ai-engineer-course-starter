"""M6: near-duplicate groups (mine.near_duplicate_groups)."""

from mine import near_duplicate_groups

BASE = ("The anode of the solar water heater should be replaced every three years and the "
        "heater itself serviced once a year before the winter starts by a technician")


def test_exact_and_near_copies_group_together():
    docs = {"a.txt": BASE, "a (1).txt": BASE, "a-v2.txt": BASE + " in October",
            "other.txt": "Red lentil soup with cumin and lemon, simmered for twenty five minutes"}
    assert near_duplicate_groups(docs) == [["a (1).txt", "a-v2.txt", "a.txt"]]


def test_threshold_is_used():
    docs = {"x": BASE, "y": BASE.replace("every three years", "every two years")}
    assert near_duplicate_groups(docs, threshold=0.6) == [["x", "y"]]
    assert near_duplicate_groups(docs, threshold=0.95) == []


def test_groups_are_transitive_and_sorted():
    w = [f"w{i}" for i in range(40)]
    a = " ".join(w[:30])
    b = " ".join(w[4:34])       # a~b
    c = " ".join(w[8:38])       # b~c, but a and c share less
    docs = {"c": c, "b": b, "a": a, "solo": "nothing in common here at all really"}
    assert near_duplicate_groups(docs, threshold=0.7) == [["a", "b", "c"]]


def test_empty_texts_are_never_duplicates():
    assert near_duplicate_groups({"e1": "", "e2": "", "x": BASE}) == []


def test_sample_folder_has_three_groups(tmp_path):
    from pss.evaluate import build_index, eval_settings

    idx, _ = build_index(eval_settings(index_dir=str(tmp_path / "idx")))
    groups = near_duplicate_groups(idx.doc_texts())
    assert groups == [["courses/ai-engineer-rag-notes-v2.md", "courses/ai-engineer-rag-notes.md"],
                      ["home/lease-2026 (1).pdf", "home/lease-2026.pdf"],
                      ["recipes/shakshuka-copy.md", "recipes/shakshuka.md"]]

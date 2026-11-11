"""M3: retrieve_phrases (mine.py). Phrases of the scenario, at or below the level, with a fallback."""

import pytest

from hebtutor.content import Content
from hebtutor.hooks import load_mine

mine = load_mine()


@pytest.fixture(scope="module")
def content():
    return Content()


def test_relevant_phrases_of_this_scenario(content):
    out = mine.retrieve_phrases(content, "bus_station", "A1", "כמה עולה כרטיס לתל אביב")
    assert out and all(set(o) == {"id", "he", "ar", "kind", "level", "score"} for o in out)
    assert all(o["level"] == "A1" for o in out)
    assert any("כרטיס" in o["he"] for o in out)
    hits = [o for o in out if o["id"]]
    assert hits and all(o["id"].startswith("bus_station") or o["kind"] == "vocab" for o in hits)
    assert [o["score"] for o in hits] == sorted([o["score"] for o in hits], reverse=True)


def test_level_filter_includes_lower_levels(content):
    out = mine.retrieve_phrases(content, "bus_station", "B1", "כרטיס", k=20)
    assert {o["level"] for o in out} <= {"A1", "A2", "B1"}
    a1 = mine.retrieve_phrases(content, "bus_station", "A1", "כרטיס", k=20)
    assert {o["level"] for o in a1} == {"A1"}


def test_fallback_to_scenario_phrases(content):
    out = mine.retrieve_phrases(content, "bus_station", "A1", "   ")
    expected = [p["he"] for p in content.scenarios["bus_station"].phrases_for("A1")][:3]
    assert [o["he"] for o in out] == expected
    assert all(o["id"] is None and o["score"] == 0.0 and o["kind"] == "phrase" for o in out)


def test_fallback_tops_up_to_three_without_repeats(content):
    out = mine.retrieve_phrases(content, "bus_station", "A1", "כן", k=6)
    assert len(out) >= 3 and len({o["he"] for o in out}) == len(out)

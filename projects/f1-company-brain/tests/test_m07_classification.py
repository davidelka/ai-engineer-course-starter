"""Milestone 7: request_classification, the label the gateway enforces (mine.request_classification)."""
from _impl import mine


def test_highest_wins():
    metas = [{"classification": "public"}, {"classification": "confidential"}, {"classification": "internal"}]
    assert mine.request_classification(metas) == "confidential"


def test_floor_and_defaults():
    assert mine.request_classification([{"classification": "public"}]) == "internal"       # floor internal
    assert mine.request_classification([{"classification": "public"}], floor="public") == "public"
    assert mine.request_classification([], floor="confidential") == "confidential"
    assert mine.request_classification([]) == "internal"
    assert mine.request_classification([], floor=None) == "internal"


def test_missing_label_is_internal_and_unknown_is_restricted():
    assert mine.request_classification([{"title": "no label"}], floor="public") == "internal"
    assert mine.request_classification([{"classification": None}], floor="public") == "internal"
    assert mine.request_classification([{"classification": ""}], floor="public") == "internal"
    assert mine.request_classification([{"classification": "secret"}]) == "restricted"


def test_case_and_spaces():
    assert mine.request_classification([{"classification": " Confidential "}]) == "confidential"
    assert mine.request_classification([{"classification": "PUBLIC"}], floor="public") == "public"

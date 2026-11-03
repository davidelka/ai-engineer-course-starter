"""Exercise 2: the router's decision rule (threshold -> clarifying question), then the real router."""
import pytest

import mine
from multikit.router import DEFAULT_QUESTION, RouteDecision


def dec(routes, conf, q=None):
    return RouteDecision(reason="r", routes=routes, confidence=conf, clarifying_question=q)


def test_routes_one_target_by_default():
    c = mine.decide_route(dec(["it_access", "oncall"], 0.9))
    assert c.action == "route" and c.targets == ["it_access"] and c.question is None and c.why


def test_max_targets_keeps_order_and_dedups():
    c = mine.decide_route(dec(["oncall", "oncall", "hr", "it_access"], 0.8), max_targets=2)
    assert c.targets == ["oncall", "hr"]


def test_low_confidence_asks_with_model_question():
    c = mine.decide_route(dec(["hr"], 0.4, "Which policy do you mean?"))
    assert c.action == "clarify" and c.targets == [] and c.question == "Which policy do you mean?" and c.why


def test_threshold_is_inclusive():
    assert mine.decide_route(dec(["hr"], 0.6), threshold=0.6).action == "route"
    assert mine.decide_route(dec(["hr"], 0.59), threshold=0.6).action == "clarify"


def test_empty_routes_ask_even_when_confident():
    c = mine.decide_route(dec([], 0.95))
    assert c.action == "clarify" and c.question == DEFAULT_QUESTION


def test_blank_question_falls_back_to_default():
    assert mine.decide_route(dec([], 0.1, "   ")).question == DEFAULT_QUESTION


def test_disallowed_domains_are_dropped():
    c = mine.decide_route(dec(["oncall", "hr"], 0.9), allowed=("hr", "it_access"))
    assert c.targets == ["hr"]
    c = mine.decide_route(dec(["oncall"], 0.9), allowed=("hr",))
    assert c.action == "clarify"


def test_router_with_your_rule_on_the_task_set():
    from agentkit import load_tasks
    from multikit import run_set
    from _lab import TASKS
    ts = {t["id"]: t for t in load_tasks(TASKS)}
    rs = run_set("router2", [ts["t01"], ts["x03"], ts["x07"]], decide=mine.decide_route)
    by = {t["id"]: (r, s) for t, r, s in rs}
    assert by["t01"][1]["success"] and by["x03"][1]["success"]
    assert by["x07"][0].info["choice"]["action"] == "clarify"

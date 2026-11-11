"""Milestone 3: route_message, rules first, then a structured-output model, with a safe fallback."""
import json

from _impl import mine
from llmkit.errors import LLMError
from llmkit.types import ChatResult, Usage


def RULES(intent, conf=0.9, matched=("request",)):
    return lambda text: {"intent": intent, "confidence": conf, "matched": list(matched)}


class Model:
    """A model that answers with fixed JSON (the shape IntentDecision expects)."""
    provider = type("P", (), {"name": "anthropic"})()
    model = "fake"

    def __init__(self, decision):
        self.decision, self.calls, self.prompts = decision, 0, []

    def complete(self, req, **kw):
        self.calls += 1
        self.prompts.append(req.messages[-1].content if isinstance(req.messages[-1].content, str) else str(req.messages[-1].content))
        return ChatResult(text=json.dumps(self.decision), stop_reason="end_turn", usage=Usage(10, 5), provider="t", model="t")


class Down(Model):
    def __init__(self):
        super().__init__({})

    def complete(self, req, **kw):
        raise LLMError("boom", kind="overloaded")


def test_rules_decide_when_sure():
    m = Model({"reason": "x", "intent": "data", "confidence": 0.9})
    r = mine.route_message("I need a Figma editor seat", rules=RULES("access_request"), llm=m)
    assert (r.intent, r.confidence, r.source, r.matched) == ("access_request", 0.9, "rules", ["request"])
    assert m.calls == 0 and r.llm is None


def test_always_asks_the_model():
    m = Model({"reason": "counts", "intent": "data", "confidence": 0.8})
    r = mine.route_message("How many?", rules=RULES("knowledge", 0.6, ["default"]), llm=m, llm_mode="always")
    assert (r.intent, r.source, r.reason, r.matched) == ("data", "llm", "counts", ["default"])
    assert r.llm["intent"] == "data" and r.llm["confidence"] == 0.8 and r.llm["input_tokens"] == 10
    assert "<message>\nHow many?\n</message>" in m.prompts[0]


def test_unsure_rules_go_to_the_model():
    m = Model({"reason": "wish verb", "intent": "access_request", "confidence": 0.7})
    r = mine.route_message("figma editor for dana please", rules=RULES(None, 0.4, ["access_word"]), llm=m)
    assert (r.intent, r.confidence, r.source) == ("access_request", 0.7, "llm") and m.calls == 1


def test_no_model_or_never_is_a_safe_default():
    for kw in ({"llm": None}, {"llm": Model({}), "llm_mode": "never"}):
        r = mine.route_message("figma editor for dana please", rules=RULES(None, 0.4, ["access_word"]), **kw)
        assert (r.intent, r.confidence, r.source) == ("knowledge", 0.4, "fallback")
        assert r.reason == "rules unsure, no model: safe default"
    r = mine.route_message("x", rules=RULES("data", 0.8), llm=None, llm_mode="never")
    assert (r.intent, r.source) == ("data", "rules")


def test_model_failure_is_a_safe_default():
    r = mine.route_message("figma editor for dana please", rules=RULES(None, 0.4, ["access_word"]), llm=Down())
    assert (r.intent, r.confidence, r.source, r.llm) == ("knowledge", 0.0, "fallback", None)
    assert r.reason == "router model failed (LLMError): safe default"


def test_unsure_model_is_a_safe_default():
    m = Model({"reason": "?", "intent": "access_request", "confidence": 0.3})
    r = mine.route_message("hmm", rules=RULES(None, 0.4, []), llm=m)
    assert (r.intent, r.confidence, r.source) == ("knowledge", 0.3, "fallback")
    assert r.reason == "model unsure (access_request, 0.30): safe default" and r.llm["intent"] == "access_request"

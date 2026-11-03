"""Exercise 5: normalize OpenAI stream events. Same stream, both formats, same result."""

import pytest

from llmkit import LLM, LLMError, RetryPolicy
from llmkit.providers.base import StreamEnd, TextDelta
from llmkit.providers.openai import OpenAIProvider
import mine


def test_text_delta():
    item = mine.openai_event_to_item("response.output_text.delta", {"delta": "Hel"})
    assert isinstance(item, TextDelta) and item.text == "Hel"


def test_bookkeeping_events_are_ignored():
    for t in ["response.created", "response.in_progress", "response.output_item.added",
              "response.content_part.added", "response.output_text.done"]:
        assert mine.openai_event_to_item(t, {}) is None


def test_completed_carries_usage_and_stop():
    data = {"response": {"id": "resp_1", "status": "completed",
                         "usage": {"input_tokens": 10, "output_tokens": 7,
                                   "output_tokens_details": {"reasoning_tokens": 3}}}}
    item = mine.openai_event_to_item("response.completed", data)
    assert isinstance(item, StreamEnd)
    assert item.raw_stop == "completed" and item.usage.output_tokens == 7 and item.usage.thinking_tokens == 3


def test_incomplete_reports_max_tokens():
    data = {"response": {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"},
                         "usage": {"input_tokens": 1, "output_tokens": 1}}}
    assert mine.openai_event_to_item("response.incomplete", data).raw_stop == "max_output_tokens"


@pytest.mark.parametrize("event,data", [
    ("error", {"code": "server_error", "message": "boom"}),
    ("response.failed", {"response": {"error": {"code": "server_error", "message": "boom"}}}),
])
def test_failures_raise(event, data):
    with pytest.raises(LLMError):
        mine.openai_event_to_item(event, data)


def test_same_stream_same_result_in_both_formats(mock, monkeypatch):
    server, url = mock
    monkeypatch.setattr(OpenAIProvider, "event_mapper", staticmethod(mine.openai_event_to_item))
    a = LLM("anthropic:mock-model", api_key="t", base_url=url, retry=RetryPolicy.none())
    o = LLM("openai:mock-model", api_key="t", base_url=url, retry=RetryPolicy.none())
    ra = [e for e in a.stream("Same question") if e.type == "done"][0].result
    ro = [e for e in o.stream("Same question") if e.type == "done"][0].result
    assert ra.text == ro.text
    assert ra.stop_reason == ro.stop_reason == "end"
    assert ra.usage.output_tokens == ro.usage.output_tokens


def test_broken_openai_stream_is_detected(mock, monkeypatch):
    server, url = mock
    server.state.cfg.error_after = 2
    monkeypatch.setattr(OpenAIProvider, "event_mapper", staticmethod(mine.openai_event_to_item))
    o = LLM("openai:mock-model", api_key="t", base_url=url, retry=RetryPolicy.none())
    with pytest.raises(LLMError) as exc:
        list(o.stream("A long question so the answer has many words"))
    assert exc.value.partial_text

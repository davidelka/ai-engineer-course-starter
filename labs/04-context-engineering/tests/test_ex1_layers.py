"""Exercise 1: break a request into context layers and find the cached prefix."""

import json

from conftest import words
from mine import layer_report

TOOL = {"name": "search_policies", "description": "Search Acme policies by keyword",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}}}


def report(body):
    out = layer_report(body, words)
    assert [x.name for x in out] == ["tools", "system", "history", "retrieved", "user_turn"]
    return {x.name: x for x in out}


def test_plain_request_has_five_layers_and_nothing_cached():
    r = report({"system": "be very brief", "messages": [{"role": "user", "content": "how many days off"}]})
    assert (r["system"].tokens, r["user_turn"].tokens) == (3, 4)
    assert r["tools"].tokens == r["history"].tokens == r["retrieved"].tokens == 0
    assert all(x.cached_tokens == 0 for x in r.values())


def test_tools_are_counted_as_json_without_cache_control():
    tool = dict(TOOL, cache_control={"type": "ephemeral"})
    r = report({"tools": [tool, TOOL], "messages": [{"role": "user", "content": "q"}]})
    one = words(json.dumps(TOOL, ensure_ascii=False))
    assert r["tools"].tokens == 2 * one
    assert r["tools"].cached_tokens == one  # the breakpoint is on the first tool only


def test_history_and_retrieved_documents():
    body = {"system": [{"type": "text", "text": "rules here"}],
            "messages": [
                {"role": "user", "content": "<documents>old doc words</documents> first q"},
                {"role": "assistant", "content": "first answer"},
                {"role": "user", "content": "<documents>doc one</documents>\nand <documents>doc two two</documents> now what?"}]}
    r = report(body)
    assert r["history"].tokens == 3 + 2 + 2  # documents in OLD turns are history
    assert r["retrieved"].tokens == words("<documents>doc one</documents>") + words("<documents>doc two two</documents>")
    assert r["user_turn"].tokens == words("\nand  now what?")
    assert r["system"].tokens == 2


def test_breakpoint_on_system_caches_tools_and_system():
    body = {"tools": [TOOL],
            "system": [{"type": "text", "text": "a b c"}, {"type": "text", "text": "d e", "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": "x y"}, {"role": "assistant", "content": "z"},
                         {"role": "user", "content": "final words"}]}
    r = report(body)
    assert r["tools"].cached_tokens == r["tools"].tokens
    assert r["system"].cached_tokens == 5
    assert r["history"].cached_tokens == 0 and r["user_turn"].cached_tokens == 0


def test_breakpoint_inside_history_and_in_last_message():
    body = {"system": "s1 s2",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "h1 h2"},
                                                      {"type": "text", "text": "h3", "cache_control": {"type": "ephemeral"}}]},
                         {"role": "assistant", "content": "a1 a2"},
                         {"role": "user", "content": "now"}]}
    r = report(body)
    assert r["system"].cached_tokens == 2 and r["history"].cached_tokens == 3 and r["history"].tokens == 5
    body["messages"][2]["content"] = [
        {"type": "text", "text": "<documents>big doc here</documents>", "cache_control": {"type": "ephemeral", "ttl": "1h"}},
        {"type": "text", "text": "question words"}]
    r = report(body)
    assert r["retrieved"].cached_tokens == r["retrieved"].tokens == 3
    assert r["user_turn"].tokens == 2 and r["user_turn"].cached_tokens == 0


def test_top_level_cache_control_caches_everything():
    body = {"system": "s1 s2", "cache_control": {"type": "ephemeral"},
            "messages": [{"role": "user", "content": "q1 q2 q3"}]}
    r = report(body)
    assert r["system"].cached_tokens == 2 and r["user_turn"].cached_tokens == 3

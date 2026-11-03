"""Lesson 4: prompt caching in llmkit and mockllm, and the ctxkit helpers. Offline and free."""

import time

import pytest

from llmkit import LLM, Block, ChatRequest, Message, RetryPolicy, cost_usd
from llmkit.providers.anthropic import AnthropicProvider
from llmkit.providers.gemini import GeminiProvider, usage_from as gemini_usage
from llmkit.providers.openai import OpenAIProvider, usage_from as openai_usage
from llmkit.types import Usage
from mockllm import MockConfig, start_in_thread

BIG = "Acme handbook line about offices, teams and travel rules. " * 300  # ~4K mock tokens


@pytest.fixture(scope="module")
def _server():
    server, url = start_in_thread(MockConfig())
    yield server, url
    server.shutdown()


@pytest.fixture
def mock(_server):
    server, url = _server
    server.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    server.state.reset()
    return server, url


def llm(url, provider="anthropic"):
    return LLM(f"{provider}:mock-model", api_key="test", base_url=url, retry=RetryPolicy(sleep=lambda s: None))


def cached_req(question, ttl="5m"):
    return ChatRequest(messages=[Message("user", question)],
                       system=[Block("You are Acme's HR assistant."), Block(BIG, cache=ttl)], max_tokens=50)


# ---------------------------------------------------------------- request bodies
def test_plain_strings_keep_the_old_wire_format():
    body = AnthropicProvider().build(ChatRequest.from_prompt("hi", system="be brief"), "m", "k", False).body
    assert body["system"] == "be brief"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert "cache_control" not in body


def test_blocks_become_cache_control_on_anthropic():
    req = ChatRequest(messages=[Message("user", [Block("docs", cache="1h"), Block("question")])],
                      system=[Block("rules"), Block("policies", cache="5m")], cache="5m")
    body = AnthropicProvider().build(req, "m", "k", False).body
    assert body["system"] == [{"type": "text", "text": "rules"},
                              {"type": "text", "text": "policies", "cache_control": {"type": "ephemeral"}}]
    assert body["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert "cache_control" not in body["messages"][0]["content"][1]
    assert body["cache_control"] == {"type": "ephemeral"}  # top-level = automatic caching


def test_other_providers_get_joined_text_and_cache_key():
    req = ChatRequest(messages=[Message("user", [Block("a", cache="5m"), Block("b")])],
                      system=[Block("x"), Block("y", cache="5m")], cache_key="hr-bot")
    o = OpenAIProvider().build(req, "m", "k", False).body
    assert o["instructions"] == "x\n\ny" and o["input"][0]["content"] == "a\n\nb"
    assert o["prompt_cache_key"] == "hr-bot"
    g = GeminiProvider().build(req, "m", "k", False).body
    assert g["systemInstruction"]["parts"][0]["text"] == "x\n\ny"
    assert g["contents"][0]["parts"][0]["text"] == "a\n\nb"


# ---------------------------------------------------------------- usage parsing
def test_anthropic_usage_adds_the_three_parts():
    u = AnthropicProvider._usage({"input_tokens": 50, "output_tokens": 7, "cache_read_input_tokens": 1000,
                                  "cache_creation_input_tokens": 300,
                                  "cache_creation": {"ephemeral_5m_input_tokens": 100, "ephemeral_1h_input_tokens": 200}})
    assert (u.input_tokens, u.cached_input_tokens, u.cache_creation_tokens, u.cache_creation_1h_tokens) == (1350, 1000, 300, 200)
    assert u.uncached_input_tokens == 50


def test_openai_and_gemini_usage():
    u = openai_usage({"input_tokens": 12000, "output_tokens": 5,
                      "input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000}})
    assert (u.cached_input_tokens, u.cache_creation_tokens, u.uncached_input_tokens) == (4000, 7000, 1000)
    g = gemini_usage({"promptTokenCount": 5000, "candidatesTokenCount": 3, "cachedContentTokenCount": 4096})
    assert g.input_tokens == 5000 and g.cached_input_tokens == 4096


def test_cost_prices_reads_and_both_write_ttls():
    # Haiku 5.5: input 0.10, read 0.01, 5m write 0.125, 1h write 0.20, output 0.50 (per 1M)
    u = Usage(input_tokens=1_000_000 + 2_000_000 + 3_000_000 + 4_000_000, output_tokens=0,
              cached_input_tokens=2_000_000, cache_creation_tokens=7_000_000, cache_creation_1h_tokens=4_000_000)
    # still under the long-context tier? no: 10M > 100K, so x5. Check with the tier off:
    prices = {"m": {"input": 0.10, "output": 0.50, "cached_input": 0.01, "cache_write": 0.125, "cache_write_1h": 0.20}}
    assert cost_usd("m", u, prices) == pytest.approx(0.10 + 0.02 + 3 * 0.125 + 4 * 0.20)
    assert cost_usd("claude-haiku-5-5", u) == pytest.approx(5 * (0.10 + 0.02 + 3 * 0.125 + 4 * 0.20))


def test_long_context_tier_counts_the_whole_prompt_once():
    # 60K uncached + 50K cached = 110K prompt tokens: above 100K, so x5 (no double counting)
    u = Usage(input_tokens=110_000, cached_input_tokens=50_000)
    assert cost_usd("claude-haiku-5-5", u) == pytest.approx(5 * (60_000 * 0.10 + 50_000 * 0.01) / 1e6)
    u2 = Usage(input_tokens=90_000, cached_input_tokens=50_000)
    assert cost_usd("claude-haiku-5-5", u2) == pytest.approx((40_000 * 0.10 + 50_000 * 0.01) / 1e6)


# ---------------------------------------------------------------- mock cache simulation
@pytest.mark.parametrize("stream", [False, True])
def test_mock_anthropic_write_then_read(mock, stream):
    server, url = mock
    c = llm(url)
    r1 = c.complete(cached_req("first question"), stream=stream)
    r2 = c.complete(cached_req("a different question"), stream=stream)
    assert r1.usage.cache_creation_tokens > 3000 and r1.usage.cached_input_tokens == 0
    assert r2.usage.cached_input_tokens == r1.usage.cache_creation_tokens and r2.usage.cache_creation_tokens == 0
    assert r2.cost_usd < r1.cost_usd
    assert server.state.stats()["cache_reads"] == 1


def test_mock_no_breakpoint_no_cache(mock):
    server, url = mock
    req = ChatRequest(messages=[Message("user", "q")], system="rules\n" + BIG, max_tokens=50)
    c = llm(url)
    c.complete(req)
    r = c.complete(req)
    assert r.usage.cached_input_tokens == 0 and r.usage.cache_creation_tokens == 0


def test_mock_changed_prefix_misses(mock):
    server, url = mock
    c = llm(url)
    c.complete(cached_req("q1"))
    req = cached_req("q2")
    req.system[0] = Block("Today is 2026-11-01. You are Acme's HR assistant.")  # a date before the docs
    r = c.complete(req)
    assert r.usage.cached_input_tokens == 0 and r.usage.cache_creation_tokens > 0


def test_mock_below_minimum_is_silently_not_cached(mock):
    server, url = mock
    req = ChatRequest(messages=[Message("user", "q")], system=[Block("short rules", cache="5m")], max_tokens=50)
    r = llm(url).complete(req)
    assert r.usage.cache_creation_tokens == 0


def test_mock_ttl_expiry_and_1h(mock):
    server, url = mock
    server.state.cfg.cache_ttl_scale = 0.001  # 5m -> 0.3s, 1h -> 3.6s
    c = llm(url)
    c.complete(cached_req("q1"))
    time.sleep(0.4)
    r = c.complete(cached_req("q2"))
    assert r.usage.cached_input_tokens == 0, "5-minute entry should have expired"
    time.sleep(0.4)  # let q2's 5-minute entry expire too
    r1 = c.complete(cached_req("q3", ttl="1h"))
    assert r1.usage.cache_creation_1h_tokens == r1.usage.cache_creation_tokens > 0
    time.sleep(0.4)
    assert c.complete(cached_req("q4", ttl="1h")).usage.cached_input_tokens > 0


def test_mock_automatic_caching_follows_the_conversation(mock):
    server, url = mock
    c = llm(url)
    msgs = [Message("user", BIG + " first question")]
    r1 = c.complete(ChatRequest(messages=msgs, cache="5m", max_tokens=50))
    msgs = msgs + [Message("assistant", "answer one"), Message("user", "second question")]
    r2 = c.complete(ChatRequest(messages=msgs, cache="5m", max_tokens=50))
    assert r1.usage.cache_creation_tokens > 0
    assert r2.usage.cached_input_tokens == r1.usage.cache_creation_tokens  # found via the lookback
    assert r2.usage.cache_creation_tokens > 0  # and the breakpoint moved forward


def test_mock_rejects_too_many_breakpoints(mock):
    from llmkit import LLMError
    server, url = mock
    req = ChatRequest(messages=[Message("user", [Block(f"b{i}", cache="5m") for i in range(5)])], max_tokens=10)
    with pytest.raises(LLMError) as e:
        llm(url).complete(req)
    assert e.value.status == 400


@pytest.mark.parametrize("provider,minimum", [("openai", 1024), ("gemini", 4096)])
def test_mock_automatic_prefix_caching(mock, provider, minimum):
    server, url = mock
    c = llm(url, provider)
    big = BIG * 2  # ~8K mock tokens
    c.complete(ChatRequest(messages=[Message("user", "q1")], system=big, max_tokens=20))
    r = c.complete(ChatRequest(messages=[Message("user", "q2")], system=big, max_tokens=20))
    assert r.usage.cached_input_tokens >= minimum
    if provider == "openai":
        assert r.usage.cached_input_tokens % 128 == 0
    short = c.complete(ChatRequest(messages=[Message("user", "q3")], system="tiny", max_tokens=20))
    assert short.usage.cached_input_tokens == 0


def test_mock_prefill_delay_rewards_hits(mock):
    server, url = mock
    server.state.cfg.prefill_tps = 40_000  # ~4K tokens -> ~0.1s when uncached
    c = llm(url)
    r1 = c.complete(cached_req("q1"))
    r2 = c.complete(cached_req("q2"))
    assert r2.latency_s < r1.latency_s


def test_mock_parallel_requests_cannot_hit_an_entry_still_being_written(mock):
    from concurrent.futures import ThreadPoolExecutor
    server, url = mock
    server.state.cfg.prefill_tps = 20_000  # ~0.2s prefill
    c = llm(url)
    with ThreadPoolExecutor(3) as pool:
        rs = list(pool.map(lambda i: c.complete(cached_req(f"q{i}")), range(3)))
    assert all(r.usage.cached_input_tokens == 0 for r in rs)
    assert c.complete(cached_req("after")).usage.cached_input_tokens > 0


# ---------------------------------------------------------------- ctxkit
def words(t):
    return len(t.split())


def test_layer_report_reference():
    from ctxkit import layer_report
    body = {
        "tools": [{"name": "lookup", "description": "find a doc", "input_schema": {"type": "object"}}],
        "system": [{"type": "text", "text": "one two three"},
                   {"type": "text", "text": "four five", "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": "old question here"},
                     {"role": "assistant", "content": "old answer"},
                     {"role": "user", "content": "<documents>doc a b</documents> what now?"}],
    }
    r = {x.name: x for x in layer_report(body, words)}
    assert [x for x in r] == ["tools", "system", "history", "retrieved", "user_turn"]
    assert r["system"].tokens == 5 and r["system"].cached_tokens == 5
    assert r["history"].tokens == 5 and r["history"].cached_tokens == 0
    assert r["retrieved"].tokens == 3 and r["user_turn"].tokens == 2
    assert r["tools"].cached_tokens == r["tools"].tokens > 0
    body["cache_control"] = {"type": "ephemeral"}
    r = {x.name: x for x in layer_report(body, words)}
    assert r["user_turn"].cached_tokens == 2  # automatic: the whole request is the prefix


def test_compact_and_truncate_reference():
    from ctxkit import compact, truncate
    msgs = []
    for i in range(6):
        msgs += [Message("user", f"user {i} " + "w " * 8), Message("assistant", f"assistant {i} " + "w " * 8)]
    msgs.append(Message("user", "final question"))
    t = truncate(msgs, 40, words)
    assert t[0].role == "user" and t[-1].text == "final question" and sum(words(m.text) for m in t) <= 40
    calls = []
    out = compact(msgs, 60, words, lambda old: calls.append(len(old)) or "S", keep_last=4)
    assert out[0].text.startswith("<conversation_summary>\nS\n</conversation_summary>")
    assert out[-1].text == "final question" and len(out) == 5 and calls == [8]
    assert compact(msgs[:3], 1000, words, lambda o: "x") == msgs[:3]


def test_cache_model():
    from ctxkit import CacheScenario, break_even_hit_rate, hit_probability, scenario_cost
    assert break_even_hit_rate(1.0, 1.25, 0.1) == pytest.approx(0.25 / 1.15)
    assert break_even_hit_rate(1.0, 2.0, 0.1) == pytest.approx(1 / 1.9)
    assert break_even_hit_rate(1.0, 1.0, 0.1) == 0.0
    assert hit_probability(12, 300) == pytest.approx(1 - 2.718281828 ** -1, rel=1e-6)
    s = scenario_cost(CacheScenario(calls_per_hour=600, prefix_tokens=10_000, suffix_tokens=200, output_tokens=200))
    assert s["hit_rate"] > 0.99 and s["saving"] > 0.7


def test_haystack_places_needle_and_distractors():
    from ctxkit.haystack import NEEDLES, build_haystack, is_correct
    sections = [f"## S{i}\nline a\nline b\nline c" for i in range(10)]
    n = NEEDLES[0]
    xml, tokens = build_haystack(sections, 60, n, 0.0, n_distractors=2, count=words)
    docs = xml.split("<document ")
    assert n.sentence in docs[1] and tokens > 0
    assert sum(d in xml for d in n.distractors) == 2
    xml_end, _ = build_haystack(sections, 60, n, 1.0, count=words)
    assert n.sentence in xml_end.split("<document ")[-1]
    assert is_correct("The code is 4-8-1-5-2.", "48152") and not is_correct("7-7-2-0-9", "48152")


def test_layout_reference_is_cache_friendly():
    from ctxkit.layout import build_hr_request, naive_hr_request
    a = build_hr_request("POLICY", "q1?", employee="Dana", today="2026-11-01")
    b = build_hr_request("POLICY", "q2?", employee="Omer", today="2026-11-02")
    assert a.system == b.system and a.system[-1].cache == "5m"
    assert "Dana" not in a.system_text and "2026-11-01" not in a.system_text
    n = naive_hr_request("POLICY", "q1?", employee="Dana", today="2026-11-01")
    assert n.system_text.startswith("Today is 2026-11-01")


def test_fake_extractive_llm():
    from ctxkit.fake import ExtractiveLLM, heuristic_summarizer
    f = ExtractiveLLM({"employee id": "A-4471"})
    yes = f.complete(ChatRequest(messages=[Message("user", "My ID is A-4471"), Message("assistant", "ok"),
                                           Message("user", "What is my employee ID?")]))
    no = f.complete(ChatRequest.from_prompt("What is my employee ID?"))
    assert yes.text == "A-4471" and no.text == "I don't know."
    s = heuristic_summarizer([Message("user", "Hello there. My employee ID is A-4471."), Message("assistant", "Noted 123.")])
    assert "A-4471" in s and "Noted" not in s

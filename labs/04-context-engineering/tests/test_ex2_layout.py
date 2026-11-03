"""Exercise 2: a cache-friendly HR assistant request (stable prefix, dynamic suffix)."""

from pathlib import Path

from ctxkit.layers import layer_report as reference_layers
from llmkit import LLM, Block, ChatRequest, Message, RetryPolicy
from llmkit.providers.anthropic import AnthropicProvider
from conftest import words
from mine import HR_INSTRUCTIONS, build_hr_request

ROOT = Path(__file__).resolve().parents[3]
POLICIES = (ROOT / "data" / "acme" / "hr_policies.md").read_text(encoding="utf-8")
HANDBOOK = (ROOT / "labs" / "04-context-engineering" / "data" / "acme_handbook.md").read_text(encoding="utf-8")


def build(q="How many vacation days do I get?", employee="Dana Cohen", today="2026-11-01", **kw):
    return build_hr_request(POLICIES, q, employee=employee, today=today, **kw)


def test_system_is_instructions_then_documents():
    req = build()
    assert isinstance(req, ChatRequest) and isinstance(req.system, list) and len(req.system) == 2
    assert all(isinstance(b, Block) for b in req.system)
    assert req.system[0].text == HR_INSTRUCTIONS
    docs = req.system[1].text
    assert docs.startswith("<documents>\n") and docs.endswith("\n</documents>")
    assert POLICIES.strip() in docs
    assert req.max_tokens == 400


def test_one_breakpoint_on_the_last_stable_block():
    req = build(ttl="1h")
    assert [b.cache for b in req.system] == [None, "1h"]
    assert isinstance(req.messages[-1].content, str)
    assert build().system[-1].cache == "5m"


def test_nothing_dynamic_in_the_prefix():
    a = build("q one?", employee="Dana Cohen", today="2026-11-01")
    b = build("a totally different question?", employee="Karim Haddad", today="2027-02-14")
    assert a.system == b.system, "the system prompt must be byte-identical across calls"
    for name in ("Dana Cohen", "2026-11-01"):
        assert name not in a.system_text


def test_user_turn_has_context_first_and_question_last():
    req = build("Can I carry days over?", employee="Dana Cohen", today="2026-11-01")
    last = req.messages[-1]
    assert last.role == "user"
    t = last.text
    assert t.index("<context>") < t.index("employee: Dana Cohen") < t.index("today: 2026-11-01") < t.index("</context>")
    assert t.index("</context>") < t.index("<question>")
    assert t.rstrip().endswith("<question>\nCan I carry days over?\n</question>")


def test_history_is_kept_before_the_new_turn():
    hist = [Message("user", "hi"), Message("assistant", "hello, how can I help?")]
    req = build(history=hist)
    assert req.messages[:2] == hist and len(req.messages) == 3
    assert build(history=None).messages[0].role == "user"


def test_wire_body_and_layers():
    body = AnthropicProvider().build(build(), "claude-haiku-5-5", "k", False).body
    assert "cache_control" in body["system"][1] and "cache_control" not in body["system"][0]
    r = {x.name: x for x in reference_layers(body, words)}
    assert r["system"].cached_tokens == r["system"].tokens > 0
    assert r["user_turn"].cached_tokens == 0


def test_second_call_hits_the_cache_on_the_mock(mock):
    server, url = mock
    llm = LLM("anthropic:mock-model", api_key="t", base_url=url, retry=RetryPolicy(sleep=lambda s: None))
    big = POLICIES + "\n\n" + HANDBOOK
    r1 = llm.complete(build_hr_request(big, "q1?", employee="A", today="2026-11-01"))
    r2 = llm.complete(build_hr_request(big, "q2?", employee="B", today="2026-11-02"))
    assert r1.usage.cache_creation_tokens > 5000
    assert r2.usage.cached_input_tokens == r1.usage.cache_creation_tokens

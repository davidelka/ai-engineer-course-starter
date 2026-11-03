"""Which model answers each kind of call, per MODE. Three purposes, three factories:

    answer   the knowledge answer (acmeqa's prompt: <sources> + <question>)
    flow     the workflow's intake extraction and risk summary (flowkit's prompts)
    router   the intent router's structured-output stage

    MODE      answer                         flow                 router
    offline   acmeqa OfflineAnswerer         flowkit FakeLLM      FakeRouterLLM
    mock      llmkit -> mockllm (HTTP)       flowkit FakeLLM      FakeRouterLLM
    live      Claude Haiku 5.5               Claude Haiku 5.5     Claude Haiku 5.5
    sim       ObedientChat (guardkit sim)    flowkit FakeLLM      FakeRouterLLM

None of the offline stand-ins is a language model; they exist so that every path, the evaluation
and the tests run for free. The numbers they produce measure the plumbing, the retrieval, the
policy and the guards, not model quality: that is measured live (milestone 10).

OfflineUpstream is the one fake "provider" behind the in-process gateway: it reads the system prompt
to see which purpose a call has and hands it to the right stand-in, so LLM_PATH=gateway also runs
offline end to end.
"""

from __future__ import annotations

import html
import re
from types import SimpleNamespace
from typing import Any, Iterator

from llmkit.types import ChatRequest, ChatResult, StreamEvent, Usage, content_text

from .config import BrainSettings


def _fake_stream(result: ChatResult, chunk_words: int = 3) -> Iterator[StreamEvent]:
    words = result.text.split(" ")
    for i in range(0, len(words), chunk_words):
        yield StreamEvent("text", " ".join(words[i:i + chunk_words]) + (" " if i + chunk_words < len(words) else ""))
    yield StreamEvent("done", result=result)


# ---------------------------------------------------------------- the obedient simulation (security eval)
_SRC = re.compile(r'<source\b([^>]*)>\n(.*?)\n</source>', re.S)
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_UNTRUSTED = re.compile(r"<<untrusted id=\S+ nonce=(\w+)>>\n?(.*?)\n?<</untrusted nonce=\1>>", re.S)


def to_guardkit_prompt(user: str) -> str:
    """acmeqa's user message (maybe spotlighted by GuardedLLM) -> the layout guardkit's simulated
    model parses: spotlighted sources stay <<untrusted ...>> regions (with the doc id), plain sources
    become 'Document [id] title:' blocks, and the question goes last after 'Question:'."""
    blocks = []
    for m in _SRC.finditer(user):
        attrs = dict(_ATTR.findall(m.group(1)))
        doc = attrs.get("doc", attrs.get("id", "?"))
        body = m.group(2)
        u = _UNTRUSTED.search(body)
        if u:
            blocks.append(f"<<untrusted id={doc} nonce={u.group(1)}>>\n{html.unescape(u.group(2))}\n"
                          f"<</untrusted nonce={u.group(1)}>>")
        else:
            blocks.append(f"Document [{doc}] {html.unescape(attrs.get('title', ''))}:\n{html.unescape(body)}")
    q = re.search(r"<question>(.*?)</question>", user, re.S)
    question = html.unescape(q.group(1)) if q else user
    return ("\n\n".join(blocks) or "(no documents found)") + f"\n\nQuestion: {question}"


class ObedientChat:
    """guardkit's ObedientModel (a SIMULATION of a naive model that follows instructions found anywhere
    in its context, with lower odds inside spotlight markers or under an instruction hierarchy) behind
    llmkit's complete()/stream() surface. Deterministic, free. For the security evaluation only."""

    model = "obedient-sim"

    def __init__(self):
        from guardkit.models import ObedientModel
        self.inner = ObedientModel()
        self.provider = SimpleNamespace(name="sim")

    def complete(self, req: ChatRequest, **_: Any) -> ChatResult:
        user = content_text(req.messages[-1].content)
        reply = self.inner.generate(req.system_text, to_guardkit_prompt(user))
        return ChatResult(text=reply.text, stop_reason="end_turn", usage=Usage(input_tokens=len(user) // 4 + 1,
                          output_tokens=len(reply.text) // 4 + 1), provider="sim", model=self.model, cost_usd=0.0)

    def stream(self, req: ChatRequest, **kw: Any) -> Iterator[StreamEvent]:
        yield from _fake_stream(self.complete(req, **kw))


# ---------------------------------------------------------------- one fake provider for the gateway
class OfflineUpstream:
    """What the in-process gateway calls when every deployment is offline. Dispatch by prompt."""

    model = "offline-upstream"

    def __init__(self, answer: Any = None):
        from acmeqa.answer import OfflineAnswerer
        from flowkit import FakeLLM
        from .router import FakeRouterLLM
        self.answer = answer or OfflineAnswerer()
        self.flow = FakeLLM()
        self.router = FakeRouterLLM()
        self.provider = SimpleNamespace(name="anthropic")

    def pick(self, req: ChatRequest) -> Any:
        sys_text = req.system_text
        if "Acme Knowledge Assistant" in sys_text:
            return self.answer
        if "You route messages" in sys_text:
            return self.router
        return self.flow

    def complete(self, req: ChatRequest, **kw: Any) -> ChatResult:
        target = self.pick(req)
        if target is self.flow and req.response_schema is None and "<request>" in content_text(req.messages[-1].content):
            # the gateway turned native structured output into prompt mode; FakeLLM keys on response_schema
            from dataclasses import replace
            req = replace(req, response_schema={"type": "object"})
        r = target.complete(req)
        return r


# ---------------------------------------------------------------- factories
def _live(s: BrainSettings):
    from llmkit import LLM, RetryPolicy
    return LLM(s.llm_model, retry=RetryPolicy(max_attempts=3))


def answer_llm(s: BrainSettings) -> Any:
    if s.mode == "live":
        return _live(s)
    if s.mode == "mock":
        from llmkit import LLM, RetryPolicy
        return LLM("anthropic:claude-haiku-5-5", api_key="mock", base_url=s.mock_url, retry=RetryPolicy(max_attempts=3))
    if s.mode == "sim":
        return ObedientChat()
    from acmeqa.answer import OfflineAnswerer
    return OfflineAnswerer()


def flow_llm(s: BrainSettings) -> Any:
    if s.mode == "live":
        return _live(s)
    from flowkit import FakeLLM
    return FakeLLM()


def router_llm(s: BrainSettings) -> Any:
    if s.mode == "live":
        return _live(s)
    from .router import FakeRouterLLM
    return FakeRouterLLM()

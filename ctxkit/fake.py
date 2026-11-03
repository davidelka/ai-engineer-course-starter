"""Offline stand-ins, so the haystack and compaction labs run for free.

ExtractiveLLM is NOT a language model. It answers a question only if the exact fact it
is told to look for is present somewhere in the prompt, and says "I don't know" otherwise.
So offline runs measure one thing honestly: whether the information is still IN the
context (after truncation or compaction, or wherever it was placed). They cannot show
"lost in the middle": a string search does not care about position. That needs a real
model, which is what the live runs are for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from llmkit import ChatRequest, ChatResult, Message, Usage, content_text

from .tokens import count_tokens


@dataclass
class ExtractiveLLM:
    """facts: {question substring -> answer string}. If the last user message contains a key
    and the answer string appears anywhere in the prompt, reply with the answer string."""

    facts: dict[str, str] = field(default_factory=dict)
    model: str = "fake-extractive"

    def complete(self, req: ChatRequest, **_) -> ChatResult:
        prompt = content_text(req.system) + "\n" + "\n".join(m.text for m in req.messages)
        question = req.messages[-1].text if req.messages else ""
        answer = "I don't know."
        for key, value in self.facts.items():
            if key.lower() in question.lower() and value.lower() in prompt.lower():
                answer = value
                break
        usage = Usage(input_tokens=count_tokens(prompt), output_tokens=count_tokens(answer))
        return ChatResult(text=answer, stop_reason="end", usage=usage, provider="fake",
                          model=self.model, cost_usd=0.0)


SENT_RE = re.compile(r"(?<=[.!?])\s+")


def heuristic_summarizer(messages: list[Message]) -> str:
    """A crude offline summarizer: keeps the employee's sentences that contain a digit or
    talk about themselves ("my", "I'm", "I am", "I have", "I live"), and nothing the
    assistant said. Real summaries come from llm_summarizer."""
    keep = []
    for m in messages:
        if m.role != "user":
            continue
        text = m.text
        if "<conversation_summary>" in text:  # an earlier summary: keep its lines
            inner = text.split("<conversation_summary>", 1)[1].split("</conversation_summary>", 1)[0]
            keep += [ln.strip("- ").strip() for ln in inner.strip().splitlines() if ln.strip()]
            text = text.split("</conversation_summary>", 1)[1]
        for s in SENT_RE.split(text):
            low = s.lower()
            if any(ch.isdigit() for ch in s) or any(w in low for w in ("my ", "i'm ", "i am ", "i have ", "i live")):
                keep.append(s.strip())
    return "\n".join(f"- {s}" for s in keep)

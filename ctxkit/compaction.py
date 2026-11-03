"""Managing a conversation that outgrows its token budget.

    truncate(messages, budget, count)              sliding window: drop the oldest turns
    compact(messages, budget, count, summarize)    reference for exercise 6: summarize the
                                                   old turns, keep the recent ones verbatim
    llm_summarizer(llm)                            a summarize() that asks a model

Messages are llmkit Message objects. The list always starts with a user message and ends
with the newest user message (the one about to be answered).
"""

from __future__ import annotations

from typing import Callable

from llmkit import ChatRequest, Message

SUMMARY_OPEN = "<conversation_summary>"
SUMMARY_CLOSE = "</conversation_summary>"

SUMMARY_SYSTEM = """You compress a conversation between an employee and Acme's HR assistant so
the assistant can continue it without the original turns.

Keep, exactly as written: names, numbers, dates, IDs, amounts, decisions, preferences
and constraints the employee stated about themselves, and any open question or promise
the assistant made. Drop greetings, repetition and general policy explanations that can
be looked up again. If the conversation starts with an earlier summary, merge it in.
Write short factual bullet lines in English. No preamble."""


def messages_tokens(messages: list[Message], count: Callable[[str], int]) -> int:
    return sum(count(m.text) for m in messages)


def _start_with_user(messages: list[Message]) -> list[Message]:
    i = 0
    while i < len(messages) - 1 and messages[i].role != "user":
        i += 1
    return messages[i:]


def truncate(messages: list[Message], budget: int, count: Callable[[str], int]) -> list[Message]:
    """Drop the oldest messages until the rest fits the budget (or only the last one is left).
    The result always starts with a user message."""
    out = list(messages)
    while len(out) > 1 and messages_tokens(out, count) > budget:
        out = _start_with_user(out[1:])
    return out


def compact(messages: list[Message], budget: int, count: Callable[[str], int],
            summarize: Callable[[list[Message]], str], keep_last: int = 4) -> list[Message]:
    if messages_tokens(messages, count) <= budget:
        return list(messages)
    keep = max(1, keep_last)
    result = list(messages)
    while True:
        k = min(keep, len(messages))
        start = len(messages) - k
        if messages[start].role != "user" and start > 0:  # the kept part must start with user
            start -= 1
        old, recent = messages[:start], messages[start:]
        if old:
            summary = summarize(old)
            first = recent[0]
            merged = Message("user", f"{SUMMARY_OPEN}\n{summary}\n{SUMMARY_CLOSE}\n\n{first.text}")
            result = [merged] + list(recent[1:])
        else:
            result = list(recent)
        if messages_tokens(result, count) <= budget or keep <= 1:
            return result
        keep = max(1, keep - 2)


def llm_summarizer(llm, max_tokens: int = 600, effort: str = "low") -> Callable[[list[Message]], str]:
    """summarize(messages) -> str, by asking `llm` (an llmkit LLM). Its cost is real: keep
    the returned function's .results list to add it to your totals."""
    results = []

    def summarize(messages: list[Message]) -> str:
        transcript = "\n".join(f"{m.role.upper()}: {m.text}" for m in messages)
        req = ChatRequest.from_prompt(f"<conversation>\n{transcript}\n</conversation>\n\nSummarize it.",
                                      system=SUMMARY_SYSTEM, max_tokens=max_tokens, effort=effort)
        r = llm.complete(req)
        results.append(r)
        return r.text.strip()

    summarize.results = results
    return summarize

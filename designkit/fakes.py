"""Reference fakes (exercise 2): small, fast, deterministic adapters that keep
the same promises as the real ones. A fake is not a mock: it has real behavior
(a dict that really stores, a ranking that really sorts), so a test that uses
it checks the outcome, not which methods were called in which order.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Union

from .domain import rank
from .types import Answer, Completion, ModelRejected, ModelUnavailable, Passage, RetrieverUnavailable


class FakeChatModel:
    """reply: a fixed string, a list of strings (one per call), or a function
    (system, prompt) -> str. With no reply, it answers by citing the first
    document in the prompt, like a well-behaved model would.
    fail: None, "unavailable" or "rejected"."""

    def __init__(self, reply: Union[None, str, list[str], Callable[[str, str], str]] = None,
                 *, fail: Optional[str] = None, name: str = "fake:chat"):
        if fail not in (None, "unavailable", "rejected"):
            raise ValueError("fail must be None, 'unavailable' or 'rejected'")
        self.reply = reply
        self.fail = fail
        self.name = name
        self.calls: list[tuple[str, str, int]] = []

    def complete(self, system: str, prompt: str, *, max_tokens: int = 512) -> Completion:
        self.calls.append((system, prompt, max_tokens))
        if self.fail == "unavailable":
            raise ModelUnavailable("fake: model overloaded")
        if self.fail == "rejected":
            raise ModelRejected("fake: invalid request")
        if callable(self.reply):
            text = self.reply(system, prompt)
        elif isinstance(self.reply, list):
            text = self.reply[min(len(self.calls), len(self.reply)) - 1]
        elif self.reply is not None:
            text = self.reply
        else:
            ids = re.findall(r'<document id="([^"]+)"', prompt)
            text = f"According to Acme's documents, here is the answer [{ids[0]}]." if ids else "I don't know."
        return Completion(text=text, model=self.name, input_tokens=len(prompt) // 4,
                          output_tokens=max(1, len(text) // 4))


class InMemoryRetriever:
    def __init__(self, passages: list[Passage], *, fail: bool = False):
        self.passages = list(passages)
        self.fail = fail
        self.calls: list[str] = []

    def search(self, query: str, k: int = 4) -> list[Passage]:
        self.calls.append(query)
        if self.fail:
            raise RetrieverUnavailable("fake: search backend down")
        return rank(query, self.passages, k)


class InMemoryAnswerStore:
    def __init__(self):
        self.data: dict[str, Answer] = {}

    def get(self, request_id: str) -> Optional[Answer]:
        return self.data.get(request_id)

    def put(self, answer: Answer) -> bool:
        if answer.request_id in self.data:
            return False
        self.data[answer.request_id] = answer
        return True


class FixedClock:
    def __init__(self, at: Optional[datetime] = None):
        self.at = at or datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.at

    def advance(self, seconds: float) -> None:
        self.at += timedelta(seconds=seconds)


# A tiny Acme corpus for tests: the same facts as data/acme, already split.
SAMPLE_PASSAGES = [
    Passage(doc_id="vacation_policy.md", title="Vacation Policy",
            text="Full-time employees receive 14 paid vacation days in their first year of employment. "
                 "Up to 5 unused days may be carried over to the next calendar year."),
    Passage(doc_id="remote_work_policy.md", title="Remote Work Policy",
            text="Employees may work remotely up to 2 days per week. Tuesday and Wednesday are office days. "
                 "Acme provides a one-time home office allowance of 1,500 NIS."),
    Passage(doc_id="saas_access_policy.md#needs_security", title="SaaS Access Policy: needs_security",
            text="The security team reviews admin rights, production infrastructure, customer data "
                 "and financial systems access requests."),
]

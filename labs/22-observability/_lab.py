"""Shared helpers for the lesson 22 scripts: paths, picking your functions (mine.py) or the
reference ones (obskit) with --reference, and a mock-backed model for offline runs."""

from __future__ import annotations

import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]
RESULTS = LAB / "results"
FIXTURES = LAB / "fixtures"

REFERENCE = {
    "percentile": ("obskit.analyze", "percentile"),
    "summarize": ("obskit.analyze", "summarize"),
    "israeli_id_valid": ("obskit.redact", "israeli_id_valid"),
    "redact_text": ("obskit.redact", "redact_text"),
    "redact_attributes": ("obskit.redact", "redact_attributes"),
    "is_good": ("obskit.slo", "is_good"),
    "burn_rate": ("obskit.slo", "burn_rate"),
    "alerts_at": ("obskit.slo", "alerts_at"),
}


def pick(name: str, reference: bool = False):
    """Return (function, source). Falls back to the reference while yours is still a TODO."""
    import importlib
    mod, attr = REFERENCE[name]
    ref = getattr(importlib.import_module(mod), attr)
    if reference:
        return ref, "reference"
    import mine
    fn = getattr(mine, name)
    warned = []

    def guarded(*a, **kw):
        try:
            return fn(*a, **kw)
        except NotImplementedError:
            if not warned:
                warned.append(1)
                print(f"  (mine.{name} is still a TODO: using the reference for this run)")
            return ref(*a, **kw)
    return guarded, "mine.py"


class MockBacked:
    """A model for offline runs: llmkit LLM -> real HTTP -> mockllm, but the reply text is
    decided here, per request. By default it is ragkit's ExtractiveAnswerer, which answers
    from the <source> blocks of the prompt (deterministic, no reasoning). `script` can force
    a reply for the next call, which is how the forensic generator makes a fallback model
    say something wrong.

    InstrumentedLLM wraps THIS object, so spans see the real llmkit ChatResult: real token
    counts from the mock, real retries, real timeouts, real prompt-cache usage fields."""

    def __init__(self, llm, server):
        from ragkit.fake import ExtractiveAnswerer
        self.llm, self.server = llm, server
        self.answerer = ExtractiveAnswerer()
        self.script: list[str] = []

    model = property(lambda self: self.llm.model)
    provider = property(lambda self: self.llm.provider)
    base_url = property(lambda self: self.llm.base_url)

    @property
    def on_retry(self):
        return self.llm.on_retry

    @on_retry.setter
    def on_retry(self, fn):
        self.llm.on_retry = fn

    def reply_for(self, req) -> str:
        if self.script:
            return self.script.pop(0)
        if "<sources>" not in req.messages[-1].text:
            return "I am not sure."
        return self.answerer.complete(req).text

    def complete(self, req, **kw):
        self.server.state.cfg.reply = self.reply_for(req)
        return self.llm.complete(req, **kw)

    def stream(self, req, **kw):
        self.server.state.cfg.reply = self.reply_for(req)
        return self.llm.stream(req, **kw)


def start_mock(**cfg):
    """An in-process mockllm on a free port. Returns (server, url)."""
    from mockllm import MockConfig, start_in_thread
    return start_in_thread(MockConfig(**cfg))

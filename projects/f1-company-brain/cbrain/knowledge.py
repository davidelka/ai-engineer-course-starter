"""The knowledge path: M1's assistant (acmeqa, imported unchanged) with the guard layers around it.

    k = GuardedKnowledge(settings, answer_llm)
    for ev in k.events("How many vacation days carry over?", role="engineering"):
        ...    # input_guard?, route, data?, sources, guard, token..., answer, done

What M1 already does and is NOT re-implemented here: hybrid retrieval (BM25 + dense, RRF), the ACL
as a `where` before ranking, the version filter, context packing, citations resolved to exact
spans, the refusal protocol, the docs/data router with text-to-SQL, streaming, prompt caching and
a trace per question. M1 runs YOUR M1 functions (projects/m1-knowledge-assistant/mine.py): Company
Brain is built on the knowledge assistant you wrote, so finish M1 first. With --reference (solutions
branch) M1's references run too.

What this module adds, by composition (no M1 file changes):
- the input screen before M1 runs (guards.Screens.question)
- a wrapper around M1's pack_context hook: drops flagged chunks (guards.Screens.filter_hits), sets
  the data classification of the call for the gateway (milestone 7), and, for the security
  evaluation only, injects an attack's extra document or tool result into the candidates
- GuardedLLM around the answer model (hierarchy, canary, spotlighting)
- the output validator on the final answer; STRICT_OUTPUT holds tokens until it passed
"""

from __future__ import annotations

import contextvars
from typing import Any, Iterator, Optional

from ragkit.types import Chunk, Hit

from .config import BrainSettings
from .gateway import CURRENT_CLASSIFICATION
from .guards import REFUSAL_INPUT, GuardedLLM, Screens, output_replacement, validate_output

_EXTRA: contextvars.ContextVar[list] = contextvars.ContextVar("cbrain_extra_hits", default=[])
_SINK: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar("cbrain_guard_sink", default=None)


def m1_settings(s: BrainSettings, *, trace: bool = True):
    from acmeqa.config import Settings
    m1_mode = "live" if s.mode == "live" else "offline"
    kw = dict(mode=m1_mode, reference=s.reference, index_dir=s.index_dir, cache_dir=s.state_dir / "embeddings",
              trace_file=s.traces_path if (trace and s.tracing) else None)
    if s.embedder:
        kw["embedder"] = s.embedder
    elif m1_mode == "live":
        kw["embedder"] = "e5-small"
    else:
        kw["embedder"] = "fake"
    return Settings(**kw)


def attack_hits(inject_doc: Optional[dict], tool_result: Optional[str], role: str) -> list[Hit]:
    """Security evaluation only: an attacker's document (web page, email, poisoned wiki page) and/or
    a tool result, as candidates at the TOP of the ranking. That is the worst case: we assume the
    attacker managed to get retrieved. The ACL still applies to the injected document."""
    from acmeqa.retrieval import doc_visible
    out: list[Hit] = []
    if inject_doc:
        meta = {"title": inject_doc.get("title", inject_doc["id"]), "classification":
                inject_doc.get("classification", "internal"), "department": inject_doc.get("department", ""),
                "origin": inject_doc.get("origin", "web"), "effective_date": "", "language": "en"}
        if doc_visible(role, meta):
            text = inject_doc["text"]
            out.append(Hit(Chunk(id=f"{inject_doc['id']}#0", doc_id=inject_doc["id"], text=text, start=0,
                                 end=len(text), meta=meta), score=99.0))
    if tool_result:
        meta = {"title": "ticket_lookup output", "classification": "internal", "origin": "tool"}
        out.append(Hit(Chunk(id="tool:ticket_lookup#0", doc_id="tool:ticket_lookup", text=tool_result, start=0,
                             end=len(tool_result), meta=meta), score=98.0))
    return out


class GuardedKnowledge:
    def __init__(self, s: BrainSettings, answer_llm: Any, *, data_llm: Any = None, guards: Optional[bool] = None,
                 classify=None, screens: Optional[Screens] = None, tracing: bool = True):
        from acmeqa.assistant import Assistant
        self.s = s
        self.guards = s.guards if guards is None else guards
        self.screens = screens or Screens()
        self.classify = classify
        llm = GuardedLLM(answer_llm) if self.guards else answer_llm
        m1 = m1_settings(s, trace=tracing)
        self.assistant = Assistant(m1, llm=llm, data_llm=data_llm, tracing=tracing and s.tracing)
        self._orig_pack = self.assistant.hooks.pack_context
        self.assistant.hooks.pack_context = self._pack

    # the wrapper around M1's pack_context hook
    def _pack(self, cands: list, **kw: Any) -> list:
        extra = _EXTRA.get()
        if extra:
            cands = list(extra) + list(cands)
        ctx = self._orig_pack(cands, **kw)
        dropped: list = []
        if self.guards:
            ctx, dropped = self.screens.filter_hits(ctx)
        cls = (self.classify or (lambda metas: "internal"))([h.chunk.meta for h in ctx])
        CURRENT_CLASSIFICATION.set(cls)
        sink = _SINK.get()
        if sink is not None:
            sink.update(dropped=dropped, classification=cls)
        return ctx

    @property
    def tracing(self):
        return self.assistant.tracing

    def events(self, question: str, role: str, *, extra_hits: Optional[list] = None,
               _sink: Optional[dict] = None) -> Iterator[dict]:
        """Events of one question. Must be iterated in ONE thread (contextvars), see service.py."""
        if self.guards:
            v = self.screens.question(question)
            if v.flagged:
                yield {"event": "guard", "data": {"layer": "input", "blocked": True, "reasons": v.reasons}}
                yield {"event": "answer", "data": {"text": REFUSAL_INPUT, "refused": True, "kind": "blocked",
                                                   "citations": [], "invalid_citations": [], "blocked_by": "input"}}
                yield {"event": "done", "data": {"usage": {}, "cost_usd": 0.0, "latency_ms": 0.0, "ttft_ms": None,
                                                 "timings_ms": {}, "trace_id": "", "model": "-"}}
                return
        guard: dict = {"dropped": [], "classification": "internal"}
        tok_e = _EXTRA.set(list(extra_hits or []))
        tok_s = _SINK.set(guard)
        held: list[dict] = []
        sources: list[dict] = []
        try:
            for ev in self.assistant.events(question, role, _sink=_sink):
                e = ev["event"]
                if e == "sources":
                    sources = ev["data"].get("context", [])
                    yield ev
                    yield {"event": "guard", "data": {"layer": "context", "blocked": False,
                                                      "dropped": guard["dropped"],
                                                      "classification": guard["classification"]}}
                elif e == "token":
                    if self.guards and self.s.strict_output:
                        held.append(ev)
                    else:
                        yield ev
                elif e == "answer":
                    d = dict(ev["data"])
                    findings = validate_output(d.get("text", "")) if self.guards else []
                    if findings:
                        if _sink is not None:
                            _sink["raw_answer"] = d.get("text", "")
                        d.update(text=output_replacement(findings, [x["doc_id"] for x in sources]), refused=True,
                                 citations=[], blocked_by="output", findings=findings, replaced=True)
                        yield {"event": "guard", "data": {"layer": "output", "blocked": True, "findings": findings}}
                    else:
                        yield from held
                    held = []
                    yield {"event": "answer", "data": d}
                else:
                    yield ev
        finally:
            for var, tok in ((_EXTRA, tok_e), (_SINK, tok_s)):
                try:
                    var.reset(tok)
                except ValueError:     # closed from another context (client went away): nothing to undo
                    pass

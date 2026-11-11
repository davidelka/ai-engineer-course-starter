"""The tutor conversation engine: one student turn in, one assessed tutor turn out.

    screen input ─► (borderline? LLM classifier) ─► redact PII ─► retrieve phrases
        ─► distress / unsafe / personal_info: fixed kind reply, no model call
        ─► else: tutor model (llmkit.structured, Assessment) ─► validate ─► outcome

turn()          one structured call (complete_structured with repair turns).
stream_turn()   the same call streamed. The JSON's first field is reply_he, so its text is
                decoded while the model writes; every finished SENTENCE is screened
                (safety.screen_output) and only then emitted. The student sees (and hears)
                the first sentence early, and nothing unscreened ever leaves the server.
                If the streamed JSON does not validate, the turn falls back to turn() and the
                final "outcome" event carries the authoritative reply.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from obskit import span
from voicekit.pipeline import split_sentences

from .content import Content, render
from .hooks import Hooks
from .models import Assessment, Finding, SessionState
from .prompts import build_request, opening
from .safety import SAFE_REPLIES, SafetyClassifier, Screen, screen_output, screen_text


@dataclass
class TurnOutcome:
    assessment: Assessment
    findings: list[Finding] = field(default_factory=list)
    screen: Screen = field(default_factory=Screen)
    redacted_text: str = ""
    pii_kinds: list[str] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    model_called: bool = True
    cost_usd: float = 0.0
    timings_ms: dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {"assessment": self.assessment.model_dump(), "findings": [f.__dict__ for f in self.findings],
                "input_flag": self.screen.flag, "pii_redacted": self.pii_kinds, "model_called": self.model_called,
                "retrieved": [r["he"] for r in self.retrieved], "cost_usd": round(self.cost_usd, 6),
                "timings_ms": self.timings_ms, "error": self.error}


class ReplyStreamer:
    """Decodes the value of "reply_he" out of a JSON object that arrives in pieces."""

    def __init__(self, field_name: str = "reply_he"):
        self.field_name = field_name
        self.buf, self.out, self.done = "", "", False

    def feed(self, piece: str) -> str:
        """Add raw JSON text; return the NEW decoded characters of the field (milestone 4:
        mine.partial_json_field decodes the field from everything received so far)."""
        from .hooks import call
        self.buf += piece
        if self.done:
            return ""
        value, self.done = call("partial_json_field", self.buf, self.field_name)
        new = value[len(self.out):]
        self.out = value
        return new


class Tutor:
    def __init__(self, llm, content: Content, *, hooks: Optional[Hooks] = None, safety_llm=None,
                 max_tokens: int = 700, max_repairs: int = 1, cache: bool = True):
        self.llm, self.content = llm, content
        self.hooks = hooks or Hooks()
        self.classifier = SafetyClassifier(safety_llm) if safety_llm is not None else None
        self.max_tokens, self.max_repairs, self.cache = max_tokens, max_repairs, cache

    # ------------------------------------------------------------ session
    def start(self, st: SessionState) -> str:
        line = opening(self.content, st)
        st.history.append(("tutor", line))
        return line

    def record(self, st: SessionState, out: TurnOutcome) -> None:
        """Append the turn to the session (redacted text only) and advance the turn index."""
        st.history.append(("student", out.redacted_text))
        st.history.append(("tutor", out.assessment.reply_he))
        st.turn_index += 1
        c = out.assessment.correction
        st.expected_phrase = c.corrected if c else None

    # ------------------------------------------------------------ shared front half
    def _prepare(self, st: SessionState, text: str) -> tuple[TurnOutcome, bool]:
        t = {}
        t0 = time.perf_counter()
        with span("safety_input", type="guardrail") as sp:
            scr = screen_text(text)
            sp.set_attribute("hebtutor.input_flag", scr.flag)
        t["screen"] = _ms(t0)
        cost = 0.0
        if scr.flag == "none" and scr.borderline and self.classifier is not None:
            t1 = time.perf_counter()
            with span("safety_classifier", type="guardrail") as sp:
                verdict, c = self.classifier.classify(text)
                cost += c
                sp.set_attribute("hebtutor.classifier", verdict.category)
            if verdict.category != "none" and verdict.confidence >= 0.5:
                scr = Screen(verdict.category, scr.reasons + [f"classifier:{verdict.category}"], scr.score)
            t["classifier"] = _ms(t1)
        t1 = time.perf_counter()
        redacted, kinds = self.hooks.redact_for_log(text)
        t["redact"] = _ms(t1)
        out = TurnOutcome(Assessment(reply_he=""), screen=scr, redacted_text=redacted, pii_kinds=kinds,
                          cost_usd=cost, timings_ms=t)
        if scr.blocks_tutor:
            r = SAFE_REPLIES[scr.flag]
            out.assessment = Assessment(reply_he=render(r["reply_he"], st.addressing), help_ar=r["help_ar"],
                                        level_signal="unclear", safety_flag=scr.flag)
            out.model_called = False
            return out, True
        t1 = time.perf_counter()
        with span("retrieve_phrases", type="retrieval") as sp:
            out.retrieved = self.content.retrieve(st.scenario_id, st.level, redacted)
            sp.set_attribute("hebtutor.hits", len(out.retrieved))
        t["retrieve"] = _ms(t1)
        return out, False

    def _finish(self, st: SessionState, out: TurnOutcome, a: Assessment, text: str, mode: str) -> TurnOutcome:
        t1 = time.perf_counter()
        a, findings = self.hooks.validate_assessment(a, out.redacted_text, level=st.level, mode=mode,
                                                     input_flag=out.screen.flag)
        a.reply_he = render(a.reply_he, st.addressing)
        out.assessment = a
        out.findings += findings
        out.timings_ms["validate"] = _ms(t1)
        return out

    # ------------------------------------------------------------ non-streaming
    def turn(self, st: SessionState, text: str, *, mode: str = "text", images=None) -> TurnOutcome:
        from llmkit.structured import StructuredError, complete_structured

        t0 = time.perf_counter()
        with span("tutor_turn", type="agent", attributes={"hebtutor.scenario": st.scenario_id,
                                                          "hebtutor.level": st.level, "hebtutor.mode": mode}) as root:
            out, blocked = self._prepare(st, text)
            if not blocked:
                req = build_request(self.content, st, out.redacted_text, out.retrieved, mode=mode,
                                    max_tokens=self.max_tokens, cache=self.cache, images=images)
                t1 = time.perf_counter()
                try:
                    r = complete_structured(self.llm, req, Assessment, max_repairs=self.max_repairs,
                                            max_tokens=self.max_tokens)
                    out.cost_usd += r.cost_usd
                    if r.repairs:
                        out.findings.append(Finding("repaired", str(r.repairs), "info"))
                    a = r.value
                except StructuredError as exc:
                    out.cost_usd += exc.result.cost_usd if exc.result else 0.0
                    out.error = f"structured_{exc.stage}"
                    a = Assessment(reply_he="", level_signal="unclear")
                out.timings_ms["llm"] = _ms(t1)
                out = self._finish(st, out, a, text, mode)
            root.set_attribute("hebtutor.safety_flag", out.assessment.safety_flag)
            root.set_attribute("hebtutor.cost_usd", round(out.cost_usd, 6))
        out.timings_ms["total"] = _ms(t0)
        return out

    # ------------------------------------------------------------ streaming
    def stream_turn(self, st: SessionState, text: str, *, mode: str = "text") -> Iterator[tuple[str, Any]]:
        """Yields ("sentence", str) for each screened sentence of the reply, then ("outcome", TurnOutcome)."""
        from llmkit.structured import extract_json

        t0 = time.perf_counter()
        out, blocked = self._prepare(st, text)
        if blocked:
            out.timings_ms["total"] = _ms(t0)
            yield "sentence", out.assessment.reply_he
            yield "outcome", out
            return
        req = build_request(self.content, st, out.redacted_text, out.retrieved, mode=mode, max_tokens=self.max_tokens,
                            cache=self.cache)
        from llmkit.structured import provider_schema
        req.response_schema, _ = provider_schema(Assessment, self.llm.provider.name)
        req.schema_name = "Assessment"
        rs, pending, raw, result, emitted = ReplyStreamer(), "", "", None, []
        t1 = time.perf_counter()
        with span("tutor_turn_stream", type="agent", attributes={"hebtutor.scenario": st.scenario_id}):
            for ev in self.llm.stream(req):
                if ev.type == "text":
                    if not raw:
                        out.timings_ms["llm_first_token"] = _ms(t1)
                    raw += ev.text
                    pending += rs.feed(ev.text)
                    done, pending = split_sentences(pending, final=rs.done)
                    for s in done:
                        why = screen_output(s)
                        if why:
                            out.findings.append(Finding("sentence_dropped", why, "block"))
                            continue
                        if not emitted:
                            out.timings_ms["first_sentence"] = _ms(t1)
                        emitted.append(s)
                        yield "sentence", render(s, st.addressing)
                elif ev.type == "done":
                    result = ev.result
            out.timings_ms["llm"] = _ms(t1)
            if result is not None:
                out.cost_usd += result.cost_usd or 0.0
            try:
                a = Assessment.model_validate_json(extract_json(raw))
            except ValueError:
                out.findings.append(Finding("stream_invalid_fallback", raw[:60], "warn"))
                fb = self.turn(st, text, mode=mode)
                fb.cost_usd += out.cost_usd
                fb.findings = out.findings + fb.findings
                fb.timings_ms["total"] = _ms(t0)
                yield "outcome", fb
                return
            out = self._finish(st, out, a, text, mode)
        if emitted and any(f.code == "sentence_dropped" for f in out.findings):
            out.assessment.reply_he = " ".join(emitted)  # the student saw only the screened sentences
        out.timings_ms["total"] = _ms(t0)
        yield "outcome", out


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 2)


def assessment_json(a: Assessment) -> str:
    return json.dumps(a.model_dump(), ensure_ascii=False)

"""Offline stand-ins for the model, with the same API as llmkit.LLM (complete + stream).

    RuleTutorLLM    the free baseline "model": reads the session block and the student's
                    utterance out of the request, runs hebtutor/rules.py and the safety screen,
                    and answers with Assessment JSON (or SafetyVerdict JSON for classifier calls).
                    Can simulate time to first token and tokens per second, so latency budgets
                    measure real code paths.
    OracleTutorLLM  answers with the GOLD correction of the eval set when it recognizes the
                    utterance (tests the plumbing: validation, metrics, gates). Optionally makes
                    the first reply invalid once, to exercise llmkit.structured's repair loop.
    RecordingLLM    wraps a real llmkit.LLM and appends every reply to a JSONL file.
    ReplayLLM       answers from such a recording: re-run the eval of a real model for free.

Usage is estimated at about 3 characters per token (Hebrew and Arabic take more tokens per
character than English) and priced as Claude Haiku 5.5, so cost code paths run.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Callable, Iterator, Optional, Union

from llmkit.pricing import cost_usd
from llmkit.types import ChatResult, StreamEvent, Usage, content_text

from .content import Content
from .models import Assessment, SafetyVerdict, VocabItem
from .rules import RuleDetector, is_stuck, level_signal, rule_reply
from .safety import SAFE_REPLIES, screen_text

SESSION_RE = re.compile(r'<session scenario="([^"]+)" level="([^"]+)" addressing="([^"]+)" mode="([^"]+)" turn="(\d+)"/>')
UTTER_RE = re.compile(r"<student_utterance>\n?(.*?)\n?</student_utterance>", re.S)
PHRASE_RE = re.compile(r"^- (.+?) = ", re.M)


def system_text(req) -> str:
    return req.system if isinstance(req.system, str) else "\n".join(getattr(b, "text", "") for b in req.system)


def request_key(req) -> str:
    """Stable key of one tutor/classifier request: session line + last user message."""
    s = SESSION_RE.search(system_text(req))
    texts = [content_text(m.content) for m in req.messages]
    last = "\n".join(texts[-3:])  # includes a repair turn and the reply it repairs, when there is one
    kind = "safety" if "You classify one message" in system_text(req) else "tutor"
    return hashlib.sha256(f"{kind}|{s.group(0) if s else ''}|{last}".encode("utf-8")).hexdigest()[:20]


class _Provider:
    name = "anthropic"


class FakeLLMBase:
    model = "claude-haiku-5-5"

    def __init__(self, *, ttft_s: float = 0.0, tps: float = 0.0, chunk_chars: int = 12,
                 sleep: Callable[[float], None] = time.sleep):
        self.provider = _Provider()
        self.ttft_s, self.tps, self.chunk_chars, self.sleep = ttft_s, tps, chunk_chars, sleep
        self.calls = 0

    def answer(self, req) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    def _result(self, req, text: str, latency: float, ttft: Optional[float]) -> ChatResult:
        prompt = system_text(req) + "\n".join(content_text(m.content) for m in req.messages)
        usage = Usage(input_tokens=len(prompt) // 3, output_tokens=max(1, len(text) // 3))
        return ChatResult(text=text, stop_reason="end", usage=usage, provider="anthropic", model=self.model,
                          cost_usd=cost_usd(self.model, usage), latency_s=latency, ttft_s=ttft,
                          request_id=f"fake-{self.calls}")

    def complete(self, req, *, stream: bool = False, **kw) -> ChatResult:
        self.calls += 1
        t0 = time.perf_counter()
        text = self.answer(req)
        if self.ttft_s or self.tps:
            self.sleep(self.ttft_s + (len(text) / 3 / self.tps if self.tps else 0))
        return self._result(req, text, time.perf_counter() - t0, self.ttft_s if stream else None)

    def stream(self, req, **kw) -> Iterator[StreamEvent]:
        self.calls += 1
        t0 = time.perf_counter()
        text = self.answer(req)
        if self.ttft_s:
            self.sleep(self.ttft_s)
        ttft = None
        for i in range(0, len(text), self.chunk_chars):
            piece = text[i:i + self.chunk_chars]
            if self.tps:
                self.sleep(len(piece) / 3 / self.tps)
            if ttft is None:
                ttft = time.perf_counter() - t0
            yield StreamEvent("text", piece)
        yield StreamEvent("done", result=self._result(req, text, time.perf_counter() - t0, ttft))


class RuleTutorLLM(FakeLLMBase):
    def __init__(self, content: Content, **kw):
        super().__init__(**kw)
        self.content = content
        self.detector = RuleDetector(content)

    def parse(self, req) -> tuple[dict, str, list[str]]:
        sys_ = system_text(req)
        m = SESSION_RE.search(sys_)
        sess = {"scenario": "clinic", "level": "A1", "addressing": "m", "mode": "text", "turn": 0}
        if m:
            sess = {"scenario": m.group(1), "level": m.group(2), "addressing": m.group(3), "mode": m.group(4),
                    "turn": int(m.group(5))}
        # the last user turn that carries the utterance (after a repair turn it is not the last message)
        texts = [content_text(m.content) for m in req.messages if m.role == "user"]
        last = next((t for t in reversed(texts) if "<student_utterance>" in t), texts[-1] if texts else "")
        u = UTTER_RE.search(last)
        return sess, (u.group(1) if u else last), PHRASE_RE.findall(last)

    def answer(self, req) -> str:
        if "You classify one message" in system_text(req):
            text = content_text(req.messages[-1].content).removeprefix("Message: ")
            try:
                text = json.loads(text)
            except ValueError:
                pass
            s = screen_text(text, threshold=1.0)
            return SafetyVerdict(category=s.flag, confidence=0.6 if s.flag != "none" else 0.8,
                                 reason="rule-based fake classifier: " + (", ".join(s.reasons) or "no signal")
                                 ).model_dump_json()
        return self.assess(req).model_dump_json()

    def assess(self, req) -> Assessment:
        sess, text, phrases = self.parse(req)
        scr = screen_text(text)
        flag = scr.flag
        if flag in SAFE_REPLIES:
            from .content import render
            r = SAFE_REPLIES[flag]
            return Assessment(reply_he=render(r["reply_he"], sess["addressing"]), help_ar=r["help_ar"],
                              level_signal="unclear", safety_flag=flag)
        corr = None if flag in ("injection", "off_topic") else \
            self.detector.detect(text, addressing=sess["addressing"], mode=sess["mode"])
        stuck = is_stuck(text)
        reply = rule_reply(self.content, sess["scenario"], sess["level"], sess["addressing"], sess["turn"], corr,
                           stuck, flag, phrases[0] if phrases else None)
        help_ar = None
        if stuck:
            sc = self.content.scenarios[sess["scenario"]]
            help_ar = f"المطلوب: {sc.goal_ar.get(sess['level'], '')} جرّب أن تقول: {phrases[0]}" if phrases else \
                "لا بأس. حاول أن تجيب بكلمة أو كلمتين بالعبرية."
        vocab = []
        used = (corr.corrected if corr else "") + " " + reply
        for v in self.content.vocab:
            if v["scenario"] == sess["scenario"] and v["he"] in used and len(vocab) < 2:
                vocab.append(VocabItem(he=v["he"], ar=v["ar"], transliteration=v["transliteration"]))
        return Assessment(reply_he=reply, correction=corr, help_ar=help_ar, new_vocabulary=vocab,
                          level_signal=level_signal(text) if flag == "none" else "unclear", safety_flag=flag)


class OracleTutorLLM(RuleTutorLLM):
    """Gold answers for eval utterances (plumbing tests); rule answers for anything else."""

    def __init__(self, content: Content, evalset: list[dict], *, first_reply_invalid: bool = False, **kw):
        super().__init__(content, **kw)
        self.gold = {r["text"]: r for r in evalset}
        self.first_invalid = first_reply_invalid
        self._failed: set[str] = set()

    def answer(self, req) -> str:
        if "You classify one message" in system_text(req):
            return super().answer(req)
        sess, text, _ = self.parse(req)
        row = self.gold.get(text)
        if row is None:
            return super().answer(req)
        if self.first_invalid and text not in self._failed:
            self._failed.add(text)
            return '{"reply_he": "שלום", "level_signal": "C2"}'
        from .rules import EXPLAIN_AR, praise
        from .models import Correction
        g = row["gold"]
        corr = None
        if g["error_type"]:
            corr = Correction(original=g["original"], corrected=g["corrected"], error_type=g["error_type"],
                              explanation_ar=EXPLAIN_AR[g["error_type"]].format(fix=g["corrected"]))
        reply = f"כמעט! אומרים: «{g['corrected']}»." if corr else praise(sess["turn"])
        return Assessment(reply_he=reply + " מה עוד?", correction=corr, level_signal=row["level"],
                          safety_flag=g["safety_flag"]).model_dump_json()


class RecordingLLM:
    """Wraps a real model; every reply is appended to `path` keyed by request_key()."""

    def __init__(self, inner, path: Union[str, Path]):
        self.inner, self.path = inner, Path(path)
        self.provider, self.model = inner.provider, inner.model

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def _write(self, req, res: ChatResult) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": request_key(req), "text": res.text, "input_tokens": res.usage.input_tokens,
                                 "output_tokens": res.usage.output_tokens, "cost_usd": res.cost_usd,
                                 "latency_s": res.latency_s, "ttft_s": res.ttft_s}, ensure_ascii=False) + "\n")

    def complete(self, req, **kw) -> ChatResult:
        res = self.inner.complete(req, **kw)
        self._write(req, res)
        return res

    def stream(self, req, **kw) -> Iterator[StreamEvent]:
        for ev in self.inner.stream(req, **kw):
            if ev.type == "done":
                self._write(req, ev.result)
            yield ev


class ReplayLLM(FakeLLMBase):
    """Answers from a RecordingLLM file. The LAST recording of a key wins (so a re-record after a
    prompt change replaces old answers). An unknown request raises KeyError: the recording is
    older than the prompt or the eval set, record again."""

    def __init__(self, path: Union[str, Path], **kw):
        super().__init__(**kw)
        self.path = Path(path)
        self.rows: dict[str, dict] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                self.rows[r["key"]] = r

    def answer(self, req) -> str:
        k = request_key(req)
        if k not in self.rows:
            raise KeyError(f"not_recorded: {k}")
        return self.rows[k]["text"]

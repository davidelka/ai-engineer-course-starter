"""STT -> LLM -> TTS, with a timeline of every stage (lesson 21 latency budget).

Two modes:
- sequential: transcribe, wait for the whole LLM answer, synthesize the whole answer.
  First audio = STT + full LLM time + TTS time to first byte of the WHOLE text.
- streaming: the LLM streams; each finished sentence goes to TTS immediately, on its own
  thread, while the LLM keeps writing the next one. First audio = STT + LLM time to the end
  of the FIRST sentence + TTS time to first byte of that sentence.
The difference between the two is the main lesson of the latency budget.

Every timestamp is wall clock (time.perf_counter) relative to the moment the user's audio
is complete (the "end of turn"). Real systems add voice-activity detection before that and
playback / network after it; see the lesson.
"""

from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from llmkit import ChatRequest, Message

from .ports import STT, TTS, AudioInput
from .types import Transcript

_END = re.compile(r"([.!?…؟]+)(\s+|$)")  # . ! ? … and the Arabic question mark


def split_sentences(buffer: str, *, final: bool = False, max_chars: int = 140) -> tuple[list[str], str]:
    """Cut complete sentences off the front of `buffer`. Returns (sentences, rest).
    A very long run without punctuation is cut at the last comma or space before max_chars,
    so TTS never waits for a 400-character sentence. final=True flushes the rest too."""
    out: list[str] = []
    while True:
        m = _END.search(buffer)
        if m:
            out.append(buffer[:m.end(1)].strip())
            buffer = buffer[m.end():]
            continue
        if len(buffer) > max_chars:
            cut = max(buffer.rfind(",", 0, max_chars), buffer.rfind(" ", 0, max_chars))
            if cut > 20:
                out.append(buffer[:cut + 1].strip())
                buffer = buffer[cut + 1:]
                continue
        break
    if final and buffer.strip():
        out.append(buffer.strip())
        buffer = ""
    return [s for s in out if s], buffer


@dataclass
class Event:
    t: float  # seconds since end of the user's turn
    stage: str  # "stt" | "llm" | "tts"
    what: str


@dataclass
class TurnResult:
    transcript: Transcript
    reply: str = ""
    audio: bytes = b""  # concatenated TTS output (pcm when streaming, else the synthesized format)
    sentences: list[str] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    mode: str = "streaming"
    cost_usd: float = 0.0

    def at(self, stage: str, what: str) -> Optional[float]:
        return next((e.t for e in self.events if e.stage == stage and e.what == what), None)

    @property
    def first_audio_s(self) -> Optional[float]:
        return self.at("tts", "first_audio")

    @property
    def total_s(self) -> Optional[float]:
        return self.at("tts", "done")

    def budget(self) -> dict[str, Optional[float]]:
        """The numbers the lab prints: per-stage durations and the user-visible wait."""
        stt = self.at("stt", "done")
        ttft = self.at("llm", "first_token")
        return {
            "stt_s": stt,
            "llm_ttft_s": None if ttft is None or stt is None else ttft - stt,
            "llm_first_sentence_s": None if stt is None or self.at("llm", "first_sentence") is None
            else self.at("llm", "first_sentence") - stt,
            "llm_total_s": None if stt is None or self.at("llm", "done") is None else self.at("llm", "done") - stt,
            "first_audio_s": self.first_audio_s,
            "total_s": self.total_s,
        }


class VoicePipeline:
    def __init__(self, stt: STT, llm, tts: TTS, *, system: str = "", language: Optional[str] = "he",
                 voice: Optional[str] = None, instructions: Optional[str] = None, max_tokens: int = 300):
        self.stt, self.llm, self.tts = stt, llm, tts
        self.system, self.language, self.voice = system, language, voice
        self.instructions, self.max_tokens = instructions, max_tokens

    def turn(self, audio: AudioInput, *, streaming: bool = True,
             history: Optional[list[Message]] = None) -> TurnResult:
        t0 = time.perf_counter()
        events: list[Event] = []
        lock = threading.Lock()

        def mark(stage: str, what: str) -> None:
            with lock:
                events.append(Event(round(time.perf_counter() - t0, 4), stage, what))

        mark("stt", "start")
        tr = self.stt.transcribe(audio, language=self.language)
        mark("stt", "done")
        req = ChatRequest(messages=list(history or []) + [Message("user", tr.text)], system=self.system,
                          max_tokens=self.max_tokens)
        res = TurnResult(tr, events=events, mode="streaming" if streaming else "sequential")
        cost = tr.cost_usd or 0.0
        if not streaming:
            mark("llm", "start")
            llm_t0 = time.perf_counter() - t0
            # Collected from a stream so TTFT is measured; nothing is spoken until the end.
            r = self.llm.complete(req, stream=True)
            mark("llm", "done")
            if r.ttft_s is not None:
                with lock:
                    events.append(Event(round(llm_t0 + r.ttft_s, 4), "llm", "first_token"))
            mark("llm", "first_sentence")  # in this mode the "first sentence" is the whole answer
            res.reply, res.sentences = r.text, [r.text]
            cost += r.cost_usd or 0.0
            mark("tts", "start")
            chunks = []
            for c in self.tts.stream(r.text, voice=self.voice, language=self.language,
                                     instructions=self.instructions, format="pcm"):
                if not chunks:
                    mark("tts", "first_audio")
                chunks.append(c)
            mark("tts", "done")
            res.audio = b"".join(chunks)
            res.cost_usd = cost + self._tts_cost(r.text)
            return res

        q: "queue.Queue[Optional[str]]" = queue.Queue()
        llm_out: dict = {}

        def produce():
            buf, first = "", True
            mark("llm", "start")
            try:
                for ev in self.llm.stream(req):
                    if ev.type == "text":
                        if first:
                            mark("llm", "first_token")
                            first = False
                        buf += ev.text
                        done, buf = split_sentences(buf)
                        for s in done:
                            if not res.sentences:
                                mark("llm", "first_sentence")
                            res.sentences.append(s)
                            q.put(s)
                    elif ev.type == "done":
                        llm_out["result"] = ev.result
                done, buf = split_sentences(buf, final=True)
                for s in done:
                    if not res.sentences:
                        mark("llm", "first_sentence")
                    res.sentences.append(s)
                    q.put(s)
                mark("llm", "done")
            except Exception as exc:  # surface in the main thread
                llm_out["error"] = exc
            finally:
                q.put(None)

        th = threading.Thread(target=produce, daemon=True)
        th.start()
        chunks: list[bytes] = []
        tts_cost = 0.0
        mark("tts", "start")
        while True:
            s = q.get()
            if s is None:
                break
            for c in self.tts.stream(s, voice=self.voice, language=self.language,
                                     instructions=self.instructions, format="pcm"):
                if not chunks:
                    mark("tts", "first_audio")
                chunks.append(c)
            tts_cost += self._tts_cost(s)
        th.join()
        mark("tts", "done")
        if "error" in llm_out:
            raise llm_out["error"]
        r = llm_out.get("result")
        res.reply = r.text if r is not None else " ".join(res.sentences)
        res.audio = b"".join(chunks)
        res.cost_usd = cost + ((r.cost_usd or 0.0) if r is not None else 0.0) + tts_cost
        return res

    def _tts_cost(self, text: str) -> float:
        """Rough TTS cost when the adapter does not report one per stream call."""
        model = getattr(self.tts, "model", "")
        if model == "gpt-4o-mini-tts":
            return 0.015 * (len(text) / 14.0) / 60  # ~14 characters per second of speech
        return 0.0

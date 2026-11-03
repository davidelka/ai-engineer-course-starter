"""One SPOKEN turn: student audio -> STT (Hebrew) -> tutor (streamed, screened sentences) -> TTS.

Built on voicekit's ports (lesson 21) and its sentence splitter, with the tutor's own streaming
in the middle (the assessment is JSON, so voicekit.VoicePipeline's plain-text LLM stage does not
fit; the timing model is the same). Every timestamp is seconds after the student's audio is
complete. The budget the course uses: first audio within 1.5 seconds (natural turn gaps are a
few hundred milliseconds; voice products aim at about one second; a learner tolerates a bit
more, and the transcript-plus-assessment design costs some).

Honest notes, checked November 2026 (voicekit/README.md):
- OpenAI gpt-4o-mini-tts (and tts-1) shut down on 2027-01-06; whisper-1 and gpt-4o-transcribe on
  2027-02-26. gpt-transcribe (the recommended STT) gives no word timestamps. Keep the adapters
  swappable: the local path is faster-whisper with the ivrit.ai Hebrew model + the Piper Hebrew
  voice, both free and on your own machine.
- "Speaking feedback" is intelligibility via ASR (hebtutor/speaking.py), not pronunciation scoring.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from voicekit.audio import pcm_to_wav
from voicekit.ports import STT, TTS
from voicekit.types import Transcript

from .hooks import Hooks
from .models import SessionState
from .speaking import SpeakingFeedback
from .tutor import Tutor, TurnOutcome

FIRST_AUDIO_BUDGET_S = 1.5


@dataclass
class VoiceTurn:
    transcript: Transcript
    outcome: Optional[TurnOutcome] = None
    speaking: Optional[SpeakingFeedback] = None
    audio_wav: bytes = b""
    sentences: list[str] = field(default_factory=list)
    timeline: dict[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0

    def budget(self) -> dict:
        t = self.timeline
        return {"stt_s": t.get("stt_done"), "first_sentence_s": t.get("first_sentence"),
                "first_audio_s": t.get("first_audio"), "total_s": t.get("done"),
                "within_budget": (t.get("first_audio") or 99) <= FIRST_AUDIO_BUDGET_S}

    def to_dict(self) -> dict:
        return {"transcript": self.transcript.text, "stt_provider": self.transcript.provider,
                "speaking": self.speaking.to_dict() if self.speaking else None,
                "outcome": self.outcome.to_dict() if self.outcome else None, "sentences": self.sentences,
                "timeline_s": self.timeline, "budget": self.budget(), "cost_usd": round(self.cost_usd, 6)}


class SpokenTurn:
    def __init__(self, stt: STT, tutor: Tutor, tts: TTS, *, hooks: Optional[Hooks] = None,
                 voice: Optional[str] = None, sample_rate: int = 24_000):
        self.stt, self.tutor, self.tts = stt, tutor, tts
        self.hooks = hooks or tutor.hooks
        self.voice, self.sample_rate = voice, sample_rate
        self.instructions = "Speak slowly and clearly, in standard Israeli Hebrew, for a language learner."

    def run(self, st: SessionState, audio: bytes, *, filename: str = "audio.wav") -> VoiceTurn:
        t0 = time.perf_counter()
        tl: dict[str, float] = {}

        def mark(k: str) -> None:
            tl.setdefault(k, round(time.perf_counter() - t0, 4))

        sc = self.tutor.content.scenarios[st.scenario_id]
        hint = " ".join(p["he"] for p in sc.phrases_for(st.level)[:4])  # vocabulary hint for the recognizer
        tr = self.stt.transcribe(audio, language="he", prompt=hint, filename=filename)
        mark("stt_done")
        res = VoiceTurn(tr, timeline=tl, cost_usd=tr.cost_usd or 0.0)
        if st.expected_phrase:
            res.speaking = self.hooks.word_feedback(st.expected_phrase, tr.text)
            mark("speaking_done")
        if not tr.text.strip():
            res.timeline["done"] = round(time.perf_counter() - t0, 4)
            return res
        chunks: list[bytes] = []
        for ev, val in self.tutor.stream_turn(st, tr.text, mode="voice"):
            if ev == "sentence":
                mark("first_sentence")
                res.sentences.append(val)
                for c in self.tts.stream(val, voice=self.voice, language="he", instructions=self.instructions,
                                         format="pcm"):
                    mark("first_audio")
                    chunks.append(c)
            else:
                res.outcome = val
        mark("done")
        res.cost_usd += (res.outcome.cost_usd if res.outcome else 0.0) + self._tts_cost(" ".join(res.sentences))
        cfg = getattr(getattr(self.tts, "voice", None), "config", None)  # PiperTTS: voice.config.sample_rate
        sr = getattr(self.tts, "sample_rate", None) or getattr(cfg, "sample_rate", None) or self.sample_rate
        res.audio_wav = pcm_to_wav(b"".join(chunks), sr) if chunks else b""
        return res

    def _tts_cost(self, text: str) -> float:
        if getattr(self.tts, "model", "") == "gpt-4o-mini-tts":
            return 0.015 * (len(text) / 14.0) / 60  # about $0.015 per audio minute, ~14 characters per second
        return 0.0

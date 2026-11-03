"""Settings from the environment (and .env), and the factories that turn them into adapters.

    TUTOR        rule (default, free) | llm (Claude Haiku 5.5 through llmkit) | replay
    LLM_MODEL    anthropic:claude-haiku-5-5
    RECORD       path of a JSONL file: record every real model reply (with TUTOR=llm)
    REPLAY       path of such a recording (with TUTOR=replay)
    SAFETY_LLM   on (default) | off: the second-opinion classifier for borderline inputs
    STT          fake (default) | openai | local       STT_MODEL (gpt-transcribe | ivrit-ai/whisper-large-v3-turbo-ct2)
    TTS          fake (default) | openai | piper       TTS_MODEL, TTS_VOICE, PIPER_MODEL (path of the .onnx voice)
    FAKE_DELAYS  1 = the fakes sleep like real services (STT 0.25 s, LLM first token 0.5 s at 60 tokens/s,
                 TTS first byte 0.25 s), so latency budgets are meaningful offline
    DB_PATH      results/tutor.db        TRACES  results/traces.jsonl ("" = no tracing)
    ADMIN_TOKEN  enables admin writes (create classes, approve content); empty = refused
    RETENTION_DAYS  30
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT.parents[1]


@dataclass
class Settings:
    tutor: str = "rule"
    llm_model: str = "anthropic:claude-haiku-5-5"
    record: str = ""
    replay: str = ""
    safety_llm: bool = True
    stt: str = "fake"
    stt_model: str = ""
    tts: str = "fake"
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "marin"
    piper_model: str = "he_IL-saspeech-medium.onnx"
    fake_delays: bool = False
    db_path: str = str(PROJECT / "results" / "tutor.db")
    traces: str = str(PROJECT / "results" / "traces.jsonl")
    retention_days: int = 30

    @classmethod
    def from_env(cls, **override) -> "Settings":
        from llmkit import load_dotenv
        load_dotenv(str(ROOT / ".env"))
        e = os.environ.get
        s = cls(tutor=e("TUTOR", "rule"), llm_model=e("LLM_MODEL", cls.llm_model), record=e("RECORD", ""),
                replay=e("REPLAY", ""), safety_llm=e("SAFETY_LLM", "on") != "off", stt=e("STT", "fake"),
                stt_model=e("STT_MODEL", ""), tts=e("TTS", "fake"), tts_model=e("TTS_MODEL", cls.tts_model),
                tts_voice=e("TTS_VOICE", cls.tts_voice), piper_model=e("PIPER_MODEL", cls.piper_model),
                fake_delays=e("FAKE_DELAYS", "0") == "1", db_path=e("DB_PATH", cls.db_path),
                traces=e("TRACES", cls.traces), retention_days=int(e("RETENTION_DAYS", "30")))
        for k, v in override.items():
            setattr(s, k, v)
        return s

    # ------------------------------------------------------------ factories
    def make_llm(self, content):
        from .fakes import RecordingLLM, ReplayLLM, RuleTutorLLM
        delays = dict(ttft_s=0.5, tps=60) if self.fake_delays else {}
        if self.tutor == "rule":
            return RuleTutorLLM(content, **delays)
        if self.tutor == "replay":
            return ReplayLLM(self.replay or str(PROJECT / "data" / "recorded" / "claude-haiku-5-5.jsonl"), **delays)
        if self.tutor == "llm":
            from llmkit import LLM
            llm = LLM(self.llm_model)
            return RecordingLLM(llm, self.record) if self.record else llm
        raise ValueError(f"TUTOR must be rule, llm or replay, not {self.tutor!r}")

    def make_stt(self):
        if self.stt == "fake":
            from voicekit import FakeSTT
            return FakeSTT(latency_s=0.25, rtf=0.05) if self.fake_delays else FakeSTT()
        if self.stt == "openai":
            from voicekit.openai_audio import OpenAITranscriber
            return OpenAITranscriber(self.stt_model or "gpt-transcribe")
        if self.stt == "local":
            from voicekit.local import FasterWhisperSTT
            return FasterWhisperSTT(self.stt_model or "ivrit-ai/whisper-large-v3-turbo-ct2")
        raise ValueError(f"STT must be fake, openai or local, not {self.stt!r}")

    def make_tts(self):
        if self.tts == "fake":
            from voicekit import FakeTTS
            return FakeTTS(ttfb_s=0.25, rtf=0.1) if self.fake_delays else FakeTTS()
        if self.tts == "openai":
            from voicekit.openai_audio import OpenAISpeech
            return OpenAISpeech(self.tts_model, self.tts_voice)
        if self.tts == "piper":
            from voicekit.local import PiperTTS
            return PiperTTS(self.piper_model)
        raise ValueError(f"TTS must be fake, openai or piper, not {self.tts!r}")

    def setup_tracing(self):
        """obskit tracing to a JSONL file, with OUR redactor on every span (students are minors)."""
        if not self.traces:
            return None
        from obskit import setup_tracing

        from .hooks import pick_hooks
        red = pick_hooks(quiet=True).redact_for_log

        def redactor(text: str) -> tuple[str, int]:
            out, kinds = red(text)
            return out, len(kinds)
        return setup_tracing("hebrew-tutor", jsonl=self.traces, redact=redactor, capture_content=False)

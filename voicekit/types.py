"""Provider-neutral speech types (lesson 21, final project F2)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Word:
    """One recognized word.

    start / end: seconds from the start of the audio, when the engine gives timestamps
    (OpenAI whisper-1 with timestamp_granularities=["word"], faster-whisper with
    word_timestamps=True). confidence: 0..1 when the engine exposes one (faster-whisper
    word.probability; exp(sum of token logprobs) for gpt-4o(-mini)-transcribe). Confidence
    says how sure the RECOGNIZER is about the word, not how well it was pronounced.
    """

    text: str
    start: Optional[float] = None
    end: Optional[float] = None
    confidence: Optional[float] = None


@dataclass
class Transcript:
    text: str
    language: Optional[str] = None  # what the engine detected or was told
    words: list[Word] = field(default_factory=list)
    duration_s: Optional[float] = None  # audio length
    provider: str = ""
    model: str = ""
    latency_s: float = 0.0  # wall clock of the transcription call
    cost_usd: Optional[float] = None
    raw: Optional[Any] = None

    @property
    def confidence(self) -> Optional[float]:
        """Geometric mean of the word confidences (None when the engine gives none)."""
        cs = [w.confidence for w in self.words if w.confidence is not None]
        if not cs:
            return None
        return math.exp(sum(math.log(max(c, 1e-9)) for c in cs) / len(cs))


@dataclass
class Speech:
    """Synthesized audio. format: "wav" | "mp3" | "opus" | "pcm" (pcm = raw 16-bit mono)."""

    audio: bytes
    format: str = "wav"
    sample_rate: int = 24_000
    duration_s: Optional[float] = None
    provider: str = ""
    model: str = ""
    voice: str = ""
    latency_s: float = 0.0  # until the last byte
    ttfb_s: Optional[float] = None  # until the FIRST audio byte: what the listener waits for
    cost_usd: Optional[float] = None
    raw: Optional[Any] = None

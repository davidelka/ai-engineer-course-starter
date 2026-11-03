"""Fake adapters: free, offline, deterministic. Every test and every offline lab path uses them.

FakeTTS writes a real WAV (a quiet tone whose length follows the text, about 14 characters
per second, like calm speech) and hides the text inside it (a RIFF INFO comment). FakeSTT
reads the text back, then applies the errors you ask for. So a round trip
FakeTTS -> FakeSTT -> wer() is a full pipeline with known, controllable mistakes.

Both can simulate latency (a fixed part plus a part proportional to the audio length), so
the latency-budget lab measures real wall-clock time through real code paths.
"""

from __future__ import annotations

import hashlib
import random
import time
from typing import Callable, Iterator, Optional

from .audio import add_comment, duration_of, pcm_to_wav, read_comment, tone
from .ports import AudioInput, read_audio
from .types import Speech, Transcript, Word

# Letters that sound the same (or close) in modern Hebrew: a recognizer that hears the
# word right can still SPELL it wrong, and WER counts that as a full word error.
HOMOPHONES = {"ט": "ת", "ת": "ט", "כ": "ח", "ח": "כ", "ק": "כ", "א": "ע", "ע": "א", "ס": "ש", "ש": "ס"}


class FakeTTS:
    name = "fake-tts"

    def __init__(self, *, chars_per_second: float = 14.0, sample_rate: int = 16_000, ttfb_s: float = 0.0,
                 rtf: float = 0.0, chunk_s: float = 0.25, sleep: Callable[[float], None] = time.sleep):
        """ttfb_s: delay before the first audio chunk. rtf: real-time factor, seconds of
        compute per second of audio (0.1 = ten times faster than real time)."""
        self.cps, self.sample_rate, self.ttfb_s, self.rtf = chars_per_second, sample_rate, ttfb_s, rtf
        self.chunk_s, self.sleep = chunk_s, sleep

    def _duration(self, text: str) -> float:
        return max(0.3, len(text) / self.cps)

    def synthesize(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
                   instructions: Optional[str] = None, format: str = "wav") -> Speech:
        t0 = time.perf_counter()
        first = None
        chunks = []
        for c in self.stream(text, format="pcm"):
            first = first if first is not None else time.perf_counter() - t0
            chunks.append(c)
        pcm = b"".join(chunks)
        audio = add_comment(pcm_to_wav(pcm, self.sample_rate), text) if format == "wav" else pcm
        return Speech(audio, format if format == "pcm" else "wav", self.sample_rate, len(pcm) / 2 / self.sample_rate,
                      self.name, "fake", voice or "tone", time.perf_counter() - t0, first, 0.0)

    def stream(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
               instructions: Optional[str] = None, format: str = "pcm") -> Iterator[bytes]:
        total = self._duration(text)
        if self.ttfb_s:
            self.sleep(self.ttfb_s)
        done = 0.0
        while done < total - 1e-9:
            step = min(self.chunk_s, total - done)
            if self.rtf:
                self.sleep(step * self.rtf)
            yield tone(step, 196.0 + 20 * (len(text) % 7), self.sample_rate, 0.1)
            done += step


class FakeSTT:
    name = "fake-stt"

    def __init__(self, *, error_rate: float = 0.0, seed: int = 0, latency_s: float = 0.0, rtf: float = 0.0,
                 substitutions: Optional[dict[str, str]] = None, script: Optional[dict[str, str]] = None,
                 sleep: Callable[[float], None] = time.sleep):
        """error_rate: probability that a word gets a homophone spelling error.
        substitutions: whole-word replacements, to simulate what an accent makes the
        recognizer hear (e.g. {"פרק": "ברק"} for /p/ said as /b/).
        script: sha256(audio)[:16] -> text, for audio that carries no hidden text.
        latency_s + rtf * audio_seconds: simulated processing time."""
        self.error_rate, self.seed, self.latency_s, self.rtf = error_rate, seed, latency_s, rtf
        self.substitutions, self.script, self.sleep = substitutions or {}, script or {}, sleep

    def _corrupt(self, word: str, rng: random.Random) -> str:
        for i, ch in enumerate(word):
            if ch in HOMOPHONES:
                return word[:i] + HOMOPHONES[ch] + word[i + 1:]
        return word[:-1] if len(word) > 2 else word + word[-1:]

    def transcribe(self, audio: AudioInput, *, language: Optional[str] = None, prompt: Optional[str] = None,
                   word_timestamps: bool = False, filename: str = "audio.wav") -> Transcript:
        t0 = time.perf_counter()
        data = read_audio(audio)
        dur = duration_of(data) or 0.0
        if self.latency_s or self.rtf:
            self.sleep(self.latency_s + self.rtf * dur)
        text = read_comment(data)
        if text is None:
            text = self.script.get(hashlib.sha256(data).hexdigest()[:16], "")
        rng = random.Random(self.seed)
        words: list[Word] = []
        tokens = text.split()
        step = dur / max(1, len(tokens))
        for k, tok in enumerate(tokens):
            out, conf = tok, 0.97
            if tok in self.substitutions:
                out, conf = self.substitutions[tok], 0.62
            elif self.error_rate and rng.random() < self.error_rate:
                out, conf = self._corrupt(tok, rng), 0.48
            words.append(Word(out, round(k * step, 3) if word_timestamps else None,
                              round((k + 1) * step, 3) if word_timestamps else None, conf))
        return Transcript(" ".join(w.text for w in words), language, words, dur, self.name, "fake",
                          time.perf_counter() - t0, 0.0)

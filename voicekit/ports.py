"""The two ports. Application code (the voice pipeline, the F2 tutor) depends only on
these; adapters (OpenAI, local, fake) plug in behind them.

Why ports and not one "voice provider": speech-to-text and text-to-speech are separate
services with separate vendors, prices, latencies and Hebrew quality. The best STT for
Hebrew (a fine-tuned local Whisper, or a cloud API) is rarely made by the same company as
the best Hebrew voice. Keeping them apart lets you swap one without touching the other,
and lets every test run on fakes.
"""

from __future__ import annotations

from typing import Iterator, Optional, Protocol, Union, runtime_checkable

from .types import Speech, Transcript

AudioInput = Union[bytes, str]  # bytes, or a path to an audio file


@runtime_checkable
class STT(Protocol):
    name: str

    def transcribe(self, audio: AudioInput, *, language: Optional[str] = None, prompt: Optional[str] = None,
                   word_timestamps: bool = False, filename: str = "audio.wav") -> Transcript:
        """language: ISO-639-1 hint ("he", "ar", "en"). Always pass it when you know it:
        it improves accuracy and latency, and stops the engine from "detecting" Arabic in a
        Hebrew sentence with an Arabic accent (exactly the F2 situation).
        prompt: vocabulary / context hint (names, terms).
        word_timestamps: ask for per-word timing when the engine supports it."""
        ...


@runtime_checkable
class TTS(Protocol):
    name: str

    def synthesize(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
                   instructions: Optional[str] = None, format: str = "wav") -> Speech:
        ...

    def stream(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
               instructions: Optional[str] = None, format: str = "pcm") -> Iterator[bytes]:
        """Audio chunks as they are produced, so playback can start before synthesis ends."""
        ...


def read_audio(audio: AudioInput) -> bytes:
    if isinstance(audio, (bytes, bytearray)):
        return bytes(audio)
    from pathlib import Path
    return Path(audio).read_bytes()

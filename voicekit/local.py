"""Local (free, private) adapters. Optional dependencies, imported lazily:

    pip install faster-whisper   # STT, CTranslate2 Whisper (1.2.1 on PyPI, Nov 2026)
    pip install piper-tts        # TTS, ONNX voices (1.8.0 on PyPI, Nov 2026; GPL-3.0)

Hebrew, honestly (checked November 2026):
- STT: ivrit.ai publishes Hebrew fine-tunes of Whisper in faster-whisper format, e.g.
  "ivrit-ai/whisper-large-v3-turbo-ct2" (Apache-2.0; ~295 h crowd-transcribed + ~93 h
  professional Hebrew audio). The model card gives no WER figure: measure it yourself with
  voicekit.text.wer on your own recordings. faster-whisper returns per-word timestamps and a
  per-word probability (word_timestamps=True), the best free signal for pronunciation
  feedback. A large-v3-turbo model wants a GPU for real-time use; on a laptop CPU try
  compute_type="int8" and expect seconds per sentence.
- TTS: Piper has ONE Hebrew voice, he_IL-saspeech-medium (single speaker, 22.05 kHz,
  trained on OpenSLR 134, voice repo MIT; check the dataset's own license before you ship).
  Piper 1.6+ phonemizes Hebrew with a bundled Nakdimon diacritizer plus rule-based G2P,
  because unvocalized Hebrew is ambiguous. We tested the phonemizer offline (it read
  "לקנות" as liknot, correctly) but could not download the voice in our sandbox, so listen
  to it before you rely on it. Phonikud (phonikud.github.io, 2025) is a research Hebrew G2P
  with small local TTS models worth evaluating for F2.
"""

from __future__ import annotations

import io
import time
from typing import Iterator, Optional

from .audio import pcm_to_wav
from .ports import AudioInput
from .types import Speech, Transcript, Word

HEBREW_STT_MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"


class FasterWhisperSTT:
    name = "faster-whisper"

    def __init__(self, model: str = HEBREW_STT_MODEL, *, device: str = "auto", compute_type: str = "default",
                 beam_size: int = 5, vad_filter: bool = True):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("pip install faster-whisper (see labs/21-multimodal/requirements.txt)") from exc
        self.model_name, self.beam_size, self.vad_filter = model, beam_size, vad_filter
        self.model = WhisperModel(model, device=device, compute_type=compute_type)

    def transcribe(self, audio: AudioInput, *, language: Optional[str] = None, prompt: Optional[str] = None,
                   word_timestamps: bool = False, filename: str = "audio.wav") -> Transcript:
        src = io.BytesIO(audio) if isinstance(audio, (bytes, bytearray)) else audio
        t0 = time.perf_counter()
        segments, info = self.model.transcribe(src, language=language, initial_prompt=prompt,
                                               word_timestamps=word_timestamps, beam_size=self.beam_size,
                                               vad_filter=self.vad_filter)
        segments = list(segments)  # the generator does the work: consume it inside the timer
        words = [Word(w.word.strip(), w.start, w.end, w.probability)
                 for s in segments for w in (s.words or [])]
        text = " ".join(s.text.strip() for s in segments)
        return Transcript(text, info.language, words, info.duration, "local", self.model_name,
                          time.perf_counter() - t0, 0.0, None)


class PiperTTS:
    name = "piper"

    def __init__(self, model_path: str = "he_IL-saspeech-medium.onnx", *, length_scale: Optional[float] = None):
        """model_path: the .onnx voice (its .onnx.json config next to it). Download with
        `python -m piper.download_voices he_IL-saspeech-medium`. length_scale > 1 speaks
        slower, which helps learners."""
        try:
            from piper import PiperVoice, SynthesisConfig
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("pip install piper-tts (see labs/21-multimodal/requirements.txt)") from exc
        self.voice = PiperVoice.load(model_path)
        self.syn = SynthesisConfig(length_scale=length_scale)
        self.model_name = model_path

    def stream(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
               instructions: Optional[str] = None, format: str = "pcm") -> Iterator[bytes]:
        for chunk in self.voice.synthesize(text, syn_config=self.syn):  # one chunk per sentence
            yield chunk.audio_int16_bytes

    def synthesize(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
                   instructions: Optional[str] = None, format: str = "wav") -> Speech:
        t0 = time.perf_counter()
        first, chunks = None, []
        for c in self.stream(text):
            first = first if first is not None else time.perf_counter() - t0
            chunks.append(c)
        pcm = b"".join(chunks)
        rate = self.voice.config.sample_rate
        audio = pcm_to_wav(pcm, rate) if format == "wav" else pcm
        return Speech(audio, "wav" if format == "wav" else "pcm", rate, len(pcm) / 2 / rate, "local",
                      self.model_name, "saspeech", time.perf_counter() - t0, first, 0.0)


__all__ = ["FasterWhisperSTT", "PiperTTS", "HEBREW_STT_MODEL"]

"""voicekit: speech-to-text and text-to-speech behind two small ports (lesson 21).

Built for the course's final project F2, a spoken-Hebrew tutor for Arabic-speaking
high-school students, so Hebrew is a first-class concern: a language parameter on every
call, per-word timestamps and confidence where an engine gives them, Hebrew-aware WER,
and honest notes on what pronunciation feedback can and cannot be built from a transcript.

    from voicekit import FakeSTT, FakeTTS, VoicePipeline, wer
    from voicekit.openai_audio import OpenAITranscriber, OpenAISpeech   # cloud
    from voicekit.local import FasterWhisperSTT, PiperTTS               # local, optional deps

See voicekit/README.md.
"""

from .fake import FakeSTT, FakeTTS
from .pipeline import TurnResult, VoicePipeline, split_sentences
from .ports import STT, TTS
from .pronounce import ReadingFeedback, reading_feedback
from .text import ErrorRate, align, cer, normalize_hebrew, wer
from .types import Speech, Transcript, Word

__all__ = ["STT", "TTS", "FakeSTT", "FakeTTS", "VoicePipeline", "TurnResult", "split_sentences", "Speech",
           "Transcript", "Word", "wer", "cer", "align", "normalize_hebrew", "ErrorRate", "reading_feedback",
           "ReadingFeedback"]

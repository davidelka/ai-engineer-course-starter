"""OpenAI speech adapters over raw HTTP (httpx), like llmkit: no SDK hides the request.

Checked against developers.openai.com in November 2026:

Speech to text, POST /v1/audio/transcriptions (multipart form):
- models: gpt-transcribe (recommended, $0.0045/min, multilingual with code-switching,
  `languages` list instead of `language`, `keywords`, streaming), gpt-4o-transcribe
  ($0.006/min), gpt-4o-mini-transcribe ($0.003/min), whisper-1 ($0.006/min). whisper-1 and
  the gpt-4o family are deprecated, shutdown 2027-02-26.
- per-word timestamps: ONLY whisper-1 (response_format=verbose_json,
  timestamp_granularities[]=word). Token logprobs (a confidence signal): only
  gpt-4o-transcribe / gpt-4o-mini-transcribe with include[]=logprobs and json output.
  gpt-transcribe documents neither. For per-word timing AND confidence after Feb 2027, run
  faster-whisper locally (voicekit.local).
- 25 MB per file; mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm, flac.

Text to speech, POST /v1/audio/speech (JSON in, audio bytes out, chunked streaming):
- gpt-4o-mini-tts (instructions control tone/accent/speed; ~$0.015 per audio minute:
  $0.60/M text tokens in, $12/M audio tokens out), tts-1 ($15/M chars), tts-1-hd ($30/M).
- ALL THREE shut down on 2027-01-06. The replacement OpenAI names is gpt-realtime-2.1-mini
  over the Realtime API (WebSocket/WebRTC), which does not serve /v1/audio/speech. So this
  adapter has a short life; the TTS port is exactly what lets F2 swap it out.
- voices: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin,
  cedar (marin / cedar recommended). Voices are tuned for English; Hebrew input works
  (the language list follows Whisper's) but listen before you trust the accent.
- formats: mp3 (default), opus, aac, flac, wav, pcm (24 kHz 16-bit mono, no header).
  wav or pcm give the fastest first byte.
"""

from __future__ import annotations

import json
import math
import os
import time
from typing import Iterator, Optional

import httpx

from llmkit.sse import iter_sse

from .audio import duration_of
from .ports import AudioInput, read_audio
from .types import Speech, Transcript, Word

BASE_URL = "https://api.openai.com"
STT_PRICE_PER_MIN = {"gpt-transcribe": 0.0045, "gpt-4o-transcribe": 0.006, "gpt-4o-mini-transcribe": 0.003,
                     "whisper-1": 0.006}
TTS_PRICE = {"gpt-4o-mini-tts": ("minute", 0.015), "tts-1": ("char", 15 / 1e6), "tts-1-hd": ("char", 30 / 1e6)}
SHUTDOWN = {"whisper-1": "2027-02-26", "gpt-4o-transcribe": "2027-02-26", "gpt-4o-mini-transcribe": "2027-02-26",
            "gpt-4o-mini-tts": "2027-01-06", "tts-1": "2027-01-06", "tts-1-hd": "2027-01-06"}
LOGPROB_MODELS = ("gpt-4o-transcribe", "gpt-4o-mini-transcribe")
MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4", "webm": "audio/webm", "ogg": "audio/ogg",
        "flac": "audio/flac", "mp4": "audio/mp4"}


class VoiceError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def _key(api_key: Optional[str]) -> str:
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise VoiceError("no API key: set OPENAI_API_KEY in .env")
    return key


def _raise_for(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text[:300])
        except (json.JSONDecodeError, AttributeError):
            msg = resp.text[:300]
        raise VoiceError(f"OpenAI {resp.status_code}: {msg}", resp.status_code)


def words_from_logprobs(logprobs: list[dict]) -> list[Word]:
    """Token logprobs -> words with a confidence. A new word starts at a token that begins
    with whitespace; a word's confidence is exp(sum of its tokens' logprobs), the probability
    the model gave that exact spelling. No timestamps: these models do not return them."""
    words: list[Word] = []
    cur, lp = "", 0.0
    for t in logprobs or []:
        tok = t.get("token", "")
        if tok[:1].isspace() and cur.strip():
            words.append(Word(cur.strip(), confidence=math.exp(lp)))
            cur, lp = "", 0.0
        cur += tok
        lp += float(t.get("logprob", 0.0))
    if cur.strip():
        words.append(Word(cur.strip(), confidence=math.exp(lp)))
    return words


class OpenAITranscriber:
    """STT adapter. logprobs=True asks gpt-4o(-mini)-transcribe for token logprobs, turned
    into per-word confidence."""

    name = "openai-stt"

    def __init__(self, model: str = "gpt-transcribe", *, api_key: Optional[str] = None, base_url: str = BASE_URL,
                 logprobs: bool = False, http: Optional[httpx.Client] = None, timeout: float = 120.0):
        self.model, self.base_url, self.logprobs = model, base_url.rstrip("/"), logprobs
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=timeout)

    def _form(self, language: Optional[str], prompt: Optional[str], word_timestamps: bool, stream: bool) -> dict:
        if word_timestamps and self.model != "whisper-1":
            raise ValueError("per-word timestamps are documented only for whisper-1 (shutdown 2027-02-26); "
                             "use OpenAITranscriber('whisper-1') or voicekit.local.FasterWhisperSTT")
        if self.logprobs and self.model not in LOGPROB_MODELS:
            raise ValueError(f"logprobs are documented only for {', '.join(LOGPROB_MODELS)}")
        form: dict = {"model": self.model}
        if language:
            # gpt-transcribe takes a list of possible languages and rejects the singular field
            if self.model == "gpt-transcribe":
                form["languages[]"] = [language]
            else:
                form["language"] = language
        if prompt:
            form["prompt"] = prompt
        if word_timestamps:
            form["response_format"] = "verbose_json"
            form["timestamp_granularities[]"] = ["word"]
        else:
            form["response_format"] = "json"
        if self.logprobs:
            form["include[]"] = ["logprobs"]
        if stream:
            form["stream"] = "true"
        return form

    def _files(self, data: bytes, filename: str) -> dict:
        ext = filename.rsplit(".", 1)[-1].lower()
        return {"file": (filename, data, MIME.get(ext, "application/octet-stream"))}

    def transcribe(self, audio: AudioInput, *, language: Optional[str] = None, prompt: Optional[str] = None,
                   word_timestamps: bool = False, filename: str = "audio.wav") -> Transcript:
        data = read_audio(audio)
        if len(data) > 25 * 1024 * 1024:
            raise ValueError("audio is above 25 MB, the documented per-file limit: split it")
        form = self._form(language, prompt, word_timestamps, stream=False)
        t0 = time.perf_counter()
        resp = self.http.post(self.base_url + "/v1/audio/transcriptions", data=form,
                              files=self._files(data, filename),
                              headers={"authorization": f"Bearer {_key(self.api_key)}"})
        latency = time.perf_counter() - t0
        _raise_for(resp)
        body = resp.json()
        words: list[Word] = []
        if body.get("words"):
            words = [Word(w.get("word", "").strip(), w.get("start"), w.get("end")) for w in body["words"]]
        elif body.get("logprobs"):
            words = words_from_logprobs(body["logprobs"])
        langs = body.get("languages") or []
        lang = body.get("language") or (langs[0].get("code") if langs and isinstance(langs[0], dict) else None)
        usage = body.get("usage") or {}
        dur = body.get("duration") or (usage.get("seconds") if usage.get("type") == "duration" else None)
        dur = dur or duration_of(data)
        price = STT_PRICE_PER_MIN.get(self.model)
        cost = None if (price is None or dur is None) else price * dur / 60
        return Transcript(body.get("text", ""), lang or language, words, dur, "openai", self.model, latency, cost, body)

    def stream(self, audio: AudioInput, *, language: Optional[str] = None, prompt: Optional[str] = None,
               filename: str = "audio.wav") -> Iterator[str]:
        """Text deltas as the file is transcribed (stream=true; not for whisper-1)."""
        if self.model == "whisper-1":
            raise ValueError("whisper-1 ignores stream=true")
        data = read_audio(audio)
        form = self._form(language, prompt, False, stream=True)
        with self.http.stream("POST", self.base_url + "/v1/audio/transcriptions", data=form,
                              files=self._files(data, filename),
                              headers={"authorization": f"Bearer {_key(self.api_key)}"}) as resp:
            if resp.status_code >= 400:
                resp.read()
                _raise_for(resp)
            for ev in iter_sse(resp.iter_lines()):
                if not ev.data or ev.data == "[DONE]":
                    continue
                obj = json.loads(ev.data)
                if obj.get("type") == "transcript.text.delta":
                    yield obj.get("delta", "")


class OpenAISpeech:
    """TTS adapter for /v1/audio/speech. Shutdown of all its models: 2027-01-06 (see module doc)."""

    name = "openai-tts"

    def __init__(self, model: str = "gpt-4o-mini-tts", voice: str = "marin", *, api_key: Optional[str] = None,
                 base_url: str = BASE_URL, http: Optional[httpx.Client] = None, timeout: float = 120.0):
        self.model, self.voice, self.base_url = model, voice, base_url.rstrip("/")
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=timeout)
        self.shutdown = SHUTDOWN.get(model)

    def _body(self, text, voice, instructions, format) -> dict:
        if len(text) > 4096:
            raise ValueError("input above 4096 characters: split by sentence (and stream)")
        body = {"model": self.model, "input": text, "voice": voice or self.voice, "response_format": format}
        if instructions and self.model.startswith("gpt-"):
            body["instructions"] = instructions
        return body

    def stream(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
               instructions: Optional[str] = None, format: str = "pcm") -> Iterator[bytes]:
        """language is not a parameter of this API: the model reads the language from the
        text. Put guidance like "Speak slowly, in clear Israeli Hebrew" in instructions."""
        with self.http.stream("POST", self.base_url + "/v1/audio/speech",
                              json=self._body(text, voice, instructions, format),
                              headers={"authorization": f"Bearer {_key(self.api_key)}"}) as resp:
            if resp.status_code >= 400:
                resp.read()
                _raise_for(resp)
            yield from resp.iter_bytes()

    def synthesize(self, text: str, *, voice: Optional[str] = None, language: Optional[str] = None,
                   instructions: Optional[str] = None, format: str = "wav") -> Speech:
        t0 = time.perf_counter()
        first = None
        chunks = []
        for c in self.stream(text, voice=voice, instructions=instructions, format=format):
            if c and first is None:
                first = time.perf_counter() - t0
            chunks.append(c)
        audio = b"".join(chunks)
        dur = duration_of(audio, format, 24_000)
        unit, price = TTS_PRICE.get(self.model, ("", 0.0))
        cost = (price * dur / 60 if dur else None) if unit == "minute" else (price * len(text) if unit else None)
        return Speech(audio, format, 24_000, dur, "openai", self.model, voice or self.voice,
                      time.perf_counter() - t0, first, cost)

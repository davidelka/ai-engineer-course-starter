# voicekit (lesson 21, final project F2)

Speech-to-text and text-to-speech behind two ports, with adapters you can swap. Built for F2, a
spoken-Hebrew tutor for Arabic-speaking high-school students. Checked November 2026.

## Ports (voicekit/ports.py)

- `STT.transcribe(audio, *, language=None, prompt=None, word_timestamps=False, filename="audio.wav") -> Transcript`
- `TTS.synthesize(text, *, voice=None, language=None, instructions=None, format="wav") -> Speech`
  and `TTS.stream(...) -> Iterator[bytes]` (play before synthesis ends).
- `Transcript(text, language, words: [Word(text, start, end, confidence)], duration_s, provider, model,
  latency_s, cost_usd, raw)`, `Speech(audio, format, sample_rate, duration_s, ..., latency_s, ttfb_s, cost_usd)`.

Always pass `language="he"` when you know it. For learners with an Arabic accent, automatic language
detection can decide the sentence is Arabic; the hint fixes that and lowers latency.

## Adapters

- `FakeSTT`, `FakeTTS` (voicekit/fake.py): offline and deterministic. FakeTTS writes a real WAV
  whose length follows the text and hides the text inside it; FakeSTT reads it back and applies
  errors you choose (`error_rate` homophone spellings such as ת/ט, `substitutions` to simulate an
  accent, `latency_s` + `rtf` for timing).
- `OpenAITranscriber(model="gpt-transcribe")` (voicekit/openai_audio.py), `/v1/audio/transcriptions`:
  - gpt-transcribe: $0.0045/min, recommended, `languages` list, `keywords`, streaming; no word
    timestamps or logprobs documented.
  - gpt-4o-transcribe ($0.006/min), gpt-4o-mini-transcribe ($0.003/min): `logprobs=True` gives
    per-word confidence. whisper-1 ($0.006/min): the only one with per-word timestamps. All three
    shut down on 2027-02-26.
  - `.stream()` yields text deltas (not whisper-1). 25 MB per file.
- `OpenAISpeech(model="gpt-4o-mini-tts", voice="marin")`, `/v1/audio/speech`: about $0.015 per audio
  minute, `instructions` steer tone and pace, `pcm`/`wav` give the fastest first byte. gpt-4o-mini-tts,
  tts-1 and tts-1-hd all shut down on **2027-01-06**; the replacement OpenAI names
  (gpt-realtime-2.1-mini) works only through the Realtime API. Expect to replace this adapter.
- `FasterWhisperSTT(model="ivrit-ai/whisper-large-v3-turbo-ct2")` (voicekit/local.py, `pip install
  faster-whisper`): local Hebrew fine-tune (Apache-2.0), per-word timestamps AND per-word probability.
  No published WER: measure it.
- `PiperTTS("he_IL-saspeech-medium.onnx")` (`pip install piper-tts`, GPL-3.0): the one Hebrew Piper
  voice (single speaker, medium quality). Piper 1.6+ adds niqqud with Nakdimon before phonemizing.
  The phonemizer was tested offline; the voice itself was not (download blocked in our sandbox).

## Pipeline (voicekit/pipeline.py)

`VoicePipeline(stt, llm, tts, system=..., language="he").turn(audio, streaming=True)` runs
STT -> LLM -> TTS and records a timeline (`TurnResult.events`, `.budget()`): STT time, LLM time to
first token and to the first sentence, first audio, total. In streaming mode each finished sentence
is synthesized on the main thread while the LLM keeps writing on another, so first audio arrives
after the FIRST sentence, not the whole answer.

## Evaluation (voicekit/text.py)

`normalize_hebrew` (niqqud, direction marks, maqaf, geresh/gershayim, punctuation, final letters),
`wer`, `cer`, `align`. Lab 21 exercise 5 has you write `normalize_hebrew` and `wer` yourself.

## Pronunciation feedback (voicekit/pronounce.py)

`reading_feedback(reference, transcript)` aligns a known sentence with what was heard and marks each
word ok / heard_as / missing / unsure (low confidence). It catches skipped words and clear
substitutions. It cannot grade pronunciation: a good recognizer "corrects" small mistakes to the
intended word, and confidence also drops for noise and rare words. Real assessment compares phonemes
(expected phonemes from a Hebrew G2P such as Phonikud, recognized phonemes from a phoneme model).
Azure's Pronunciation Assessment lists 33 locales; we did not find Hebrew among them in November 2026,
and phoneme-level output is documented only for en-US (zh-CN with SAPI). Verify before relying on it.

## Realtime speech-to-speech (notes; voicekit does not depend on it)

- OpenAI Realtime API: GA (the beta header `OpenAI-Beta: realtime=v1` is gone), WebRTC in the browser,
  WebSocket on servers, SIP for phones. Models: gpt-realtime-2.1 ($32/M audio in, $64/M out) and
  gpt-realtime-2.1-mini ($10 / $20). Live transcription: gpt-live-transcribe ($0.017/min).
- Gemini Live API: gemini-3.8-live is GA (September 2026); the preview Live and TTS models retire on
  2026-11-17 (per a developer summary of Google's deprecation page). 16 kHz PCM in, 24 kHz out;
  audio-only sessions up to 15 minutes.
- Why the course still builds the cascade (STT -> LLM -> TTS) first: every stage is visible, testable
  and swappable; you get the transcript to grade; you pick the best Hebrew STT and the best Hebrew
  voice separately. Speech-to-speech wins on latency and prosody, but hides the text you need for
  feedback and ties you to one vendor's Hebrew.

"""Exercise 6: a spoken-Hebrew round trip with voicekit: TTS -> STT -> WER -> LLM -> TTS.

    python labs/21-multimodal/voice_roundtrip.py                  # free: fake STT/TTS + mockllm
    python labs/21-multimodal/voice_roundtrip.py --live           # OpenAI TTS + STT, Claude Haiku 5.5 (~1 cent)
    python labs/21-multimodal/voice_roundtrip.py --live --stt-model whisper-1 --words      # per-word timestamps
    python labs/21-multimodal/voice_roundtrip.py --live --stt-model gpt-4o-mini-transcribe --confidence
    python labs/21-multimodal/voice_roundtrip.py --stt local      # faster-whisper + ivrit.ai (pip install faster-whisper)
    python labs/21-multimodal/voice_roundtrip.py --tts piper --piper-model he_IL-saspeech-medium.onnx

The "student" sentence is synthesized (we have no recording of a real student), transcribed,
scored with WER against the sentence, given reading feedback, answered by a tutor LLM, and the
answer is synthesized again. Audio files land in results/ so you can LISTEN to them: the
Hebrew accent of the TTS voice is part of the evaluation, and no number captures it.
"""

from __future__ import annotations

import argparse
import time

import _lab  # noqa: F401
from _lab import DEFAULT_MODEL, RESULTS, ROOT, make_llm
from llmkit import load_dotenv
from voicekit import FakeSTT, FakeTTS, reading_feedback, wer

SENTENCE = "שלום, אני רוצה לקנות כרטיס לאוטובוס לתל אביב, בבקשה."
TUTOR = ("You are a friendly spoken-Hebrew tutor for Arabic-speaking high-school students in Israel. "
         "The student just said the sentence below (as transcribed). Reply in simple, modern Hebrew, "
         "at most two short sentences: confirm what they said, then ask one easy follow-up question. "
         "No niqqud, no transliteration.")
INSTRUCTIONS = "Speak slowly and clearly, in standard Israeli Hebrew, like a patient teacher."


def make_stt(kind: str, model: str, confidence: bool):
    if kind == "fake":
        # what an accent might make the recognizer hear: /p/ said as /b/ is not in this sentence,
        # so we use the homophone spelling ק for כ in "כרטיס", plus 10% random spelling errors
        return FakeSTT(error_rate=0.1, seed=4, substitutions={"כרטיס": "קרטיס"}, latency_s=0.3)
    if kind == "openai":
        from voicekit.openai_audio import OpenAITranscriber
        return OpenAITranscriber(model, logprobs=confidence)
    from voicekit.local import FasterWhisperSTT
    return FasterWhisperSTT(compute_type="int8")


def make_tts(kind: str, piper_model: str):
    if kind == "fake":
        return FakeTTS(ttfb_s=0.2, rtf=0.05)
    if kind == "openai":
        from voicekit.openai_audio import OpenAISpeech
        tts = OpenAISpeech("gpt-4o-mini-tts", "marin")
        print(f"note: {tts.model} shuts down on {tts.shutdown} (see voicekit/README.md)")
        return tts
    from voicekit.local import PiperTTS
    return PiperTTS(piper_model, length_scale=1.15)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="shortcut: --stt openai --tts openai --model Claude")
    ap.add_argument("--stt", choices=["fake", "openai", "local"])
    ap.add_argument("--tts", choices=["fake", "openai", "piper"])
    ap.add_argument("--model", help="LLM; default mock, or Claude Haiku 5.5 with --live")
    ap.add_argument("--stt-model", default="gpt-transcribe")
    ap.add_argument("--words", action="store_true", help="per-word timestamps (whisper-1 or local)")
    ap.add_argument("--confidence", action="store_true", help="per-word confidence (gpt-4o(-mini)-transcribe logprobs)")
    ap.add_argument("--piper-model", default="he_IL-saspeech-medium.onnx")
    ap.add_argument("--sentence", default=SENTENCE)
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    stt_kind = a.stt or ("openai" if a.live else "fake")
    tts_kind = a.tts or ("openai" if a.live else "fake")
    model = a.model or (DEFAULT_MODEL if a.live else "mock")
    stt, tts = make_stt(stt_kind, a.stt_model, a.confidence), make_tts(tts_kind, a.piper_model)
    llm = make_llm(model, {"reply": "מצוין! אמרת שאתה רוצה כרטיס לתל אביב. באיזו שעה אתה רוצה לנסוע?"}
                   if model == "mock" else None)
    total = 0.0

    print(f"1) TTS ({tts.name}): the 'student' says: {a.sentence}")
    student = tts.synthesize(a.sentence, language="he", instructions=INSTRUCTIONS, format="wav")
    (RESULTS / "student.wav").write_bytes(student.audio)
    total += student.cost_usd or 0
    print(f"   {student.duration_s or 0:.1f}s of audio, first byte after {student.ttfb_s or 0:.2f}s, "
          f"total {student.latency_s:.2f}s, ${student.cost_usd or 0:.5f} -> results/student.wav")

    print(f"\n2) STT ({stt.name} {getattr(stt, 'model', '')}), language='he'")
    t0 = time.perf_counter()
    tr = stt.transcribe(student.audio, language="he", word_timestamps=a.words, filename="student.wav")
    total += tr.cost_usd or 0
    print(f"   heard: {tr.text}\n   {time.perf_counter() - t0:.2f}s, ${tr.cost_usd or 0:.5f}, language={tr.language}")
    for w in tr.words[:20]:
        ts = f"{w.start:5.2f}-{w.end:5.2f}s " if w.start is not None else ""
        cf = f"confidence {w.confidence:.2f}" if w.confidence is not None else ""
        print(f"      {ts}{w.text}  {cf}")

    score = wer(a.sentence, tr.text)
    raw = wer(a.sentence, tr.text, normalize=None)
    print(f"\n3) WER {score.rate:.2f} after Hebrew normalization (raw {raw.rate:.2f}): "
          f"S={score.substitutions} D={score.deletions} I={score.insertions}")
    print("   reading feedback:")
    for line in reading_feedback(a.sentence, tr).lines():
        print("      " + line)

    print(f"\n4) tutor reply ({model})")
    r = llm.complete(tr.text, system=TUTOR, max_tokens=150)
    total += r.cost_usd or 0
    print(f"   {r.text}\n   {r.latency_s:.2f}s, ${r.cost_usd or 0:.5f}")

    print(f"\n5) TTS of the reply ({tts.name})")
    reply = tts.synthesize(r.text, language="he", instructions=INSTRUCTIONS, format="wav")
    (RESULTS / "tutor.wav").write_bytes(reply.audio)
    total += reply.cost_usd or 0
    print(f"   {reply.duration_s or 0:.1f}s of audio, first byte after {reply.ttfb_s or 0:.2f}s -> results/tutor.wav")
    print(f"\ntotal cost of the round trip: ${total:.4f}")


if __name__ == "__main__":
    main()

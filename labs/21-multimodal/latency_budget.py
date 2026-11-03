"""Exercise 7: the latency budget of one voice turn, sequential vs streaming.

    python labs/21-multimodal/latency_budget.py                 # free: fakes + mockllm with realistic delays
    python labs/21-multimodal/latency_budget.py --llm-ttft 1.2  # what a slower model does to the budget
    python labs/21-multimodal/latency_budget.py --live          # OpenAI STT/TTS + Claude Haiku 5.5, 3 turns (~3 cents)

"First audio" is the number a user feels: the time from the moment they stop talking until
they hear the first syllable of the answer. Conversation research puts natural turn gaps at
a few hundred milliseconds; voice agents usually aim for under about one second. The script
measures every stage with wall-clock time through the real voicekit pipeline, prints the
median of N turns, and draws the timeline of the last turn.

Offline delays (defaults, change them with the flags): STT 0.25s + 0.05s per second of audio,
LLM time to first token 0.5s then 60 tokens/s, TTS first byte 0.25s, synthesis at 10x real time.
"""

from __future__ import annotations

import argparse
import statistics

import _lab  # noqa: F401
from _lab import DEFAULT_MODEL, ROOT, make_llm
from llmkit import load_dotenv
from voicekit import FakeSTT, FakeTTS, VoicePipeline

STUDENT = "שלום, אני רוצה לקנות כרטיס לאוטובוס לתל אביב, בבקשה."
REPLY = ("מצוין, אמרת את זה יפה מאוד. עכשיו בוא ננסה משפט קצת יותר ארוך. "
         "תגיד לי: באיזו שעה יוצא האוטובוס הבא לתל אביב? ואם אתה לא בטוח, תשאל אותי.")
SYSTEM = ("You are a friendly spoken-Hebrew tutor for Arabic-speaking high-school students. Answer in simple "
          "Hebrew, three short sentences.")


def bar(t0: float, t1: float, scale: float, width: int = 60, ch: str = "#") -> str:
    a, b = int(t0 * scale), max(int(t0 * scale) + 1, int(t1 * scale))
    return " " * a + ch * (b - a) + " " * max(0, width - b)


def timeline(res) -> None:
    ev = {(e.stage, e.what): e.t for e in res.events}
    end = max(e.t for e in res.events) or 1
    scale = 60 / end
    print(f"   timeline ({res.mode}), 60 columns = {end:.2f}s, from the end of the user's speech:")
    print(f"   STT  |{bar(0, ev[('stt', 'done')], scale)}| {ev[('stt', 'done')]:.2f}s")
    print(f"   LLM  |{bar(ev[('llm', 'start')], ev[('llm', 'done')], scale)}| first token "
          f"{ev.get(('llm', 'first_token'), 0):.2f}s, first sentence {ev.get(('llm', 'first_sentence'), 0):.2f}s")
    print(f"   TTS  |{bar(ev.get(('tts', 'first_audio'), end), ev[('tts', 'done')], scale, ch='~')}| first audio "
          f"{ev.get(('tts', 'first_audio'), 0):.2f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--stt-latency", type=float, default=0.25)
    ap.add_argument("--llm-ttft", type=float, default=0.5)
    ap.add_argument("--llm-tps", type=float, default=60)
    ap.add_argument("--tts-ttfb", type=float, default=0.25)
    ap.add_argument("--budget", type=float, default=1.0, help="target for first audio, seconds")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    student_audio = FakeTTS().synthesize(STUDENT).audio
    if a.live:
        from voicekit.openai_audio import OpenAISpeech, OpenAITranscriber
        tts = OpenAISpeech("gpt-4o-mini-tts", "marin")
        student_audio = tts.synthesize(STUDENT, instructions="Speak at a normal pace.", format="wav").audio
        stt, llm = OpenAITranscriber("gpt-transcribe"), make_llm(DEFAULT_MODEL)
    else:
        stt = FakeSTT(latency_s=a.stt_latency, rtf=0.05)
        tts = FakeTTS(ttfb_s=a.tts_ttfb, rtf=0.1)
        llm = make_llm("mock", {"reply": REPLY})
        llm._mock_server.state.cfg.ttft = a.llm_ttft  # realistic pacing for this exercise
        llm._mock_server.state.cfg.tps = a.llm_tps
    pipe = VoicePipeline(stt, llm, tts, system=SYSTEM, language="he", max_tokens=200,
                         instructions="Speak clearly, in standard Israeli Hebrew.")
    cost = 0.0
    for streaming in (False, True):
        runs = []
        for _ in range(a.turns):
            res = pipe.turn(student_audio, streaming=streaming)
            runs.append(res.budget())
            cost += res.cost_usd
        mode = "streaming" if streaming else "sequential"
        print(f"\n{mode}: median of {a.turns} turns")
        for key in ("stt_s", "llm_ttft_s", "llm_first_sentence_s", "llm_total_s", "first_audio_s", "total_s"):
            vals = [r[key] for r in runs if r[key] is not None]
            if vals:
                print(f"   {key:22} {statistics.median(vals):6.2f}s")
        fa = statistics.median(r["first_audio_s"] for r in runs)
        verdict = "within" if fa <= a.budget else "OVER"
        print(f"   first audio {fa:.2f}s is {verdict} the {a.budget:.1f}s budget")
        timeline(res)
        print(f"   sentences sent to TTS: {len(res.sentences)}; heard: {res.transcript.text[:60]}")
    if a.live:
        print(f"\nlive cost (estimate): ${cost:.4f}")


if __name__ == "__main__":
    main()

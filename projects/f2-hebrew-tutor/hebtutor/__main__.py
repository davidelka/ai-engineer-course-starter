"""Command line of the tutor. Run from projects/f2-hebrew-tutor/:

    python -m hebtutor demo                       a scripted session, text and voice turns, offline and free
    python -m hebtutor chat --scenario clinic     talk to the tutor in the terminal (TUTOR=llm for Haiku)
    python -m hebtutor content [--query ...]      corpus stats, retrieval for a query
    python -m hebtutor voice [--turns 3]          latency budget of spoken turns (FAKE_DELAYS=1 / STT=openai TTS=openai)
    python -m hebtutor eval [--misses] [--json F] the 50-utterance eval (TUTOR=llm RECORD=... to record Haiku)
    python -m hebtutor traces                     p50/p95 per span from results/traces.jsonl
    python -m hebtutor serve [--port 8080]        the API and the demo page (creates a demo class)
    python -m hebtutor purge                      delete turns older than RETENTION_DAYS
    python -m hebtutor cost                       what a class costs per month, by stage

--reference uses the reference implementations instead of your mine.py functions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import PROJECT, Settings
from .hooks import pick_hooks


def build(args, **override):
    from .content import Content
    from .store import Store
    from .service import TutorService

    s = Settings.from_env(**override)
    if getattr(args, "no_traces", False):
        s.traces = ""
    if s.traces:
        s.setup_tracing()
    hooks = pick_hooks(reference=args.reference)
    content = Content()
    store = Store(override.get("db_path", s.db_path))
    return TutorService(s, content=content, store=store, hooks=hooks)


def cmd_demo(args) -> None:
    svc = build(args, db_path=":memory:", traces=str(PROJECT / "results" / "demo_traces.jsonl"))
    Path(svc.s.traces).unlink(missing_ok=True)
    svc.s.setup_tracing()
    c = svc.create_class("כיתה י'1 (הדגמה)")
    stu = svc.join(c["class_code"], "סאלם", "m")
    student = lambda: svc.store.student(stu["student_id"])  # noqa: E731
    print(f"class {c['class_code']}, student סאלם (masculine forms), tutor={svc.s.tutor}, stt={svc.s.stt}, tts={svc.s.tts}\n")
    sess = svc.start_session(student(), "clinic", "A1")
    print(f"[{sess['scenario']['title_ar']} · {sess['scenario']['title_he']} · {sess['level']}]  goal: {sess['scenario']['goal_ar']}")
    print(f"  tutor: {sess['tutor_says']}")
    turns = ["שלום, כואב לי הבתן.", "כן, יש לי חום שלוש ימים.", "לא יש לי כרטיס מגנטי.", "ما فهمت",
             "הטלפון שלי 050-7654321", "יש לי תור לרופא בעשר."]
    for t in turns:
        r = svc.text_turn(student(), sess["session_id"], t)
        show(t, r)
    print("\n  spoken turn (fake STT/TTS: the 'audio' carries its text):")
    from voicekit import FakeTTS
    st_expected = "כמה פעמים ביום לקחת?"
    svc.practice(student(), sess["session_id"], st_expected)
    said = "כמה בעמים ביום לקחת?"
    audio = FakeTTS().synthesize(said).audio
    v = svc.audio_turn(student(), sess["session_id"], audio, filename="turn.wav")
    print(f"  heard: {v['transcript']}")
    if v.get("speaking"):
        print(f"  speaking (expected '{st_expected}'): " + ", ".join(f"{w['word']}={w['status']}" for w in v["speaking"]["words"]))
    if v.get("result"):
        show(said, v["result"], prefix="  ")
    print(f"  timeline: {v['timeline_s']}  within budget: {v['budget']['within_budget']}")
    p = svc.progress(student())
    print(f"\nprogress: points {p['points']}, level {p['level']} ({p['level_score']}), cards due tomorrow: "
          f"{len(svc.store.due_cards(stu['student_id'], __import__('datetime').date.today() + __import__('datetime').timedelta(days=1)))}")
    d = svc.store.dashboard(c["class_code"])
    print(f"teacher dashboard: {json.dumps(d['students'], ensure_ascii=False)}")
    print(f"safety events: {[(e['flag'], e['text_redacted']) for e in d['safety_events']]}")
    print(f"\ntraces: {svc.s.traces}  (python -m obskit.viewer {svc.s.traces} -o results/demo_traces.html)")


def show(text: str, r: dict, prefix: str = "") -> None:
    a = r["assessment"]
    print(f"{prefix}  student: {text}")
    if r.get("pii_redacted"):
        print(f"{prefix}    (redacted before the model: {r['pii_redacted']})")
    c = a.get("correction")
    if c:
        print(f"{prefix}    correction [{c['error_type']}]: {c['original']} -> {c['corrected']} | {c['explanation_ar']}")
    if a.get("help_ar"):
        print(f"{prefix}    help (ar): {a['help_ar']}")
    if a.get("new_vocabulary"):
        print(f"{prefix}    vocab: " + ", ".join(f"{v['he']}={v['ar']} ({v['transliteration']})" for v in a["new_vocabulary"]))
    print(f"{prefix}  tutor: {a['reply_he']}   [level {a['level_signal']}, safety {a['safety_flag']}, "
          f"+{r.get('points_earned', 0)} pts, {r['cost_usd']:.5f}$]")


def cmd_chat(args) -> None:
    svc = build(args, db_path=":memory:")
    c = svc.create_class("chat")
    stu = svc.join(c["class_code"], "student", args.addressing)
    student = lambda: svc.store.student(stu["student_id"])  # noqa: E731
    sess = svc.start_session(student(), args.scenario, args.level)
    print(f"{sess['scenario']['title_he']} ({sess['level']}). Empty line to stop.\n  tutor: {sess['tutor_says']}")
    while True:
        try:
            t = input("> ").strip()
        except EOFError:
            break
        if not t:
            break
        if args.stream:
            for ev, data in svc.stream_text_turn(student(), sess["session_id"], t):
                if ev == "sentence":
                    print(f"  ... {data['text']}")
                else:
                    show(t, data)
        else:
            show(t, svc.text_turn(student(), sess["session_id"], t))


def cmd_content(args) -> None:
    from .content import Content
    c = Content()
    print(json.dumps(c.stats(), ensure_ascii=False))
    for s in c.scenarios.values():
        print(f"  {s.id:14} {s.title_he} / {s.title_ar}  levels {','.join(s.levels)}  phrases {len(s.phrases)}  vocab {len(s.vocab_ids)}")
    if args.query:
        print(f"\nretrieve({args.scenario}, {args.level}, {args.query!r}):")
        for r in c.retrieve(args.scenario, args.level, args.query):
            print(f"  {r['score']:6.3f} {r['kind']:6} {r['level']} {r['he']} = {r['ar']}")


def cmd_voice(args) -> None:
    import statistics

    from voicekit import FakeTTS
    svc = build(args, db_path=":memory:")
    c = svc.create_class("voice")
    stu = svc.join(c["class_code"], "student", "m")
    student = lambda: svc.store.student(stu["student_id"])  # noqa: E731
    sess = svc.start_session(student(), "bus_station", "A2")
    lines = ["אני רוצה לנסוע לתל אביב, מתי יוצא האוטובוס הבא?", "אני מחכה האוטובוס כבר שני שעות.",
             "כמה עולה כרטיס לבאר שבע?", "מאיזה רציף יוצא הקו?", "תודה רבה, יום טוב."]
    tts_for_student = svc.spoken.tts if svc.s.tts == "openai" else FakeTTS()
    rows = []
    for t in lines[:args.turns]:
        audio = tts_for_student.synthesize(t, format="wav").audio
        v = svc.audio_turn(student(), sess["session_id"], audio, filename="turn.wav")
        rows.append(v["timeline_s"])
        print(f"  said: {t}\n  heard: {v['transcript']}\n  tutor: {' '.join(v['sentences'])}\n  timeline: {v['timeline_s']}  "
              f"cost ${v['cost_usd']:.5f}")
    keys = ["stt_done", "first_sentence", "first_audio", "done"]
    print("\nmedian seconds after the student stops talking: " + "  ".join(
        f"{k} {statistics.median([r[k] for r in rows if k in r]):.3f}" for k in keys if any(k in r for r in rows)))
    print(f"budget: first audio <= 1.5 s")


def cmd_eval(args) -> None:
    from .evaluate import HeuristicLevelJudge, LevelJudge, evaluate, print_report
    svc = build(args, db_path=":memory:", traces="")
    judge2 = None
    if args.llm_judge:
        from llmkit import LLM
        judge2 = LevelJudge(LLM(svc.s.llm_model))
    rep = evaluate(svc.tutor, judge=HeuristicLevelJudge(), second_judge=judge2, limit=args.limit)
    print(f"tutor: {svc.s.tutor}" + (f" ({svc.s.llm_model})" if svc.s.tutor == "llm" else ""))
    print_report(rep, misses=args.misses)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rep.to_dict(rows=True), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {args.json}")


def cmd_traces(args) -> None:
    from obskit import load_spans
    path = args.path or str(PROJECT / "results" / "traces.jsonl")
    spans = load_spans(path)
    by: dict[str, list[float]] = {}
    for s in spans:
        dur = s.get("duration_ms")
        if dur is None and s.get("end_time") and s.get("start_time"):
            dur = (s["end_time"] - s["start_time"]) / 1e6
        if dur is not None:
            by.setdefault(s["name"], []).append(dur)
    print(f"{len(spans)} spans in {path}")
    for name, xs in sorted(by.items()):
        xs.sort()
        print(f"  {name:32} n={len(xs):4}  p50 {xs[len(xs) // 2]:8.1f} ms   p95 {xs[min(len(xs) - 1, int(0.95 * len(xs)))]:8.1f} ms")


def cmd_serve(args) -> None:
    import uvicorn

    from .api import create_app
    svc = build(args)
    if args.demo_class:
        c = svc.create_class("demo")
        print(f"demo class code: {c['class_code']}   teacher token: (printed once) {c['teacher_token']}", flush=True)
    uvicorn.run(create_app(svc), host=args.host, port=args.port, log_level="info")


def cmd_purge(args) -> None:
    s = Settings.from_env()
    from .store import Store
    print(Store(s.db_path).purge(s.retention_days))


def cmd_cost(args) -> None:
    from llmkit.pricing import cost_usd
    from llmkit.types import Usage
    # One student turn with Haiku 5.5: ~1,300 input tokens (about 1,100 of them the cached static
    # rules), ~250 output tokens. Measured on the offline fake as an estimate: replace with your
    # numbers from `python -m hebtutor eval` with TUTOR=llm.
    cached = cost_usd("claude-haiku-5-5", Usage(input_tokens=1300, output_tokens=250, cached_input_tokens=1100))
    uncached = cost_usd("claude-haiku-5-5", Usage(input_tokens=1300, output_tokens=250))
    students, turns_week, weeks = args.students, args.turns, 4
    n = students * turns_week * weeks
    stt_min, tts_min = n * 4 / 60, n * 5 / 60  # ~4 s of student speech, ~5 s of tutor speech per turn
    print(f"one turn: ${uncached:.5f} uncached, ${cached:.5f} with the static prompt cached")
    print(f"{students} students x {turns_week} turns/week x 4 weeks = {n} turns/month")
    print(f"  tutor (Haiku 5.5, cached): ${n * cached:.2f}")
    print(f"  STT gpt-transcribe $0.0045/min: ${stt_min * 0.0045:.2f}   (local faster-whisper: $0)")
    print(f"  TTS gpt-4o-mini-tts ~$0.015/min: ${tts_min * 0.015:.2f}   (Piper: $0; shuts down 2027-01-06)")
    print(f"  total cloud: ${n * cached + stt_min * 0.0045 + tts_min * 0.015:.2f}/month (+ hosting: local $0, AWS see README)")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m hebtutor")
    p.add_argument("--reference", action="store_true", help="use the reference implementations, not mine.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    c = sub.add_parser("chat")
    c.add_argument("--scenario", default="clinic")
    c.add_argument("--level", default="A1")
    c.add_argument("--addressing", default="m", choices=["m", "f"])
    c.add_argument("--stream", action="store_true")
    c = sub.add_parser("content")
    c.add_argument("--query", default="")
    c.add_argument("--scenario", default="clinic")
    c.add_argument("--level", default="A2")
    c = sub.add_parser("voice")
    c.add_argument("--turns", type=int, default=3)
    c.add_argument("--no-traces", action="store_true")
    c = sub.add_parser("eval")
    c.add_argument("--misses", action="store_true")
    c.add_argument("--json", default="")
    c.add_argument("--limit", type=int, default=None)
    c.add_argument("--llm-judge", action="store_true", help="also judge level-appropriateness with LLM_MODEL")
    c = sub.add_parser("traces")
    c.add_argument("path", nargs="?", default="")
    c = sub.add_parser("serve")
    c.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    c.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    c.add_argument("--demo-class", action="store_true", help="create a class at startup and print its code")
    sub.add_parser("purge")
    c = sub.add_parser("cost")
    c.add_argument("--students", type=int, default=30)
    c.add_argument("--turns", type=int, default=40)
    args = p.parse_args(argv)
    from .hooks import MilestoneTodo
    try:
        {"demo": cmd_demo, "chat": cmd_chat, "content": cmd_content, "voice": cmd_voice, "eval": cmd_eval,
         "traces": cmd_traces, "serve": cmd_serve, "purge": cmd_purge, "cost": cmd_cost}[args.cmd](args)
    except MilestoneTodo as e:
        sys.exit(f"\n{e}")


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT.parents[1]))
    main()

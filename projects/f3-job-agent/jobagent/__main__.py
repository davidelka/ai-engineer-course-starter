"""Command line of the job agent. Run from projects/f3-job-agent/:

    python -m jobagent demo                     replay one day (3 slots) offline: digests, drafts, reports
    python -m jobagent run --slot auto          one production run for the slot that is due now
    python -m jobagent eval                     the labeled set: extraction, relevance, digests
    python -m jobagent eval --extractor llm --record      the same with Claude Haiku 5.5 (about 3 cents)
    python -m jobagent schedule --show          the schedule as APScheduler / systemd / EventBridge
    python -m jobagent schedule --run           long-running scheduler (docker compose uses this)
    python -m jobagent serve                    admin API on 127.0.0.1:8080
    python -m jobagent cost                     monthly AWS estimate for the scheduled-task deployment

--reference uses the reference implementations instead of your mine.py functions.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from . import schedule
from .config import Settings
from .pipeline import Hooks, Pipeline

def pick_hooks(reference: bool) -> Hooks:
    """Your mine.py functions (on the solutions branch, --reference forces the references)."""
    from .hooks import pick_hooks as _pick
    return _pick(reference)


def pick_due_slot(reference: bool):
    pick_hooks(reference)
    return schedule.due_slot          # runs your mine.due_slot (milestone 7)


def build_pipeline(s: Settings, hooks: Hooks, *, store=None, record: bool = False) -> Pipeline:
    from .prefs import load_prefs
    from .store import Store

    return Pipeline(sources=s.sources(), extractor=s.make_extractor(record=record), prefs=load_prefs(s.prefs_path),
                    store=store or Store(s.state_path), delivery=s.make_delivery(), drafts=s.make_drafts(),
                    hooks=hooks, results_dir=s.results_dir)


# ------------------------------------------------------------------ commands
def cmd_run(a) -> int:
    from .store import S3Folder, S3StateSync, Store

    s = Settings.from_env()
    if a.extractor:
        s.extractor = a.extractor
    sync = S3StateSync(s.s3_bucket, s.s3_key, s.state_path) if s.s3_bucket else None
    folder = S3Folder(s.s3_bucket) if s.s3_bucket else None
    if sync:
        print("state:", "downloaded" if sync.download() else "new (first run)")
    if folder and s.inbox_prefix:
        print("inbox files:", folder.download_prefix(s.inbox_prefix, s.whatsapp_dir.parent))
    store = Store(s.state_path)
    slot = a.slot
    if slot == "auto":
        slot = pick_due_slot(a.reference)(datetime.now(schedule.TZ), store.done_slots())
        if slot is None:
            print("nothing due: the latest slot already ran, or it is too late for it")
            return 0
    res = build_pipeline(s, pick_hooks(a.reference), store=store, record=a.record).run(slot, force=a.force)
    store.close()
    if res.skipped:
        print(f"{slot}: skipped ({res.reason})")
        return 0
    print(f"{slot}: {res.posts_new} new posts, {len(res.new_jobs)} new jobs, "
          f"{len(res.digest.matches) if res.digest else 0} matches, ${res.cost_usd:.4f}"
          + (f", report {res.report_path}" if res.report_path else ""))
    if folder and s.outbox_prefix and res.digest and res.receipt and res.receipt.ok:
        folder.put_text(f"{s.outbox_prefix}{slot.replace(':', '')}.txt", res.digest.text)
    if sync and res.error is None:
        sync.upload()  # raises on 412: another run wrote the state meanwhile
        print("state: uploaded")
    return 1 if res.error else 0


def cmd_demo(a) -> int:
    """Replay 1 November 2026 slot by slot, on a fresh state, from the demo source files."""
    from .store import Store

    s = Settings.from_env()
    if a.extractor:
        s.extractor = a.extractor
    s.results_dir = s.home / "results" / "demo"
    if s.results_dir.exists():
        shutil.rmtree(s.results_dir)
    s.results_dir.mkdir(parents=True)
    s.delivery, s.drafts = "file", "file"
    store = Store(s.results_dir / "state.db")
    pipe = build_pipeline(s, pick_hooks(a.reference), store=store)
    pipe.first_run_lookback = timedelta(hours=12)
    total = 0.0
    for slot in ("2026-11-01T08:30", "2026-11-01T15:00", "2026-11-01T21:00"):
        res = pipe.run(slot)
        total += res.cost_usd
        d = res.digest
        print(f"\n===== {slot} | {res.posts_new} new posts | {len(res.new_jobs)} new jobs | "
              f"{len(d.matches) if d else 0} matches | {sum(r.ok for r in res.drafts)} drafts | ${res.cost_usd:.4f}")
        if d and (a.verbose or slot.endswith("08:30")):
            print(d.text)
    again = pipe.run("2026-11-01T21:00")
    print(f"\nre-running 21:00: {'skipped, already done' if again.skipped else 'RAN AGAIN (bug!)'}")
    print(f"total cost ${total:.4f}. Digests: {s.results_dir / 'digests'} | drafts: {s.results_dir / 'drafts'} | "
          f"reports: {s.results_dir / 'runs'}")
    return 0


def cmd_eval(a) -> int:
    from .evaluate import evaluate_digests, evaluate_extractor, format_report, load_posts

    s = Settings.from_env()
    if a.extractor:
        s.extractor = a.extractor
    posts = load_posts()[: a.limit] if a.limit else load_posts()
    hooks = pick_hooks(a.reference)
    if s.extractor == "llm":
        est = len(posts) * (1800 * 0.10 + 450 * 0.50) / 1e6
        print(f"about to call {s.llm_model} on {len(posts)} posts, estimated ${est:.3f} (+ repairs)")
    ex = s.make_extractor(record=a.record)
    rep = evaluate_extractor(ex, posts, scorer=hooks.score_job)
    if not a.no_digest:
        if s.extractor == "llm" and a.record:
            rec = s.home / "data" / "recorded" / f"{s.llm_model.split(':')[-1]}.jsonl"
            from .extract import ReplayExtractor
            make = lambda: ReplayExtractor(rec)  # digest replay reuses the recording: no second bill
        else:
            make = lambda: s.make_extractor()
        rep.digest = evaluate_digests(make, posts, hooks=hooks)
    print(format_report(rep))
    if a.misses:
        print("\nMisses:")
        for m in rep.misses:
            print(" ", json.dumps(m, ensure_ascii=False))
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rep.to_dict(), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"\nwritten {a.json}")
    return 0


def cmd_schedule(a) -> int:
    if a.run:
        def tick():
            ns = argparse.Namespace(slot="auto", extractor=None, force=False, record=False, reference=a.reference)
            cmd_run(ns)
        sched = schedule.apscheduler_jobs(tick)
        print("scheduler started:", ", ".join(f"{t:%H:%M}" for t in schedule.SLOTS), schedule.TZ_NAME)
        sched.start()
        return 0
    print("Slots:", ", ".join(f"{t:%H:%M}" for t in schedule.SLOTS), f"({schedule.TZ_NAME})")
    print("\nAPScheduler:")
    for t in schedule.SLOTS:
        print(f"  CronTrigger(hour={t.hour}, minute={t.minute}, timezone='{schedule.TZ_NAME}')")
    print("\nsystemd timer ([Timer] section):")
    for line in schedule.systemd_oncalendar():
        print("  " + line)
    print("\nEventBridge Scheduler (deploy/terraform/schedule.tf):")
    for e in schedule.eventbridge_expressions():
        print(f"  {e['name']}: {e['expression']}  schedule_expression_timezone = \"{e['timezone']}\"")
    now = datetime.now(schedule.TZ)
    print(f"\nnow {now:%Y-%m-%d %H:%M} -> latest slot {schedule.slot_key(schedule.latest_slot(now))}")
    return 0


def cmd_serve(a) -> int:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(Settings.from_env()), host=a.host, port=a.port, log_level="warning")
    return 0


def cmd_cost(a) -> int:
    from deploykit.cost import DeployConfig, monthly_cost

    run_hours = a.minutes / 60 * 3 * 30  # 3 runs a day
    cfg = DeployConfig(vcpu=0.25, memory_gb=0.5, tasks_avg=run_hours / 730, alb_count=0, azs=0, task_public_ip=True,
                       secrets=0, log_gb=0.01, image_gb=0.3, alarms=0)
    c = monthly_cost(cfg)
    print(f"ECS scheduled task, 0.25 vCPU / 0.5 GB, {a.minutes} min x 3 runs a day = {run_hours:.1f} task-hours/month")
    for k, v in c["items"].items():
        if v > 0.0005:
            print(f"  {k:18s} ${v:.3f}")
    print(f"  ssm parameters     $0.000 (standard SecureString parameters have no storage charge)")
    llm = 3 * 30 * a.posts * (1800 * 0.10 + 450 * 0.50) / 1e6
    print(f"  claude haiku 5.5   ${llm:.3f} ({a.posts} new posts per run)")
    total = c["total"] + llm
    print(f"  total about        ${total:.2f} per month")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m jobagent", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reference", action="store_true", help="use the reference implementations, not mine.py (solutions branch only)")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--slot", default="auto", help="'auto' or a slot key like 2026-11-01T08:30")
    r.add_argument("--extractor", default=None)
    r.add_argument("--force", action="store_true", help="run even if the slot is done")
    r.add_argument("--record", action="store_true")
    r.set_defaults(fn=cmd_run)
    d = sub.add_parser("demo")
    d.add_argument("--extractor", default=None)
    d.add_argument("-v", "--verbose", action="store_true", help="print all three digests")
    d.set_defaults(fn=cmd_demo)
    e = sub.add_parser("eval")
    e.add_argument("--extractor", default=None, help="heuristic | llm | replay:<path>")
    e.add_argument("--record", action="store_true", help="save LLM results to data/recorded/<model>.jsonl")
    e.add_argument("--limit", type=int, default=0)
    e.add_argument("--no-digest", action="store_true")
    e.add_argument("--misses", action="store_true", help="print every wrong field")
    e.add_argument("--json", default=None)
    e.set_defaults(fn=cmd_eval)
    sc = sub.add_parser("schedule")
    sc.add_argument("--show", action="store_true")
    sc.add_argument("--run", action="store_true")
    sc.set_defaults(fn=cmd_schedule)
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8080)
    sv.set_defaults(fn=cmd_serve)
    c = sub.add_parser("cost")
    c.add_argument("--minutes", type=float, default=2.0, help="minutes per run")
    c.add_argument("--posts", type=int, default=25, help="new posts per run")
    c.set_defaults(fn=cmd_cost)
    a = p.parse_args(argv)
    from .hooks import MilestoneTodo
    try:
        return a.fn(a)
    except MilestoneTodo as e:
        sys.exit(f"\n{e}")


if __name__ == "__main__":
    sys.exit(main())

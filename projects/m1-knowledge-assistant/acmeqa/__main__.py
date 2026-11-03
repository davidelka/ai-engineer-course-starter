"""Command line: python -m acmeqa <command> [options]   (run from projects/m1-knowledge-assistant)

    ingest   [--dry-run] [--docs DIR]       incremental ingestion (manifest): added/changed/unchanged/removed
    stats                                   documents, chunks, formats, languages, classifications
    acl                                     which documents each role can see
    ask      "question" [--role R] [--json] [--context]
    demo                                    a few questions across roles and both paths
    cache-check                             two questions in a row: does the system prompt get cached?
    serve    [--port 8000]                  the API and the UI on http://127.0.0.1:8000
    eval     [--parts answers,router,acl,ablation] [--no-judge] [--limit N] [--type T] [--misses]
             [--json PATH] [--record]

Global options (before the command): --mode offline|mock|live, --embedder SPEC, --rerank SPEC,
--reference (ignore mine.py), --index DIR, --replay FILE (answers recorded with eval --record).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import PROJECT, Settings


def _settings(args) -> Settings:
    over = {}
    if args.mode:
        over["mode"] = args.mode
    if args.embedder:
        over["embedder"] = args.embedder
    if args.rerank is not None:
        over["rerank"] = args.rerank
    if args.index:
        over["index_dir"] = Path(args.index)
    if args.replay:
        over["replay_file"] = Path(args.replay)
    over["reference"] = bool(args.reference)
    if args.mode == "live" and not args.embedder:
        over["embedder"] = "e5-small"
    return Settings.from_env(**over)


def cmd_ingest(args, s: Settings) -> None:
    from .ingest import IngestJob
    job = IngestJob(s)
    rep = job.run(Path(args.docs) if args.docs else None, dry_run=args.dry_run)
    print(f"index: {s.index_path}  (embedder {s.embedder})")
    print(("dry run: " if args.dry_run else "") + str(rep))
    for kind in ("added", "changed", "removed"):
        ids = getattr(rep.plan, kind)
        if ids and len(ids) <= 12:
            print(f"  {kind}: {', '.join(ids)}")
    st = job.stats()
    print(f"documents {st.documents}, chunks {st.chunks}, embed cache {st.embed_cache or '-'}")


def cmd_stats(args, s: Settings) -> None:
    from .ingest import IngestJob
    job = IngestJob(s)
    job.ensure()
    st = job.stats()
    print(json.dumps(st.__dict__, indent=1, ensure_ascii=False))


def cmd_acl(args, s: Settings) -> None:
    from .ingest import IngestJob
    from .retrieval import ROLE_LABELS, ROLES, visible_docs
    job = IngestJob(s)
    job.ensure()
    for r in ROLES:
        vis = visible_docs(r, job.docs)
        hidden = sorted(set(job.docs) - set(vis))
        print(f"- {r} ({ROLE_LABELS[r]}): sees {len(vis)} of {len(job.docs)}")
        if hidden and len(hidden) <= 8:
            print(f"    hidden: {', '.join(hidden)}")
        elif hidden:
            print(f"    hidden: {len(hidden)} docs (everything that is not public)")


def _print_result(res, show_context: bool = False) -> None:
    r = res.route
    print(f"route: {r.get('kind')} -> {res.kind}{' (fallback)' if r.get('fallback') else ''}   matched: {r.get('matched')}")
    if res.data:
        print(f"SQL ({res.data.get('data_role')}): {res.data.get('sql')}")
        for row in res.data.get("rows", [])[:8]:
            print("   ", " | ".join(str(v) for v in row))
        for p in res.data.get("provenance", []):
            print(f"   [{p}]")
    if show_context and res.context:
        print("context:")
        for h in res.context:
            print(f"  [{h.rank}] {h.chunk.doc_id} > {h.chunk.section}  ({h.chunk.effective_date})")
    print(f"\n{res.text}\n")
    for c in res.citations:
        print(f"  [{c['n']}] {c['doc_id']} :: {c.get('section') or ''} ({c.get('effective_date') or ''}) chars {c['start']}-{c['end']}")
    if res.invalid_citations:
        print(f"  invented citations: {res.invalid_citations}")
    u = res.usage or {}
    print(f"\n{res.latency_ms} ms, ttft {res.ttft_ms} ms, tokens {u.get('input_tokens', 0)}+{u.get('output_tokens', 0)} "
          f"(cached {u.get('cached_input_tokens', 0)}), ${res.cost_usd:.5f}, trace {res.trace_id[:16]}")
    if res.error:
        print(f"ERROR: {res.error}")


def cmd_ask(args, s: Settings) -> None:
    from .assistant import Assistant
    a = Assistant(s)
    res = a.ask(args.question, args.role)
    if args.json:
        d = {k: getattr(res, k) for k in ("question", "role", "route", "kind", "text", "refused", "citations",
                                           "invalid_citations", "data", "usage", "cost_usd", "latency_ms", "trace_id")}
        print(json.dumps(d, ensure_ascii=False, indent=1, default=str))
    else:
        print(f"[{s.describe()}]")
        _print_result(res, args.context)


DEMO = [
    ("employee", "How many unused vacation days can I carry over to next year, and when do they expire?"),
    ("employee", "How long was flow-api fully unavailable on August 19, 2026?"),
    ("engineering", "How long was flow-api fully unavailable on August 19, 2026?"),
    ("support", "How many open P1 tickets do we have right now?"),
    ("contractor", "How many open P1 tickets do we have right now?"),
    ("employee", "What is this month's door code for the Berlin office?"),
]


def cmd_demo(args, s: Settings) -> None:
    from .assistant import Assistant
    a = Assistant(s)
    print(f"[{s.describe()}]  your code: {a.hooks.using}\n")
    for role, q in DEMO:
        print("=" * 100)
        print(f"{role}: {q}")
        _print_result(a.ask(q, role))


def cmd_cache_check(args, s: Settings) -> None:
    from .answer import system_tokens
    from .assistant import Assistant
    a = Assistant(s)
    print(f"[{s.describe()}] system prompt ~{system_tokens()} tokens (the cacheable prefix)")
    for q in ("What is Blue Room?", "When is billing-service frozen for deploys?"):
        res = a.ask(q, "employee")
        u = res.usage or {}
        print(f"- {q}\n    input {u.get('input_tokens', 0)}, cache write {u.get('cache_creation_tokens', 0)}, "
              f"cache read {u.get('cached_input_tokens', 0)}, ${res.cost_usd:.6f}")
    if s.mode == "offline":
        print("offline answerer: no cache fields. Run with --mode mock (python -m mockllm in another terminal) or --mode live.")


def cmd_serve(args, s: Settings) -> None:
    import uvicorn

    from .assistant import Assistant
    from .service import create_app
    a = Assistant(s)
    print(f"Acme Knowledge Assistant on http://{args.host}:{args.port}   [{s.describe()}]   your code: {a.hooks.using}")
    uvicorn.run(create_app(a), host=args.host, port=args.port, log_level="info")


def cmd_eval(args, s: Settings) -> None:
    from ragkit.acme import acme_qa

    from .assistant import Assistant
    from .evaluate import evaluate, format_report
    llm = None
    rec_path = None
    if args.record:
        if s.mode != "live":
            sys.exit("--record needs --mode live (it records real answers for free replays later)")
        from .answer import Recorder
        model = s.llm_model.split(":")[-1]
        rec_path = PROJECT / "data" / "recorded" / f"{model}.jsonl"
        if rec_path.exists():
            rec_path.unlink()
        llm = Recorder(s.make_llm(), rec_path)
    a = Assistant(s, llm=llm)
    qa = acme_qa()
    if args.type:
        qa = [q for q in qa if q.get("type") == args.type]
    if args.limit:
        qa = qa[: args.limit]
    parts = tuple(p.strip() for p in args.parts.split(",") if p.strip())

    def progress(i, n):
        if s.mode != "offline" and (i % 10 == 0 or i == n):
            print(f"  {i}/{n}", file=sys.stderr)
    rep = evaluate(a, qa, judge=not args.no_judge, parts=parts, progress=progress)
    print(format_report(rep, misses=args.misses))
    if rec_path:
        meta = {"model": s.llm_model, "embedder": s.embedder, "k": s.k, "rerank": s.rerank,
                "version_mode": s.version_mode, "questions": len(qa)}
        rec_path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1))
        print(f"recorded {rec_path} (+ .meta.json): tests/test_m9_regression_gate.py now replays it for free")
    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print(f"wrote {p}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m acmeqa", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["offline", "mock", "live"])
    ap.add_argument("--embedder")
    ap.add_argument("--rerank")
    ap.add_argument("--index")
    ap.add_argument("--replay")
    ap.add_argument("--reference", action="store_true", help="use the reference functions, not mine.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--docs")
    sub.add_parser("stats")
    sub.add_parser("acl")
    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("--role", default="employee")
    p.add_argument("--json", action="store_true")
    p.add_argument("--context", action="store_true")
    sub.add_parser("demo")
    sub.add_parser("cache-check")
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p = sub.add_parser("eval")
    p.add_argument("--parts", default="answers,router,acl,ablation")
    p.add_argument("--no-judge", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--type")
    p.add_argument("--misses", action="store_true")
    p.add_argument("--json")
    p.add_argument("--record", action="store_true")
    args = ap.parse_args(argv)
    s = _settings(args)
    {"ingest": cmd_ingest, "stats": cmd_stats, "acl": cmd_acl, "ask": cmd_ask, "demo": cmd_demo,
     "cache-check": cmd_cache_check, "serve": cmd_serve, "eval": cmd_eval}[args.cmd](args, s)


if __name__ == "__main__":
    main()

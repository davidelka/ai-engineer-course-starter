"""Command line: python -m pss <command>   (tip: alias pss="python -m pss")

    demo                         the whole flow on the sample folder, offline and free
    scan   [FOLDER]              what would be indexed and what is excluded, and why (reads nothing)
    index  [FOLDER ...]          build or update the index (incremental)
    search QUERY                 --mode hybrid|bm25|dense, -k, --json
    ask    QUESTION              --llm extractive|ollama:<model>, --cloud, --dry-run, --json
    watch                        re-index on file changes (watchdog), --poll, --debounce
    serve                        local web UI on http://127.0.0.1:8765
    dups                         near-duplicate groups
    stats                        index size, formats, embedding cache
    egress                       what was sent to the cloud, --payload
    eval                         recall@k / MRR / page@1 per mode on the golden set, answers, latency

Which index: --index-dir, else the config file (--config, $PSS_CONFIG, ~/.config/pss/config.yaml),
else the folder you indexed last (`index FOLDER` remembers it), else the sample folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ROOT = PROJECT.parents[1]
if str(ROOT) not in sys.path:          # so `python -m pss` finds ragkit, guardkit, llmkit, evalkit
    sys.path.insert(1, str(ROOT))

from . import hooks  # noqa: E402
from .config import SAMPLE, config_path, load_settings  # noqa: E402

PSS_HOME = Path(os.environ.get("PSS_HOME", Path.home() / ".local" / "share" / "pss"))


def default_index_dir(roots: list[str]) -> Path:
    key = "|".join(sorted(str(Path(r).expanduser().resolve()) for r in roots))
    slug = Path(roots[0]).expanduser().resolve().name or "root"
    return PSS_HOME / f"{slug}-{hashlib.sha1(key.encode()).hexdigest()[:8]}"


def resolve_settings(args):
    from .index import restore_settings

    s = load_settings(getattr(args, "config", None))
    explicit = config_path(getattr(args, "config", None)) is not None
    folders = getattr(args, "folders", None)
    if folders:
        s.roots = [str(Path(f).expanduser().resolve()) for f in folders]
        if args.index_dir:
            s.index_dir = args.index_dir
        elif not explicit:
            s.index_dir = str(SAMPLE.parent.parent / "state" / "sample") \
                if s.roots == [str(SAMPLE)] else str(default_index_dir(s.roots))
    elif args.index_dir:
        restore_settings(s, Path(args.index_dir))
    elif not explicit and (PSS_HOME / "last.json").exists():
        last = json.loads((PSS_HOME / "last.json").read_text())["index_dir"]
        if Path(last).exists():
            restore_settings(s, Path(last))
    elif Path(s.index_dir).exists():
        restore_settings(s, Path(s.index_dir))
    if getattr(args, "embedder", None):
        s.embedder = args.embedder
    return s


def remember(s) -> None:
    try:
        PSS_HOME.mkdir(parents=True, exist_ok=True)
        (PSS_HOME / "last.json").write_text(json.dumps({"index_dir": s.index_dir, "roots": s.roots}))
    except OSError:
        pass


def open_index(s, *, sync_if_missing: bool = True):
    from .index import PersonalIndex

    idx = PersonalIndex(s)
    if not idx.load():
        if not sync_if_missing:
            raise SystemExit(f"no index at {s.index_dir}: run `python -m pss index FOLDER` first")
        print(f"(no usable index at {s.index_dir}: indexing {', '.join(s.roots)} first)", file=sys.stderr)
        rep = idx.sync()
        print(f"  {rep.summary()}", file=sys.stderr)
    return idx


def show_notices() -> None:
    for n in hooks.notices():
        print(f"[note] {n}", file=sys.stderr)


def strip_html(s: str) -> str:
    return s.replace("<mark>", "\033[1m").replace("</mark>", "\033[0m").replace("&quot;", '"') \
        .replace("&#x27;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


# ------------------------------------------------------------------ commands
def cmd_scan(args):
    from .scan import scan

    s = resolve_settings(args)
    for root in s.roots:
        rep = scan(root, s.exclude, max_file_mb=s.max_file_mb)
        print(f"{root}: {len(rep.files)} files to index, {len(rep.skipped)} skipped {rep.reasons()}")
        if args.explain:
            for rel, why in rep.skipped:
                print(f"  - skip {rel}  ({why})")
            for e in rep.files:
                print(f"  + {e.id}")
    show_notices()


def cmd_index(args):
    s = resolve_settings(args)
    from .index import PersonalIndex

    idx = PersonalIndex(s)
    idx.load()

    def progress(n, total, fid):
        if args.verbose:
            print(f"  [{n}/{total}] {fid}", file=sys.stderr)

    rep = idx.sync(progress=progress)
    remember(s)
    print(rep.summary())
    print(f"skipped while scanning: {rep.scan.reasons() or 'nothing'}")
    for fid, ws in rep.warnings.items():
        for w in ws:
            print(f"  ! {fid}: {w}")
    st = idx.stats()
    print(f"index: {st['files']} files, {st['chunks']} chunks, {st['index_bytes'] / 1024:.0f} KB at {st['index_dir']}")
    if idx.dups:
        print(f"near-duplicates: {len(idx.dups)} groups (python -m pss dups)")
    show_notices()


def cmd_search(args):
    s = resolve_settings(args)
    idx = open_index(s)
    res = idx.search(args.query, mode=args.mode, k=args.k)
    if args.json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=1))
        return
    if res.parsed.filters:
        print(f"filters: {res.parsed.filters}   text: {res.parsed.text!r}")
    for w in res.parsed.warnings:
        print(f"  ! {w}")
    for f in res.files:
        pages = f" p.{','.join(map(str, f.pages))}" if f.pages else ""
        also = f"  (also: {', '.join(f.also)})" if f.also else ""
        print(f"{f.rank:>2}. {f.id}{pages}  [{f.format}, {f.date}]{also}")
        print(f"    {strip_html(f.snippet)}")
    print(f"({len(res.files)} files, {res.ms:.1f} ms, mode {res.mode})")
    show_notices()


def cmd_ask(args):
    from .answer import OllamaError, ask, make_local_llm
    from .privacy import PrivacyError

    s = resolve_settings(args)
    if args.llm:
        s.local_model = args.llm
    idx = open_index(s)
    try:
        llm = None if args.cloud else make_local_llm(s.local_model, s)
        a = ask(idx, args.question, llm=llm, cloud=args.cloud, dry_run=args.dry_run, mode=args.mode)
    except (PrivacyError, OllamaError) as exc:
        raise SystemExit(f"error: {exc}")
    if args.json:
        print(json.dumps(a.to_dict(), ensure_ascii=False, indent=1))
        return
    if a.dry_run:
        print(f"DRY RUN: nothing was sent. This is exactly what would go to {a.model}:")
        print(f"  sources sent: {[h.chunk.doc_id for h in a.hits]}")
        print(f"  withheld (never_send): {a.withheld or 'none'}")
        print(f"  redactions: {a.redactions or 'none'}")
        print("----- system -----\n" + a.payload["system"] + "\n----- user -----\n" + a.payload["user"])
        return
    print(a.display_text())
    print()
    for c in a.citations:
        print(f"  [{c.n}] {c.file}" + (f" p.{c.page}" if c.page else ""))
    if a.invalid_citations:
        print(f"  ! citations to missing sources: {a.invalid_citations}")
    where = f"cloud ({a.model}), cost ${a.cost_usd:.5f}, egress id {a.egress_id}" if a.where == "cloud" \
        else f"local ({a.model}), nothing left this machine"
    print(f"({where}, {a.latency_s:.1f}s)")
    if a.withheld:
        print(f"  withheld from the cloud: {a.withheld}")
    show_notices()


def cmd_watch(args):
    from .watch import watch

    s = resolve_settings(args)
    idx = open_index(s)
    print(f"watching {', '.join(s.roots)} (debounce {args.debounce}s{', polling' if args.poll else ''}). Ctrl+C to stop.")

    def on_sync(paths, rep):
        print(f"{time.strftime('%H:%M:%S')} {len(paths)} paths changed -> {rep.summary()}")

    watch(idx, debounce=args.debounce, poll=args.poll, on_sync=on_sync)


def cmd_serve(args):
    from .api import serve

    s = resolve_settings(args)
    idx = open_index(s)
    print(f"http://{args.host}:{args.port}  (index: {s.index_dir}; cloud {'enabled' if s.cloud.enabled else 'disabled'})")
    serve(idx, args.host, args.port, allow_remote=args.allow_remote)


def cmd_dups(args):
    idx = open_index(resolve_settings(args))
    if not idx.dups:
        print("no near-duplicates")
    for g in idx.dups:
        print(" ~ " + "  |  ".join(g))
    show_notices()


def cmd_stats(args):
    idx = open_index(resolve_settings(args), sync_if_missing=False)
    print(json.dumps(idx.stats(), ensure_ascii=False, indent=1))


def cmd_egress(args):
    from .privacy import EgressLog

    s = resolve_settings(args)
    log = EgressLog(s.egress_log)
    print(json.dumps(log.summary(), indent=1))
    for e in log.entries()[-args.last:]:
        if e.get("event") == "send":
            print(f"- {time.strftime('%Y-%m-%d %H:%M', time.localtime(e['ts']))} {e['model']} {e['chars']} chars "
                  f"files={e['files']} withheld={e['withheld']} redactions={e['redactions']}")
            if args.payload:
                print(e["payload"]["user"])
        else:
            print(f"    result ok={e.get('ok')} tokens={e.get('input_tokens')}/{e.get('output_tokens')} cost=${e.get('cost_usd')}")


def cmd_eval(args):
    from .evaluate import (RECORDED, build_index, eval_answers, eval_recorded, eval_retrieval, eval_settings,
                           format_report, load_golden)

    base = load_settings(args.config)
    s = eval_settings(base, embedder=args.embedder or "fake")
    golden = load_golden()
    idx, build = build_index(s)
    rep = {"embedder": s.embedder, "build": build,
           "retrieval": eval_retrieval(idx, golden, modes=args.modes.split(","))}
    if args.recorded:
        rep["llm"] = f"recorded {args.recorded}"
        rep["answers"] = eval_recorded(golden, Path(args.recorded))
    elif args.llm != "none":
        from .answer import make_local_llm

        s.local_model = args.llm
        llm = make_local_llm(args.llm, s)
        model = args.llm.split(":", 1)[-1].replace(":", "-").replace("/", "_")
        rec = RECORDED / f"{model}.jsonl" if args.record else None
        rep["llm"] = args.llm
        rep["answers"] = eval_answers(idx, golden, llm, record=rec)
        if rec:
            print(f"recorded answers to {rec}", file=sys.stderr)
    print(format_report(rep))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwritten {args.json}")
    show_notices()


def cmd_demo(args):
    import shutil
    from dataclasses import replace

    from ragkit.fake import ExtractiveAnswerer

    from .answer import ask
    from .config import PROJECT as P
    from .config import Settings
    from .index import PersonalIndex

    s = Settings()
    s.index_dir = str(P / "state" / "demo")
    if args.embedder:
        s.embedder = args.embedder
    shutil.rmtree(s.index_dir, ignore_errors=True)
    print("== 1. index the sample folder (data/sample: 45 files, Hebrew and English) ==")
    idx = PersonalIndex(s)
    rep = idx.sync()
    print(f"   {rep.summary()}")
    print(f"   skipped: {rep.scan.skipped}")
    for fid, ws in rep.warnings.items():
        print(f"   ! {fid}: {ws[0]}")
    print(f"   near-duplicate groups: {idx.dups}")
    st = idx.stats()
    print(f"   {st['files']} files, {st['chunks']} chunks, {st['index_bytes'] / 1024:.0f} KB, embedder {st['embedder']}")
    print("\n== 2. search: the same queries in three modes ==")
    for q in ["ערבות בנקאית", "type:pdf אחריות מדחס", "how much luggage can each of us take on the plane"]:
        for mode in ("bm25", "dense", "hybrid"):
            r = idx.search(q, mode=mode, k=3)
            top = ", ".join(f.id + (f" p.{f.pages[0]}" if f.pages else "") for f in r.files) or "(nothing)"
            print(f"   [{mode:<6}] {q}\n            -> {top}")
    print("\n== 3. ask (extractive stand-in: free, not a language model) ==")
    a = ask(idx, "כמה עולה הטיול השנתי?", llm=ExtractiveAnswerer())
    print(f"   {a.display_text()}")
    for c in a.citations:
        print(f"   [{c.n}] {c.file}" + (f" p.{c.page}" if c.page else ""))
    print("\n== 4. what WOULD leave the machine with --cloud (dry run, nothing is sent) ==")
    s2 = replace(s)
    s2.cloud = replace(s.cloud, enabled=True)
    idx.s = s2
    pv = ask(idx, "מתי התור לרופאה ומה צריך להביא? אפשר לחזור אליי ב-050-555-0199", cloud=True, dry_run=True)
    idx.s = s
    print(f"   sources that would be sent: {[h.chunk.doc_id for h in pv.hits]}")
    print(f"   withheld (health/ and finance/ never go to the cloud): {pv.withheld}")
    print(f"   redactions: {pv.redactions}")
    print("\nnext: python -m pss serve   (web UI)   |   python -m pss eval   (the numbers)")
    show_notices()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="pss", description="Personal Smart Search (local-first)")
    ap.add_argument("--config")
    ap.add_argument("--index-dir")
    ap.add_argument("--embedder", help="ragkit embedder spec: fake | e5-small | e5-base | bge-m3 ...")
    ap.add_argument("--reference", action="store_true", help="use the reference functions, not mine.py (solutions branch only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("demo")
    p.set_defaults(fn=cmd_demo)
    p = sub.add_parser("scan")
    p.add_argument("folders", nargs="*")
    p.add_argument("--explain", action="store_true")
    p.set_defaults(fn=cmd_scan)
    p = sub.add_parser("index")
    p.add_argument("folders", nargs="*")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_index)
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--mode", default="hybrid", choices=("hybrid", "bm25", "dense"))
    p.add_argument("-k", type=int, default=8)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_search)
    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("--llm", help="extractive | ollama:<model> (default: local_model from the config)")
    p.add_argument("--cloud", action="store_true", help="use the cloud model (needs cloud.enabled in the config)")
    p.add_argument("--dry-run", action="store_true", help="with --cloud: show exactly what would be sent")
    p.add_argument("--mode", default="hybrid", choices=("hybrid", "bm25", "dense"))
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_ask)
    p = sub.add_parser("watch")
    p.add_argument("--poll", action="store_true")
    p.add_argument("--debounce", type=float, default=2.0)
    p.set_defaults(fn=cmd_watch)
    p = sub.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--allow-remote", action="store_true")
    p.set_defaults(fn=cmd_serve)
    for name, fn in (("dups", cmd_dups), ("stats", cmd_stats)):
        sub.add_parser(name).set_defaults(fn=fn)
    p = sub.add_parser("egress")
    p.add_argument("--last", type=int, default=20)
    p.add_argument("--payload", action="store_true")
    p.set_defaults(fn=cmd_egress)
    p = sub.add_parser("eval")
    p.add_argument("--modes", default="bm25,dense,hybrid")
    p.add_argument("--llm", default="extractive", help="extractive | ollama:<model> | none")
    p.add_argument("--record", action="store_true", help="save the answers to data/recorded/<model>.jsonl")
    p.add_argument("--recorded", help="score a recording instead of calling a model")
    p.add_argument("--json")
    p.set_defaults(fn=cmd_eval)
    # --embedder works both before and after the subcommand ("pss --embedder e5-small eval"
    # and "pss eval --embedder e5-small"). SUPPRESS keeps the main parser's value when omitted.
    for name in ("eval", "index", "search", "ask", "stats"):
        sub.choices[name].add_argument("--embedder", default=argparse.SUPPRESS,
                                       help="ragkit embedder spec: fake | e5-small | e5-base | bge-m3 ...")
    args = ap.parse_args(argv)
    if not hasattr(args, "folders"):
        args.folders = None
    try:
        if args.reference:
            hooks.force_reference(True)
        args.fn(args)
    except hooks.MilestoneTodo as e:
        sys.exit(f"\n{e}")
    except RuntimeError as e:
        if "solutions branch" not in str(e):
            raise
        sys.exit(f"\n{e}")


if __name__ == "__main__":
    main()

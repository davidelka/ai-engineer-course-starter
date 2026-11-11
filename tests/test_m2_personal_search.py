"""Environment tests for midterm project M2 (projects/m2-personal-search): the reference package
`pss`, offline. No network, no keys, no paid calls, no Ollama: the cloud model is a ragkit
replay LLM (a real llmkit.LLM over httpx.MockTransport) and Ollama is an httpx.MockTransport."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "m2-personal-search"
sys.path[:0] = [str(ROOT), str(PROJECT)]
pytest.importorskip("pss._reference", reason="reference implementations live on the solutions branch")
os.environ.setdefault("PSS_HOME", tempfile.mkdtemp(prefix="pss-home-"))

from llmkit import ChatRequest, Message  # noqa: E402
from ragkit.fake import ExtractiveAnswerer  # noqa: E402
from ragkit.replay import body_text, replay_llm  # noqa: E402

from pss import hooks  # noqa: E402
from pss.answer import OllamaError, OllamaLLM, ask, build_request  # noqa: E402
from pss.config import DEFAULT_EXCLUDES, SAMPLE, Settings  # noqa: E402
from pss.evaluate import (build_index, eval_retrieval, eval_settings, format_report, grounded_rate,  # noqa: E402
                          load_golden)
from pss.extract import date_from_name, fix_pdf_text, looks_reversed, unreverse  # noqa: E402
from pss.index import PersonalIndex  # noqa: E402
from pss.privacy import EgressLog, PrivacyError, redact_for_cloud  # noqa: E402
from pss.query import parse_query, where_from  # noqa: E402
from pss.scan import is_excluded, scan  # noqa: E402
from pss.snippets import make_snippet  # noqa: E402
from pss.watch import DebouncedChanges  # noqa: E402

hooks.force_reference(True)


@pytest.fixture(scope="module")
def idx(tmp_path_factory):
    s = eval_settings(index_dir=str(tmp_path_factory.mktemp("pss-idx")), ocr="off")
    index, _ = build_index(s)
    return index


def cloud_settings(index, **kw):
    s = replace(index.s)
    s.cloud = replace(index.s.cloud, enabled=True, **kw)
    return s


# ------------------------------------------------------------------ scan and extract
def test_scan_excludes_private_and_hidden():
    rep = scan(SAMPLE, DEFAULT_EXCLUDES)
    ids = {f.id for f in rep.files}
    assert len(ids) == 43 and "home/lease-2026.pdf" in ids
    assert ("private/", "excluded: private/") in rep.skipped and (".cache/", "excluded: .*") in rep.skipped
    assert is_excluded("kids/**/x".replace("**/", ""), ["kids/**/x"]) == "kids/**/x"


def test_hebrew_visual_order_is_fixed():
    visual = '.ח"ש 12,600 ךסב תיאקנב תוברע רוסמי רכושה'
    assert looks_reversed(visual)
    assert unreverse(visual) == 'השוכר ימסור ערבות בנקאית בסך 12,600 ש"ח.'
    page = "תוריכשה תפוקת .2\n.ח\"ש 4,200 ךסב תוריכש ימד םלשי רכושה\nCheck-in from 14:00"
    fixed = fix_pdf_text(page)
    assert fixed.split("\n")[0] == "2. תקופת השכירות"           # no evidence alone: decided per page
    assert fixed.split("\n")[2] == "Check-in from 14:00"          # English lines untouched
    assert fix_pdf_text("Netﬂix") == "Netflix"


def test_dates_from_file_names():
    assert date_from_name("receipt-laptop-2026-03.html") == "2026-03-01"
    assert date_from_name("clinic-appointment-2026-11-18.pdf") == "2026-11-18"
    assert date_from_name("lease-2026.pdf") == "2026-01-01"
    assert date_from_name("notes.md") is None and date_from_name("id-12026-x") is None


# ------------------------------------------------------------------ index
def test_index_pages_dates_dups(idx):
    m = idx.manifest.files
    assert m["home/lease-2026.pdf"]["pages"] == 3 and m["home/lease-2026.pdf"]["date_source"] == "filename"
    assert {c.meta["page"] for c in idx.chunks.values() if c.doc_id == "finance/car-insurance-2026.pdf"} == {1, 2, 3}
    assert "ערבות בנקאית בסך 12,600" in idx.doc_texts()["home/lease-2026.pdf"]
    assert ["home/lease-2026 (1).pdf", "home/lease-2026.pdf"] in idx.dups and len(idx.dups) == 3
    st = idx.stats()
    assert st["files"] == 43 and st["chunks"] > 43 and st["index_bytes"] > 0


def test_incremental_sync_and_reload(tmp_path):
    root = tmp_path / "docs"
    shutil.copytree(SAMPLE / "travel", root / "travel")
    s = Settings(roots=[str(root)], index_dir=str(tmp_path / "idx"), ocr="off")
    a = PersonalIndex(s).sync()
    assert len(a.plan.added) == 5 and a.chunks_added >= 5
    b = PersonalIndex.open(s)
    assert len(b.chunks) == a.chunks_added
    os.utime(root / "travel" / "eilat-weekend-ideas.md", (1, 1))         # touched only
    (root / "travel" / "packing-list-italy.md").write_text("# רשימה\n- דרכונים\n", encoding="utf-8")
    (root / "travel" / "new-note.txt").write_text("Hotel in Florence: Rooms Hotel, check-in 15:00\n")
    r = b.sync()
    assert r.plan.added == ["travel/new-note.txt"] and r.plan.changed == ["travel/packing-list-italy.md"]
    assert r.plan.touched == ["travel/eilat-weekend-ideas.md"] and not r.plan.removed
    assert b.rank_files("Florence", mode="bm25")[0][0] == "travel/new-note.txt"
    s2 = replace(s)
    s2.chunker = "recursive:120:20"                                      # settings changed: rebuild
    assert PersonalIndex.open(s2).sync().rebuilt


# ------------------------------------------------------------------ search
def test_search_modes_filters_and_folding(idx):
    r = idx.search("ערבות בנקאית", mode="bm25", k=5)
    assert r.files[0].id == "home/lease-2026.pdf" and r.files[0].pages[0] == 2
    assert r.files[0].also == ["home/lease-2026 (1).pdf"]                # the copy is folded in
    assert "<mark>" in r.files[0].snippet
    for mode in ("bm25", "dense", "hybrid"):
        assert idx.search("check-in Old Town Rooms", mode=mode).files[0].id == "travel/rome-hotel-booking-2026-08.pdf"
    f = idx.search("folder:receipts after:2026-06")
    assert sorted(x.id for x in f.files) == ["receipts/receipt-pharmacy-2026-08.txt", "receipts/receipt-supermarket-2026-10.html"]
    assert all(x.format == "pdf" for x in idx.search("type:pdf אחריות", k=10).files)


def test_query_parser_and_where():
    p = parse_query("סוג:pdf after:2026-06 lang:he ערבות")
    assert p.text == "ערבות" and p.filters == {"type": ["pdf"], "after": "2026-06-01", "lang": "he"}
    w = where_from({"folder": ["kids"], "before": "2026-11-01"})

    class C:
        def __init__(self, fid, date):
            self.doc_id, self.meta = fid, {"file": fid, "date": date}
    assert w(C("kids/a.md", "2026-10-31")) and not w(C("kids/a.md", "2026-11-01")) and not w(C("kidsx/a.md", "2026-01-01"))


def test_snippet_highlights_hebrew_prefixes_and_escapes():
    s = make_snippet('השוכר ימסור <b>ערבות</b> ו"בערבות" נוספת', "ערבות")
    assert s.count("<mark>") == 2 and "&lt;b&gt;" in s


# ------------------------------------------------------------------ answers: local
def test_local_answer_cites_file_and_page(idx):
    a = ask(idx, "דמי שכירות לחודש", llm=ExtractiveAnswerer())
    assert a.where == "local" and not a.abstained and "4,200" in a.text
    assert a.citations and a.citations[0].file.startswith("home/lease-2026") and a.citations[0].page == 1
    assert a.invalid_citations == []
    req = build_request("q", a.hits)
    assert 'file="home/lease-2026' in req.messages[0].text and 'page="1"' in req.messages[0].text


def test_ollama_adapter_body_retry_and_errors():
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.append(body)
        if "think" in body:
            return httpx.Response(400, json={"error": "model does not support thinking"})
        return httpx.Response(200, json={"message": {"content": "<think>x</think>4,200 ש\"ח [1]"},
                                         "prompt_eval_count": 900, "eval_count": 12, "done_reason": "stop"})

    llm = OllamaLLM("qwen3.5:4b", http=httpx.Client(transport=httpx.MockTransport(handler)))
    res = llm.complete(ChatRequest(messages=[Message("user", "q")], system="sys", max_tokens=99))
    assert res.text == '4,200 ש"ח [1]' and res.usage.input_tokens == 900 and res.cost_usd == 0.0
    assert seen[0]["think"] is False and "think" not in seen[1]
    assert seen[0]["options"]["num_ctx"] == 8192 and seen[0]["messages"][0] == {"role": "system", "content": "sys"}
    gone = OllamaLLM("nope", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404, text="not found"))))
    with pytest.raises(OllamaError, match="ollama pull nope"):
        gone.complete(ChatRequest(messages=[Message("user", "q")]))


# ------------------------------------------------------------------ answers: cloud (the guarded path)
def test_cloud_is_off_by_default(idx):
    with pytest.raises(PrivacyError):
        ask(idx, "anything", cloud=True)


def test_cloud_dry_run_sends_nothing_and_shows_payload(idx, tmp_path):
    calls = []
    llm = replay_llm(lambda body: calls.append(body) or "x")
    s = cloud_settings(idx)
    s.index_dir = str(tmp_path)
    orig, idx.s = idx.s, s
    try:
        a = ask(idx, "מתי התור לרופאה? חזרו אליי ב-050-555-0199", cloud=True, dry_run=True, cloud_llm=llm)
    finally:
        idx.s = orig
    assert calls == [] and not EgressLog(s.egress_log).entries()
    assert "health/clinic-appointment-2026-11-18.pdf" in a.withheld
    assert "050-555-0199" not in a.payload["user"] and "[PHONE]" in a.payload["user"]


def test_cloud_call_withholds_redacts_and_logs_first(idx, tmp_path):
    bodies, order = [], []
    log_path = tmp_path / "egress.jsonl"

    def responder(body):
        order.append(("sent", log_path.exists() and "send" in log_path.read_text()))
        bodies.append(body)
        return "השוכר משלם 4,200 ש\"ח בחודש [1]."

    s = cloud_settings(idx, never_send=["health/", "finance/", "receipts/"])
    s.index_dir = str(tmp_path)
    orig, idx.s = idx.s, s
    try:
        a = ask(idx, "דמי שכירות לחודש, ואיפה הקבלה של המחשב? מייל david@example.org", cloud=True,
                cloud_llm=replay_llm(responder))
        a2 = ask(idx, "receipt laptop ThinkPad", cloud=True, cloud_llm=replay_llm(responder))
    finally:
        idx.s = orig
    assert order[0] == ("sent", True)                                    # logged BEFORE the request
    system, user = body_text(bodies[0])
    assert "david@example.org" not in user and "[EMAIL]" in user
    assert "050-555-01" not in user and "receipts/" not in user and "health/" not in user
    assert a.citations[0].file.startswith("home/lease-2026") and a.egress_id
    assert "receipts/receipt-laptop-2026-03.html" in a2.withheld
    entries = EgressLog(s.egress_log).entries()
    sends = [e for e in entries if e["event"] == "send"]
    assert len(sends) == 2 and sends[0]["redactions"].get("EMAIL") == 1
    assert sends[0]["payload"]["user"] == user                           # the log holds exactly what was sent
    assert [e["event"] for e in entries] == ["send", "result", "send", "result"]
    assert EgressLog(s.egress_log).summary()["calls"] == 2


def test_redact_for_cloud_reference():
    out, c = redact_for_cloud("card 4111 1111 1111 1111, IBAN IL62 0108 0000 0009 9999 999, acct 12-345-678901")
    assert out == "card [CARD], IBAN [IBAN], acct [BANK_ACCOUNT]" and c == {"CARD": 1, "IBAN": 1, "BANK_ACCOUNT": 1}


# ------------------------------------------------------------------ web API
def test_api_local_only_and_file_serving(idx):
    from fastapi.testclient import TestClient

    from pss.api import create_app

    c = TestClient(create_app(idx, llm=ExtractiveAnswerer()))
    st = c.get("/api/status").json()
    assert st["stats"]["files"] == 43 and st["privacy"]["cloud_enabled"] is False
    r = c.get("/api/search", params={"q": "type:pdf ערבות", "mode": "hybrid"}).json()
    assert r["results"][0]["id"] == "home/lease-2026.pdf" and r["filters"] == {"type": ["pdf"]}
    a = c.post("/api/ask", json={"q": "דמי שכירות לחודש"}).json()
    assert a["where"] == "local" and a["citations"]
    assert c.post("/api/ask", json={"q": "x", "cloud": True}).status_code == 403
    f = c.get("/api/file/home/lease-2026.pdf")
    assert f.status_code == 200 and f.headers["content-type"] == "application/pdf"
    assert c.get("/api/file/receipts/receipt-laptop-2026-03.html").headers["content-type"].startswith("text/plain")
    assert c.get("/api/file/private/passwords-DO-NOT-INDEX.txt").status_code == 404
    assert c.get("/api/file/../../../etc/passwd").status_code == 404
    assert c.get("/api/status", headers={"host": "evil.example"}).status_code == 403
    assert "<html" in c.get("/").text and 'dir="rtl"' in c.get("/").text


# ------------------------------------------------------------------ watcher
def test_debounce_and_excluded_events(tmp_path):
    t = [0.0]
    ch = DebouncedChanges([tmp_path], DEFAULT_EXCLUDES, debounce=2.0, clock=lambda: t[0])
    assert ch.add(str(tmp_path / "notes" / "a.md")) and not ch.add(str(tmp_path / ".git" / "index"))
    assert not ch.add(str(tmp_path / "x" / "passwords.txt")) and ch.ignored == 2
    t[0] = 1.0
    ch.add(str(tmp_path / "notes" / "a.md"))
    t[0] = 2.5
    assert not ch.due()                                                  # 1.5s since the last event
    t[0] = 3.1
    assert ch.due() and ch.take() == {"notes/a.md"} and not ch.due()


def test_watch_reindexes_a_new_file(tmp_path):
    from pss.watch import watch

    root = tmp_path / "docs"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.md").write_text("# first note\nnothing here\n")
    s = Settings(roots=[str(root)], index_dir=str(tmp_path / "idx"), ocr="off")
    index = PersonalIndex(s)
    index.sync()
    stop, done = threading.Event(), []
    th = threading.Thread(target=watch, kwargs=dict(index=index, debounce=0.3, poll=True, stop=stop,
                                                    on_sync=lambda p, r: done.append(r), tick=0.1))
    th.start()
    try:
        time.sleep(0.5)
        (root / "notes" / "boiler.md").write_text("# Boiler\nThe anode was replaced in April.\n")
        deadline = time.time() + 15
        while time.time() < deadline and not any("notes/boiler.md" in r.plan.added for r in done):
            time.sleep(0.1)
    finally:
        stop.set()
        th.join(timeout=10)
    assert any("notes/boiler.md" in r.plan.added for r in done)
    assert index.rank_files("anode", mode="bm25")[0][0] == "notes/boiler.md"


# ------------------------------------------------------------------ eval and CLI
def test_eval_report(idx):
    golden = load_golden()
    assert len(golden) == 52
    r = eval_retrieval(idx, golden, modes=("bm25", "hybrid"), kinds={"keyword", "filter"})
    assert r["modes"]["bm25"]["by_kind"]["keyword"]["recall@5"] >= 0.95
    txt = format_report({"retrieval": r})
    assert "[bm25]" in txt and "recall@5" in txt
    assert grounded_rate("The rent is 4,200 NIS. [1]", {1: "דמי שכירות בסך 4,200 ש\"ח"}) == 1.0
    assert grounded_rate("The rent is 5,000 NIS [1].", {1: "4,200"}) == 0.0


def test_cli_index_search_json(tmp_path, capsys):
    from pss.__main__ import main

    root = tmp_path / "docs"
    shutil.copytree(SAMPLE / "kids", root / "kids")
    main(["--index-dir", str(tmp_path / "idx"), "--reference", "index", str(root)])
    out = capsys.readouterr().out
    assert "added 6" in out
    main(["--index-dir", str(tmp_path / "idx"), "search", "עין עבדת", "--json"])
    res = json.loads(capsys.readouterr().out)
    assert res["results"][0]["id"] == "kids/school-trip-permission-2026-11.docx"


def test_hooks_fall_back_to_reference_until_mine_is_done():
    hooks.force_reference(False)
    try:
        fn = hooks.get("parse_query")
        mod = hooks.load_mine()
        implemented = True
        try:
            mod.parse_query("x")
        except NotImplementedError:
            implemented = False
        assert fn("type:pdf x").text == "x"
        assert hooks.using_mine("parse_query") == implemented
    finally:
        hooks.force_reference(True)

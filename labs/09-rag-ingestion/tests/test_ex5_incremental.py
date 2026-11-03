"""Exercise 5: content_hash and plan_ingest in mine.py."""

import shutil

import mine
from ragkit.acme import DOCS_DIR
from ragkit.chunking import make_chunker
from ragkit.pipeline import IngestPipeline


def test_hash_is_stable_and_short():
    h = mine.content_hash(b"hello", {"a": 1, "b": "x"})
    assert isinstance(h, str) and len(h) == 16 and int(h, 16) >= 0
    assert h == mine.content_hash(b"hello", {"b": "x", "a": 1})        # key order does not matter


def test_hash_changes_with_bytes_or_metadata():
    base = mine.content_hash(b"policy text", {"classification": "internal"})
    assert base != mine.content_hash(b"policy text!", {"classification": "internal"})
    assert base != mine.content_hash(b"policy text", {"classification": "confidential"})
    assert mine.content_hash(b"x") == mine.content_hash(b"x", {}) == mine.content_hash(b"x", None)


def test_hash_matches_the_documented_recipe():
    import hashlib
    import json
    meta = {"title": "חופשה", "version": "2.0"}
    h = hashlib.sha256(b"abc")
    h.update(b"\0")
    h.update(json.dumps(meta, sort_keys=True, ensure_ascii=False, default=str).encode())
    assert mine.content_hash(b"abc", meta) == h.hexdigest()[:16]


def test_plan_all_four_buckets_sorted():
    prev = {"b": "1", "a": "2", "c": "3", "z": "9"}
    cur = {"a": "2", "b": "X", "d": "4", "e": "5"}
    p = mine.plan_ingest(prev, cur)
    assert p.added == ["d", "e"] and p.changed == ["b"] and p.unchanged == ["a"]
    assert p.removed == ["c", "z"]


def test_plan_first_run_and_no_change():
    p = mine.plan_ingest({}, {"a": "1", "b": "2"})
    assert p.added == ["a", "b"] and not (p.changed or p.unchanged or p.removed)
    p = mine.plan_ingest({"a": "1"}, {"a": "1"})
    assert p.unchanged == ["a"] and not (p.added or p.changed or p.removed)


def test_plan_pipeline_changed_reprocesses_everything():
    p = mine.plan_ingest({"a": "1", "b": "2"}, {"a": "1", "b": "3", "c": "4"}, pipeline_changed=True)
    assert p.changed == ["a", "b"] and p.added == ["c"] and p.unchanged == []


def test_pipeline_runs_with_your_functions(tmp_path, tok):
    src = tmp_path / "docs"
    src.mkdir()
    for name in ("hr-vacation-2026.md", "hr-sick-leave.md", "hr-relocation.docx", "hr-relocation.meta.yaml"):
        shutil.copy(DOCS_DIR / name, src / name)
    def pipe():
        return IngestPipeline(tmp_path / "store", make_chunker("heading:400:40", tok),
                              planner=mine.plan_ingest, hasher=mine.content_hash)
    r1 = pipe().run(src)
    assert r1.plan.added == ["hr-relocation", "hr-sick-leave", "hr-vacation-2026"]
    r2 = pipe().run(src)
    assert r2.plan.unchanged == ["hr-relocation", "hr-sick-leave", "hr-vacation-2026"] and r2.chunks_added == 0
    meta = src / "hr-relocation.meta.yaml"
    meta.write_text(meta.read_text().replace("classification: confidential", "classification: internal"))
    (src / "hr-sick-leave.md").unlink()
    p = pipe()
    r3 = p.run(src)
    assert r3.plan.changed == ["hr-relocation"] and r3.plan.removed == ["hr-sick-leave"]
    assert {c.doc_id for c in p.all_chunks()} == {"hr-relocation", "hr-vacation-2026"}
    assert all(c.classification == "internal" for c in p.all_chunks() if c.doc_id == "hr-relocation")

"""M3: incremental re-indexing (mine.plan_sync)."""

from mine import plan_sync

M = {
    "a.md": {"hash": "h-a", "size": 10, "mtime": 100.0},
    "b.md": {"hash": "h-b", "size": 20, "mtime": 200.0},
    "c.md": {"hash": "h-c", "size": 30, "mtime": 300.0},
    "d.md": {"hash": "h-d", "size": 40, "mtime": 400.0},
}


class Hasher:
    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, fid):
        self.calls.append(fid)
        return self.table[fid]


def test_all_four_cases_and_sorted_lists():
    cur = {"a.md": {"size": 10, "mtime": 100.0},      # unchanged
           "b.md": {"size": 20, "mtime": 999.0},      # touched: mtime moved, same bytes
           "c.md": {"size": 31, "mtime": 301.0},      # changed
           "z.md": {"size": 5, "mtime": 1.0},         # added
           "e.md": {"size": 6, "mtime": 2.0}}         # added
    h = Hasher({"b.md": "h-b", "c.md": "h-c2", "z.md": "h-z", "e.md": "h-e"})
    p = plan_sync(M, cur, h)
    assert p.added == ["e.md", "z.md"]
    assert p.changed == ["c.md"]
    assert p.touched == ["b.md"]
    assert p.unchanged == ["a.md"]
    assert p.removed == ["d.md"]
    assert p.hashes == {"b.md": "h-b", "c.md": "h-c2", "z.md": "h-z", "e.md": "h-e"}


def test_unchanged_files_are_never_read():
    cur = {k: {"size": v["size"], "mtime": v["mtime"]} for k, v in M.items()}
    h = Hasher({})
    p = plan_sync(M, cur, h)
    assert h.calls == [] and p.unchanged == sorted(M) and not (p.added or p.changed or p.removed)


def test_each_file_is_hashed_at_most_once():
    cur = {"a.md": {"size": 11, "mtime": 100.0}, "new.md": {"size": 1, "mtime": 1.0}}
    h = Hasher({"a.md": "h-a2", "new.md": "h-n"})
    plan_sync(M, cur, h)
    assert sorted(h.calls) == ["a.md", "new.md"]


def test_empty_manifest_means_everything_is_added():
    cur = {"x/1.pdf": {"size": 1, "mtime": 1.0}, "x/0.pdf": {"size": 1, "mtime": 1.0}}
    p = plan_sync({}, cur, lambda fid: "h")
    assert p.added == ["x/0.pdf", "x/1.pdf"] and p.to_index == ["x/0.pdf", "x/1.pdf"]


def test_end_to_end_one_file_edited(tmp_path):
    import shutil

    from pss.config import SAMPLE, Settings
    from pss.index import PersonalIndex

    root = tmp_path / "docs"
    shutil.copytree(SAMPLE / "recipes", root / "recipes")
    s = Settings(roots=[str(root)], index_dir=str(tmp_path / "idx"))
    idx = PersonalIndex(s)
    first = idx.sync()
    assert len(first.plan.added) == 5
    (root / "recipes" / "lentil-soup.txt").write_text("Red lentil soup with smoked paprika\n", encoding="utf-8")
    (root / "recipes" / "pita-bread.html").unlink()
    again = PersonalIndex.open(s).sync()
    assert again.plan.changed == ["recipes/lentil-soup.txt"] and again.plan.removed == ["recipes/pita-bread.html"]
    assert len(again.plan.unchanged) + len(again.plan.touched) == 3

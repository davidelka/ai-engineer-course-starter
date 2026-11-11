"""Walk a folder and decide, file by file, what may be indexed.

This is the first privacy boundary: a file that is excluded here is never opened, parsed,
embedded or stored, so it can never appear in a result or reach a model. Excluding later (for
example, filtering search results) would leave its text in the index on disk.

Pattern semantics (a small, predictable subset of .gitignore):
    "*.key"        no slash: matched against EVERY path component (folders and the file name),
                   so ".*" skips hidden files AND everything inside hidden folders
    "private/"     trailing slash: a FOLDER name, anywhere in the path ("a/private/x.txt")
    "finance/*.pdf", "kids/**/report*"
                   a slash inside: matched against the whole relative path, where "*" stays
                   inside one component and "**" spans any number of folders (also zero)
Matching is case-insensitive (a folder named "Private" is private too).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

TEXT_EXT = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf", ".docx"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}
SUPPORTED = TEXT_EXT | IMAGE_EXT


def is_excluded(*args, **kwargs):
    """Milestone 2: runs your mine.is_excluded (see pss/hooks.py)."""
    from . import hooks
    return hooks.get("is_excluded")(*args, **kwargs)


@dataclass
class FileEntry:
    id: str                 # path relative to the root, posix style: the document id everywhere
    path: Path              # absolute path
    root: Path
    size: int
    mtime: float
    ext: str

    @property
    def folder(self) -> str:
        return self.id.split("/")[0] if "/" in self.id else ""

    def stat_dict(self) -> dict:
        return {"size": self.size, "mtime": self.mtime}


@dataclass
class ScanReport:
    files: list[FileEntry] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)   # (rel path, reason)

    def reasons(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for _, r in self.skipped:
            key = r.split(":")[0]
            out[key] = out.get(key, 0) + 1
        return out


def scan(root: os.PathLike | str, exclude: list[str], *, max_file_mb: float = 25.0,
         is_excluded_fn=None) -> ScanReport:
    """Every indexable file under root. Excluded folders are pruned while walking, so a huge
    excluded folder (node_modules, a photo library) costs nothing."""
    from . import hooks

    excl = is_excluded_fn or hooks.get("is_excluded")
    root = Path(root).expanduser().resolve()
    rep = ScanReport()
    if root.is_file():
        walk: Iterator = iter([(str(root.parent), [], [root.name])])
        base = root.parent
    else:
        walk = os.walk(root, followlinks=False)
        base = root
    for dirpath, dirnames, filenames in walk:
        rel_dir = os.path.relpath(dirpath, base).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        keep = []
        for d in sorted(dirnames):
            rel = f"{rel_dir}/{d}" if rel_dir else d
            pat = excl(rel + "/x", exclude)      # a file inside it: tests folder rules
            if pat is not None:
                rep.skipped.append((rel + "/", f"excluded: {pat}"))
            else:
                keep.append(d)
        dirnames[:] = keep
        for fn in sorted(filenames):
            rel = f"{rel_dir}/{fn}" if rel_dir else fn
            p = Path(dirpath) / fn
            if p.is_symlink():
                rep.skipped.append((rel, "symlink: not followed"))
                continue
            pat = excl(rel, exclude)
            if pat is not None:
                rep.skipped.append((rel, f"excluded: {pat}"))
                continue
            ext = p.suffix.lower()
            if ext not in SUPPORTED or fn.endswith(".meta.yaml"):
                rep.skipped.append((rel, f"unsupported: {ext or 'no extension'}"))
                continue
            st = p.stat()
            if st.st_size > max_file_mb * 1024 * 1024:
                rep.skipped.append((rel, f"too large: {st.st_size / 1e6:.1f} MB"))
                continue
            rep.files.append(FileEntry(id=rel, path=p, root=base, size=st.st_size,
                                       mtime=round(st.st_mtime, 3), ext=ext))
    return rep

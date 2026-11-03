"""Loaders: file -> Document (cleaned text + metadata).

    from ragkit.loaders import load_document, iter_sources
    doc = load_document("data/acme/corpus/docs/sales-sla-2026.pdf")

A loader is a function (path, bytes, **options) -> LoadResult. LOADERS maps a file
extension to one; register_loader(".pptx", my_fn) adds a format without touching anything
else. Metadata precedence: what the file says (front matter, <title>, DOCX properties) is
overridden by a sidecar `<stem>.meta.yaml` next to the file, which is how binary formats
carry the same fields as Markdown front matter.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional, Union

from ..clean import guess_language, normalize
from ..types import Document
from .base import LoadResult, parse_yaml
from .docx import load_docx
from .html import load_html
from .markdown import load_markdown, split_front_matter
from .pdf import load_pdf

Loader = Callable[..., LoadResult]
LOADERS: dict[str, Loader] = {
    ".md": load_markdown, ".markdown": load_markdown, ".txt": load_markdown,
    ".html": load_html, ".htm": load_html,
    ".pdf": load_pdf,
    ".docx": load_docx,
}
FORMATS = {".md": "md", ".markdown": "md", ".txt": "txt", ".html": "html", ".htm": "html",
           ".pdf": "pdf", ".docx": "docx"}
SIDECAR_SUFFIX = ".meta.yaml"


def register_loader(ext: str, fn: Loader, fmt: Optional[str] = None) -> None:
    ext = ext if ext.startswith(".") else "." + ext
    LOADERS[ext] = fn
    FORMATS[ext] = fmt or ext.lstrip(".")


def sidecar_for(path: Path) -> Path:
    return path.with_name(path.stem + SIDECAR_SUFFIX)


@dataclass
class Source:
    """A file to ingest, before parsing: enough to decide whether it changed."""

    id: str
    path: Path
    sidecar: Optional[Path]
    content_hash: str


def source_hash(data: bytes, sidecar_bytes: bytes = b"", extra: str = "") -> str:
    """sha256 over the raw file bytes, the sidecar metadata, and any pipeline string. Hashing the
    RAW bytes means an unchanged file is skipped before any (slow) parsing happens."""
    h = hashlib.sha256()
    for part in (data, b"\0", sidecar_bytes, b"\0", extra.encode()):
        h.update(part)
    return h.hexdigest()[:16]


def _source_id(path: Path, sidecar: Optional[Path]) -> str:
    if sidecar is not None:
        meta = parse_yaml(sidecar.read_text(encoding="utf-8"))
        if meta.get("id"):
            return str(meta["id"])
    if path.suffix in (".md", ".markdown"):
        head = path.read_text(encoding="utf-8-sig")[:2000]
        meta, _ = split_front_matter(head) if head.count("\n---") else ({}, "")
        if meta.get("id"):
            return str(meta["id"])
    return path.stem


Hasher = Callable[[bytes, dict], str]


def iter_sources(root: Union[str, Path], *, recursive: bool = True,
                 hasher: Optional[Hasher] = None) -> Iterator[Source]:
    """Every loadable file under root, sorted, with its sidecar attached (sidecars are never
    sources themselves). hasher(raw_bytes, sidecar_meta) -> str replaces the default hash
    (the lab plugs in mine.content_hash)."""
    root = Path(root)
    files = [root] if root.is_file() else sorted(root.rglob("*") if recursive else root.iterdir())
    for p in files:
        if not p.is_file() or p.name.endswith(SIDECAR_SUFFIX) or p.suffix.lower() not in LOADERS:
            continue
        side = sidecar_for(p)
        side = side if side.exists() else None
        data = p.read_bytes()
        side_bytes = side.read_bytes() if side else b""
        h = hasher(data, parse_yaml(side_bytes.decode("utf-8")) if side else {}) if hasher \
            else source_hash(data, side_bytes)
        yield Source(id=_source_id(p, side), path=p, sidecar=side, content_hash=h)


def load_document(path: Union[str, Path, Source], *, clean: bool = True, keep_raw: bool = False,
                  **options) -> Document:
    """Load one file into a Document. options go to the loader (e.g. mode="plain" for PDF,
    extractor="trafilatura" for HTML). keep_raw=True keeps the naive extraction and the
    removed boilerplate in doc.extras for inspection."""
    src = path if isinstance(path, Source) else None
    p = Path(src.path if src else path)
    ext = p.suffix.lower()
    if ext not in LOADERS:
        raise ValueError(f"no loader for {ext!r}; register one with register_loader()")
    data = p.read_bytes()
    side = src.sidecar if src else (sidecar_for(p) if sidecar_for(p).exists() else None)
    side_bytes = side.read_bytes() if side else b""
    res = LOADERS[ext](p, data, **options)
    meta = dict(res.meta)
    if side_bytes:
        meta.update(parse_yaml(side_bytes.decode("utf-8")))
    meta.setdefault("format", FORMATS.get(ext, ext.lstrip(".")))
    meta["format"] = FORMATS.get(ext, meta["format"])
    meta["source_path"] = str(p)
    text = normalize(res.text) if clean else res.text
    meta.setdefault("language", guess_language(text))
    doc_id = str(meta.get("id") or (src.id if src else p.stem))
    meta["id"] = doc_id
    meta.setdefault("title", doc_id)
    extras = {}
    if keep_raw:
        extras = {"raw_text": res.raw_text, "removed": res.removed, "loader_text": res.text}
    return Document(id=doc_id, text=text, meta=meta,
                    content_hash=src.content_hash if src else source_hash(data, side_bytes),
                    extras=extras)


def load_directory(root: Union[str, Path], **options) -> list[Document]:
    return [load_document(s, **options) for s in iter_sources(root)]


__all__ = ["LOADERS", "FORMATS", "LoadResult", "Source", "register_loader", "iter_sources",
           "load_document", "load_directory", "source_hash", "split_front_matter", "parse_yaml"]

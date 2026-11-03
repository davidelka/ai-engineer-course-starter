"""Markdown with an optional YAML front matter block."""

from __future__ import annotations

from pathlib import Path

from .base import LoadResult, parse_yaml


def split_front_matter(raw: str) -> tuple[dict, str]:
    """('---\\nid: x\\n---\\nbody') -> ({'id': 'x'}, 'body'). No front matter -> ({}, raw)."""
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    meta = parse_yaml(raw[3:end])
    body = raw[end + 4:]
    nl = body.find("\n")
    body = body[nl + 1:] if nl != -1 else ""
    return meta, body.lstrip("\n")


def load_markdown(path: Path, data: bytes) -> LoadResult:
    raw = data.decode("utf-8-sig")
    meta, body = split_front_matter(raw)
    if "title" not in meta:
        for line in body.splitlines():
            if line.startswith("# "):
                meta["title"] = line[2:].strip()
                break
    return LoadResult(text=body, meta=meta, raw_text=raw)


__all__ = ["load_markdown", "split_front_matter"]

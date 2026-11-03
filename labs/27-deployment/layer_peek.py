"""Look inside the layers of a saved image and find files that should not be there.

    docker save company-brain-api:baked -o labs/27-deployment/results/baked.tar
    python labs/27-deployment/layer_peek.py labs/27-deployment/results/baked.tar --find .env

An image is a stack of tar archives (layers) plus a config. Deleting a file in a later
layer only adds a "whiteout" marker; the bytes stay in the earlier layer, and anyone who
can pull the image can read them. This script opens every layer blob (docker-archive or
OCI layout, gzip/zstd-free tars) and lists matching paths. Values are masked: only the
first characters of each line are printed.
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import tarfile


def iter_layers(outer: tarfile.TarFile):
    """Yield (layer_name, inner TarFile) for every member of the outer tar that is a tar."""
    for m in outer.getmembers():
        if not m.isfile() or m.size < 512:
            continue
        data = outer.extractfile(m).read()
        try:
            inner = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
            inner.getmembers()
        except (tarfile.TarError, EOFError, OSError):
            continue
        yield m.name, inner


def mask(text: str, keep: int = 14) -> str:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line[:keep] + ("..." if len(line) > keep else ""))
    return " | ".join(out[:3])


def peek(path: str, pattern: str) -> list[dict]:
    found = []
    with tarfile.open(path) as outer:
        names = set(outer.getnames())
        manifest = json.load(outer.extractfile("manifest.json")) if "manifest.json" in names else None
        order = {layer: i for i, layer in enumerate(manifest[0].get("Layers", []))} if manifest else {}
        for name, inner in iter_layers(outer):
            for m in inner.getmembers():
                base = m.name.rsplit("/", 1)[-1]
                whiteout = base.startswith(".wh.")
                target = base[4:] if whiteout else base
                if fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(m.name, pattern):
                    preview = ""
                    if m.isfile() and not whiteout and m.size < 64_000:
                        preview = mask(inner.extractfile(m).read().decode("utf-8", "replace"))
                    found.append({"layer": name, "layer_index": order.get(name), "path": m.name,
                                  "whiteout": whiteout, "size": m.size, "preview": preview})
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description="find files inside image layers")
    ap.add_argument("image_tar", help="output of: docker save IMAGE -o file.tar")
    ap.add_argument("--find", default=".env", help="file name or glob, e.g. .env or *.pem")
    a = ap.parse_args()
    hits = peek(a.image_tar, a.find)
    if not hits:
        print(f"no {a.find!r} in any layer")
        return
    for h in hits:
        idx = "" if h["layer_index"] is None else f"layer #{h['layer_index']} "
        kind = "WHITEOUT (deleted here, still present below)" if h["whiteout"] else f"{h['size']} bytes"
        print(f"{idx}{h['layer'][:40]:40}  {h['path']:30}  {kind}  {h['preview']}")


if __name__ == "__main__":
    main()

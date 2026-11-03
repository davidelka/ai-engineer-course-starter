"""Images and documents in the mock (lesson 21).

What the mock does with media, deterministically and for free:
- finds every image / document block in the provider's own shape (Anthropic image and
  document blocks, OpenAI input_image / input_file parts, Gemini inlineData / fileData parts);
- reads the real type and pixel size from the bytes, and returns the provider's 400 for
  what the real API rejects (type mismatch, broken image, over-size, too many pages);
- bills image tokens with the provider's published formula (llmkit.media), so usage
  numbers move when you resize, exactly like the real thing;
- answers with what it saw ("2 images: image/png 1200x1600 seen at ...").

The "oracle" (for offline extraction labs): an image may carry a small JSON payload in a
PNG tEXt chunk, a JPEG comment or any other metadata chunk (e.g. WebP XMP) as
"mockllm-oracle:" + JSON. It says what a model would read
in the picture, and from which resolution each field becomes legible:

    {"caption": "...", "fields": {"total": {"value": "412.50", "min_long_edge": 700,
                                             "misread": "412.80"}, ...}}

When the request asks for structured output, the mock fills matching schema fields from the
oracle. A field whose min_long_edge is above the size the provider actually LOOKS at (after
its own resize) comes back as the misread value: shrink the image too much and accuracy
drops, like a real model squinting at small text. The real model has no oracle, of course:
this only makes the offline path behave plausibly.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Optional

from llmkit.media import (GEMINI_LEVEL_SIDE, IMAGE_TYPES, LIMITS, PDF_TYPE, anthropic_image_tokens,
                          gemini_image_tokens, image_info, openai_image_tokens, parse_data_url, pdf_page_count)

ORACLE_KEY = "mockllm-oracle"
URL_IMAGE_TOKENS = 1000  # the mock cannot fetch URLs: a fixed, documented guess
PAGE_PX = (1275, 1650)  # a letter page rendered at 150 dpi, for page-image token estimates


@dataclass
class Seen:
    kind: str  # "image" | "document"
    source: str  # "base64" | "url" | "file"
    media_type: str = ""
    width: int = 0
    height: int = 0
    nbytes: int = 0
    pages: int = 0
    detail: Optional[str] = None
    tokens: int = 0
    seen_w: int = 0  # the size the provider looks at after its resize
    seen_h: int = 0
    oracle: Optional[dict] = None
    text_chars: int = 0  # documents: characters of text we could pull out
    jpeg_quality: Optional[int] = None  # estimated from the quantization table

    def describe(self) -> str:
        if self.kind == "document":
            src = f"{self.pages} page(s)" if self.source == "base64" else f"from {self.source} (not fetched by the mock)"
            return f"document {self.media_type}, {src}, ~{self.tokens} tokens"
        if self.source != "base64":
            return f"image from {self.source} (not fetched by the mock), billed {self.tokens} tokens"
        seen = "" if (self.seen_w, self.seen_h) == (self.width, self.height) else f", seen at {self.seen_w}x{self.seen_h}"
        q = f", JPEG quality ~{self.jpeg_quality}" if self.jpeg_quality else ""
        return f"image {self.media_type} {self.width}x{self.height}{seen}{q}, {self.tokens} tokens"


# ---------------------------------------------------------------- oracle payloads
def read_oracle(data: bytes) -> Optional[dict]:
    """The JSON payload from a PNG tEXt/iTXt chunk or a JPEG COM segment, if present."""
    raw: Optional[bytes] = None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        i = 8
        while i + 8 <= len(data):
            length = struct.unpack(">I", data[i:i + 4])[0]
            ctype = data[i + 4:i + 8]
            chunk = data[i + 8:i + 8 + length]
            if ctype in (b"tEXt", b"zTXt", b"iTXt"):
                key, _, rest = chunk.partition(b"\x00")
                if key == ORACLE_KEY.encode():
                    if ctype == b"tEXt":
                        raw = rest
                    elif ctype == b"zTXt":
                        raw = zlib.decompress(rest[1:])
                    else:  # iTXt: flag, method, lang\0, translated\0, text
                        flag, method = rest[0], rest[1]
                        rest = rest[2:].split(b"\x00", 2)[-1]
                        raw = zlib.decompress(rest) if flag else rest
                    break
            if ctype == b"IEND":
                break
            i += 12 + length
    elif data[:3] == b"\xff\xd8\xff":
        m = re.search(rb"\xff\xfe(..)" + re.escape(ORACLE_KEY.encode()) + rb":", data, re.S)
        if m:
            seg_len = struct.unpack(">H", m.group(1))[0]
            start = m.end()
            raw = data[start:m.start() + 2 + seg_len]
    if raw is None:
        # Any other carrier (e.g. a WebP XMP chunk): "mockllm-oracle:" followed by JSON.
        k = data.find(ORACLE_KEY.encode() + b":")
        if k < 0:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(data[k + len(ORACLE_KEY) + 1:].decode("utf-8", "ignore"))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    try:
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


_STD_LUMA = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
             14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
             49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]


def jpeg_quality(data: bytes) -> Optional[int]:
    """Approximate libjpeg quality (1-100) from the first luminance quantization table."""
    i = data.find(b"\xff\xdb")
    if i < 0 or len(data) < i + 5 + 64:
        return None
    if data[i + 4] >> 4:  # 16-bit table: rare, skip
        return None
    table = data[i + 5:i + 5 + 64]
    scale = sum(table) * 100 / sum(_STD_LUMA)
    q = (200 - scale) / 2 if scale <= 100 else 5000 / scale
    return max(1, min(100, round(q)))


def quality_factor(q: Optional[int]) -> float:
    """Mock assumption: heavy JPEG artifacts blur small text like a lower resolution would."""
    if q is None or q >= 70:
        return 1.0
    return 0.9 if q >= 40 else 0.75 if q >= 20 else 0.55


def pdf_text_chars(data: bytes) -> int:
    """Characters inside PDF text operators ( ... ) Tj / TJ. Rough, uncompressed streams only.
    Compressed (Flate) streams are inflated first when possible."""
    chunks = [data]
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\n?endstream", data, re.S):
        raw = m.group(1)
        for decode in (lambda b: b, lambda b: base64.a85decode(b.strip().removesuffix(b"~>"), adobe=False)):
            try:
                chunks.append(zlib.decompress(decode(raw)))
                break
            except (zlib.error, ValueError):
                continue
    return sum(len(s) for c in chunks for s in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*T[jJ]", c))


# ---------------------------------------------------------------- inspection
def _digest(b64: str) -> str:
    return "sha256:" + hashlib.sha256(b64.encode()).hexdigest()[:16]


def _model_for(flavor: str, model: str) -> str:
    if flavor == "openai":
        return model if model.startswith("gpt-") else "gpt-5.4-mini"
    if flavor == "gemini":
        return model if model.startswith("gemini-") else "gemini-3.6-flash"
    return model


def _measure_image(flavor: str, model: str, s: Seen, data: bytes) -> Optional[tuple[int, str]]:
    try:
        info = image_info(data)
    except ValueError:
        return 400, "Could not process image"
    s.media_type, s.width, s.height, s.nbytes = info.media_type, info.width, info.height, len(data)
    s.oracle = read_oracle(data)
    if info.media_type == "image/jpeg":
        s.jpeg_quality = jpeg_quality(data)
    m = _model_for(flavor, model)
    if flavor == "anthropic":
        est = anthropic_image_tokens(info.width, info.height, m)
        s.tokens, s.seen_w, s.seen_h = est.tokens, est.width, est.height
    elif flavor == "openai":
        try:
            est = openai_image_tokens(info.width, info.height, m, s.detail or "auto")
        except ValueError as exc:
            return 400, f"Invalid image: {exc}"
        s.tokens, s.seen_w, s.seen_h = est.tokens, est.width, est.height
    else:
        est = gemini_image_tokens(info.width, info.height, m, s.detail)
        s.tokens = est.tokens
        # Mock assumption (not documented by Google): the fixed budget behaves like a
        # downscale to this long edge. Only used for the oracle's legibility check.
        side = GEMINI_LEVEL_SIDE.get(s.detail or "high", 1536)
        f = min(1.0, side / max(info.width, info.height))
        s.seen_w, s.seen_h = max(1, int(info.width * f)), max(1, int(info.height * f))
    return None


def _measure_doc(flavor: str, model: str, s: Seen, data: bytes) -> Optional[tuple[int, str]]:
    if not data.startswith(b"%PDF-"):
        return 400, "The PDF specified was not valid."
    s.media_type, s.nbytes = PDF_TYPE, len(data)
    s.pages = max(1, pdf_page_count(data))
    s.text_chars = pdf_text_chars(data)
    text_tokens = max(1, round(s.text_chars / 4)) if s.text_chars else 0
    m = _model_for(flavor, model)
    if flavor == "anthropic":
        page = anthropic_image_tokens(*PAGE_PX, m).tokens
        s.tokens = s.pages * page + text_tokens
    elif flavor == "openai":
        page = openai_image_tokens(*PAGE_PX, m, "low" if s.detail == "low" else "high").tokens
        s.tokens = s.pages * page + text_tokens
    else:  # Gemini: 560 per page by default (Gemini 3), native text not billed
        s.tokens = s.pages * {"low": 280, "medium": 560, "high": 1120}.get(s.detail or "medium", 560)
    return None


def inspect(flavor: str, body: dict, model: str = "mock-model") -> tuple[list[Seen], dict, Optional[tuple[int, str]]]:
    """Find, measure and validate media. Returns (seen, stripped_body, problem).

    stripped_body is a deep copy where every base64 payload is replaced by its digest, so
    token estimates and cache hashing see the image's identity, not megabytes of text."""
    stripped = json.loads(json.dumps(body))
    seen: list[Seen] = []

    def take(kind: str, source: str, payload: Optional[str], detail=None, media_type: str = "") -> Optional[tuple]:
        s = Seen(kind=kind, source=source, detail=detail, media_type=media_type)
        seen.append(s)
        if payload is None:
            s.tokens = URL_IMAGE_TOKENS if kind == "image" else 1500
            return None
        try:
            data = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            return 400, f"{kind} data is not valid base64"
        problem = (_measure_image if kind == "image" else _measure_doc)(flavor, model, s, data)
        if problem:
            return problem
        if flavor == "anthropic" and kind == "image" and media_type and media_type != s.media_type:
            return 400, f"Image does not match the provided media type {media_type}"
        if flavor == "anthropic" and kind == "image" and media_type and media_type not in IMAGE_TYPES:
            return 400, f"media_type: Input should be {', '.join(IMAGE_TYPES)}"
        return None

    problem = None
    if flavor == "anthropic":
        for m in stripped.get("messages") or []:
            c = m.get("content")
            if not isinstance(c, list):
                continue
            for b in c:
                if not isinstance(b, dict) or b.get("type") not in ("image", "document"):
                    continue
                src = b.get("source") or {}
                st = src.get("type")
                if st == "base64":
                    problem = problem or take(b["type"], "base64", src.get("data", ""), media_type=src.get("media_type", ""))
                    src["data"] = _digest(src.get("data", ""))
                elif st in ("url", "file"):
                    problem = problem or take(b["type"], st, None)
                elif b["type"] == "document" and st == "text":
                    continue
                else:
                    problem = problem or (400, f"{b['type']}.source.type: Input tag {st!r} found using 'type' does "
                                               "not match any of the expected tags: 'base64', 'url', 'file'")
    elif flavor == "openai":
        inp = stripped.get("input")
        for it in inp if isinstance(inp, list) else []:
            c = it.get("content") if isinstance(it, dict) else None
            for p in c if isinstance(c, list) else []:
                if not isinstance(p, dict):
                    continue
                if p.get("type") == "input_image":
                    url = p.get("image_url") or ""
                    if url.startswith("data:"):
                        try:
                            mt, raw = parse_data_url(url)
                        except (ValueError, binascii.Error):
                            problem = problem or (400, "Invalid 'image_url': expected a URL or a base64 data URL.")
                            continue
                        problem = problem or take("image", "base64", base64.b64encode(raw).decode(), p.get("detail"), mt)
                        p["image_url"] = "data:" + mt + ";" + _digest(url)
                    else:
                        problem = problem or take("image", "file" if p.get("file_id") else "url", None, p.get("detail"))
                elif p.get("type") == "input_file":
                    fd = p.get("file_data") or ""
                    if fd:
                        if not p.get("filename"):
                            problem = problem or (400, "Missing required parameter: 'input[].content[].filename'.")
                        try:
                            mt, raw = parse_data_url(fd)
                        except (ValueError, binascii.Error):
                            problem = problem or (400, "Invalid 'file_data': expected a base64 data URL.")
                            continue
                        problem = problem or take("document", "base64", base64.b64encode(raw).decode(), p.get("detail"), mt)
                        p["file_data"] = "data:" + mt + ";" + _digest(fd)
                    else:
                        problem = problem or take("document", "file" if p.get("file_id") else "url", None)
    else:
        for c in stripped.get("contents") or []:
            for p in c.get("parts") or []:
                if not isinstance(p, dict):
                    continue
                level = ((p.get("mediaResolution") or {}).get("level") or "").replace("MEDIA_RESOLUTION_", "").lower()
                level = level if level in ("low", "medium", "high", "ultra_high") else None
                if "inlineData" in p or "inline_data" in p:
                    blob = p.get("inlineData") or p.get("inline_data") or {}
                    mt = blob.get("mimeType") or blob.get("mime_type") or ""
                    kind = "document" if mt == PDF_TYPE else "image"
                    problem = problem or take(kind, "base64", blob.get("data", ""), level, mt)
                    blob["data"] = _digest(blob.get("data", ""))
                elif "fileData" in p or "file_data" in p:
                    fd = p.get("fileData") or p.get("file_data") or {}
                    mt = fd.get("mimeType") or fd.get("mime_type") or ""
                    problem = problem or take("document" if mt == PDF_TYPE else "image", "url", None, level)

    if problem is None:
        problem = _limits(flavor, seen)
    return seen, stripped, problem


def _limits(flavor: str, seen: list[Seen]) -> Optional[tuple[int, str]]:
    images = [s for s in seen if s.kind == "image"]
    docs = [s for s in seen if s.kind == "document"]
    if flavor == "anthropic":
        lim = LIMITS["anthropic"]
        if len(images) > lim["max_images"]:
            return 400, f"Too many images: a maximum of {lim['max_images']} images may be provided per request."
        many = len(images) + len(docs) > lim["many_images"]
        for s in images:
            if s.source != "base64":
                continue
            if s.nbytes * 4 / 3 > lim["image_bytes_b64"]:
                return 400, "image exceeds 10 MB maximum"
            side = lim["many_images_max_side"] if many else lim["max_side"]
            if max(s.width, s.height) > side:
                why = " for many-image requests (more than 20 images)" if many else ""
                return 400, f"image dimensions exceed max allowed size{why}: {side} pixels"
        pages = sum(s.pages for s in docs)
        if pages > lim["pdf_pages"]:
            return 400, f"A maximum of {lim['pdf_pages']} PDF pages may be provided."
    elif flavor == "gemini":
        pages = sum(s.pages for s in docs)
        if pages > LIMITS["gemini"]["pdf_pages"]:
            return 400, "The document has more than 1000 pages."
    return None


# ---------------------------------------------------------------- answers
def legible(s: Seen, spec: dict) -> bool:
    need = spec.get("min_long_edge") or 0
    return max(s.seen_w, s.seen_h) * quality_factor(s.jpeg_quality) >= need


def oracle_fields(seen: list[Seen]) -> dict[str, Any]:
    """Field values a model 'reads' across all images: the oracle value when legible at the
    size the provider looks at, the misread value otherwise (None if no misread given)."""
    out: dict[str, Any] = {}
    read_ok: set[str] = set()
    for s in seen:
        for name, spec in ((s.oracle or {}).get("fields") or {}).items():
            if name in read_ok:  # already read clearly in another image
                continue
            if not isinstance(spec, dict):
                out[name] = spec
                read_ok.add(name)
            elif legible(s, spec):
                out[name] = spec.get("value")
                read_ok.add(name)
            else:
                out[name] = spec.get("misread")
    return out


def fill_from_oracle(obj: Any, values: dict[str, Any]) -> Any:
    """Overwrite top-level keys of a schema sample with oracle values."""
    if isinstance(obj, dict):
        return {k: (values[k] if k in values else v) for k, v in obj.items()}
    return obj


def describe(seen: list[Seen], question: str) -> str:
    imgs = [s for s in seen if s.kind == "image"]
    docs = [s for s in seen if s.kind == "document"]
    head = []
    if imgs:
        head.append(f"{len(imgs)} image(s)")
    if docs:
        head.append(f"{len(docs)} document(s)")
    lines = [f"mockllm saw {' and '.join(head)}:"]
    lines += [f"#{i} {s.describe()}" for i, s in enumerate(seen, 1)]
    caps = [s.oracle.get("caption") for s in seen if s.oracle and s.oracle.get("caption")]
    if caps:
        lines.append("Caption: " + " | ".join(caps))
    vals = oracle_fields(seen)
    if vals:
        lines.append("Readable fields: " + ", ".join(f"{k}={v}" for k, v in vals.items()))
    q = " ".join(question.split())[:80]
    if q:
        lines.append(f"You asked: {q}")
    return "\n".join(lines)

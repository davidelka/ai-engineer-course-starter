"""Images and documents (lesson 21): sniffing, limits and image-token estimates.

Pure functions, no I/O and no Pillow: the header of a PNG, JPEG, GIF or WebP file
already holds its width and height, so we read them from the bytes directly.

The token formulas below are the providers' published rules, checked in November 2026
(sources at the end of this docstring). They are ESTIMATES: the provider's own usage
numbers are the truth, so measure (Anthropic count_tokens is free; OpenAI and Gemini
report usage on every call). Where a rule was reconstructed from worked examples
rather than stated as code, the function says so.

Anthropic (platform.claude.com/docs/en/build-with-claude/vision):
  tokens = ceil(w/28) * ceil(h/28) after an automatic downscale.
  High-resolution tier (Claude 4.7 and later): long edge <= 2576 px and <= 4784 tokens.
  Standard tier (older models): long edge <= 1568 px and <= 1568 tokens.
  Doc examples: 1920x1080 -> 1456x819 = 1560 tokens (standard), 2691 (high-res, not resized);
  3840x2160 -> 2576x1449 = 4784 tokens (high-res).
OpenAI (developers.openai.com/api/docs/guides/images-vision):
  patch models (gpt-5.2 and later, gpt-4.1-mini): fit the detail level's max dimension,
  count 32x32 patches, shrink to the patch budget, tokens = ceil(patches * multiplier).
  tile models (gpt-5.1, gpt-5, gpt-4o, gpt-4.1): fit 2048x2048, shortest side to 768,
  base + tiles(512px) * per_tile; detail=low costs only the base.
Gemini (ai.google.dev/gemini-api/docs/media-resolution, image-understanding):
  Gemini 3 and later: a fixed budget per image by media_resolution
  (low 280, medium 560, high 1120, ultra_high 2240; default 1120).
  Gemini 2.x: 258 tokens if both sides <= 384 px, else 258 per tile with a crop unit of
  floor(min(w, h) / 1.5), clamped to 256..768.
"""

from __future__ import annotations

import base64
import math
import re
import struct
from dataclasses import dataclass
from typing import Optional

IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")
PDF_TYPE = "application/pdf"


# ---------------------------------------------------------------- sniffing
@dataclass(frozen=True)
class ImageInfo:
    media_type: str
    width: int
    height: int


def sniff_media_type(data: bytes) -> Optional[str]:
    """The real type of the bytes, from their magic number (never from a file name)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:5] == b"%PDF-":
        return PDF_TYPE
    return None


def _jpeg_size(data: bytes) -> Optional[tuple[int, int]]:
    i = 2
    n = len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # no length field
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        # SOF0..SOF15 hold the frame size, except DHT (C4), JPG (C8) and DAC (CC).
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seg_len
    return None


def _webp_size(data: bytes) -> Optional[tuple[int, int]]:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:  # lossy
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L" and len(data) >= 25:  # lossless: 14-bit sizes after a 0x2f signature
        b = data[21:25]
        w = 1 + (((b[1] & 0x3F) << 8) | b[0])
        h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
        return w, h
    if chunk == b"VP8X" and len(data) >= 30:  # extended: 24-bit (size - 1)
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return w, h
    return None


def image_info(data: bytes) -> ImageInfo:
    """Media type and pixel size of PNG / JPEG / GIF / WebP bytes. Raises ValueError otherwise."""
    mt = sniff_media_type(data)
    size: Optional[tuple[int, int]] = None
    if mt == "image/png" and len(data) >= 24:
        size = struct.unpack(">II", data[16:24])
    elif mt == "image/gif" and len(data) >= 10:
        size = struct.unpack("<HH", data[6:10])
    elif mt == "image/jpeg":
        size = _jpeg_size(data)
    elif mt == "image/webp":
        size = _webp_size(data)
    if mt not in IMAGE_TYPES or not size:
        raise ValueError(f"not a supported image (PNG, JPEG, GIF, WebP); detected {mt or 'unknown bytes'}")
    return ImageInfo(mt, int(size[0]), int(size[1]))


def pdf_page_count(data: bytes) -> int:
    """Rough page count of a PDF (counts /Type /Page objects). Good enough for limits and
    estimates; use pypdf when you need the exact structure."""
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


def to_data_url(media_type: str, data: bytes) -> str:
    return f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"


def parse_data_url(url: str) -> tuple[str, bytes]:
    """'data:image/png;base64,....' -> ('image/png', bytes). Raises ValueError."""
    m = re.match(r"^data:([\w.+/-]+);base64,(.*)$", url, re.S)
    if not m:
        raise ValueError("not a base64 data URL")
    return m.group(1), base64.b64decode(m.group(2))


def guess_type_from_url(url: str) -> str:
    ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
            "webp": "image/webp", "pdf": PDF_TYPE}.get(ext, "application/octet-stream")


# ---------------------------------------------------------------- limits (Nov 2026)
# Per image / document, as documented. Checked before sending so a mistake is a clear
# local error, not a 400 after uploading 30 MB. Sources: the vision and PDF pages of each
# provider (see the module docstring); Gemini's inline limit is "20MB per request" on the
# image-understanding page and "100 MB per request (50 MB for PDFs)" on the newer
# file-input-methods page: we use the stricter number.
LIMITS = {
    "anthropic": {"image_bytes_b64": 10 * 1024 * 1024, "max_side": 8000, "max_images": 100,
                  "many_images": 20, "many_images_max_side": 3000, "pdf_pages": 100,
                  "request_bytes": 128 * 1024 * 1024},
    "openai": {"request_bytes": 512 * 1024 * 1024, "max_images": 1500, "max_patches": 30_000,
               "file_bytes": 50 * 1024 * 1024},
    "gemini": {"request_bytes": 20 * 1024 * 1024, "max_images": 3600, "pdf_pages": 1000,
               "pdf_bytes": 50 * 1024 * 1024},
}


# ---------------------------------------------------------------- token estimates
@dataclass(frozen=True)
class TokenEstimate:
    tokens: int
    width: int  # the size the provider actually looks at, after its resize
    height: int
    method: str  # a one-line explanation of the formula used


def _fit(w: int, h: int, max_w: int, max_h: int) -> tuple[int, int]:
    """Scale down (never up) to fit inside max_w x max_h, keeping the aspect ratio."""
    s = min(1.0, max_w / w, max_h / h)
    return (max(1, int(w * s)), max(1, int(h * s))) if s < 1 else (w, h)


# ---- Anthropic
ANTHROPIC_TIERS = {"high": (2576, 4784), "standard": (1568, 1568)}  # (max long edge, max tokens)


def anthropic_tier(model: str) -> str:
    """'high' for Claude 4.7 and later (and the mock, which is priced like Haiku 5.5),
    'standard' for older models."""
    m = re.search(r"-(\d+)-(\d+)(?:-|$)", model)
    if not m:
        return "high"
    return "high" if (int(m.group(1)), int(m.group(2))) >= (4, 7) else "standard"


def _a_tokens(w: int, h: int) -> int:
    return math.ceil(w / 28) * math.ceil(h / 28)


def anthropic_resize(w: int, h: int, tier: str = "high") -> tuple[int, int]:
    """The size Claude looks at. Reconstructed from the documented limits and examples:
    keep the image if it fits both limits; otherwise shrink the long edge (in steps of 28 px,
    one patch) until both the long-edge and the token limits hold. Matches every example in
    the docs (1920x1080 -> 1456x819 standard; 3840x2160 -> 2576x1449 high-res)."""
    max_long, max_tok = ANTHROPIC_TIERS[tier]
    long, short = max(w, h), min(w, h)
    if long <= max_long and _a_tokens(w, h) <= max_tok:
        return w, h
    new_long = min(long, max_long) // 28 * 28
    while True:
        new_short = max(1, round(short * new_long / long))
        if _a_tokens(new_long, new_short) <= max_tok or new_long <= 28:
            break
        new_long -= 28
    return (new_long, new_short) if w >= h else (new_short, new_long)


def anthropic_image_tokens(w: int, h: int, model: str = "claude-haiku-5-5") -> TokenEstimate:
    tier = anthropic_tier(model)
    rw, rh = anthropic_resize(w, h, tier)
    return TokenEstimate(_a_tokens(rw, rh), rw, rh,
                         f"{tier} tier: ceil({rw}/28) x ceil({rh}/28) = {math.ceil(rw / 28)} x {math.ceil(rh / 28)}")


# ---- OpenAI
# Patch models: detail -> (max dimension, patch budget or None). "auto" -> another detail.
_P54 = {"low": (2048, 6144), "high": (2048, 2500), "original": (6000, 10_000), "auto": "high"}
OPENAI_PATCH = {
    "gpt-6-astra": {"low": (512, None), "high": (65535, 2500), "original": (65535, None), "auto": "original"},
    "gpt-5.6": {"low": (512, None), "high": (2048, 2500), "original": (65535, None), "auto": "original"},
    "gpt-5.5": {"high": (2048, 2500), "original": (6000, 10_000), "auto": "high", "low": "high"},
    "gpt-5.4": _P54,  # also gpt-5.4-mini, gpt-5.4-nano (prefix match)
    "gpt-5.2": {"low": (2048, 6144), "high": (2048, 6144), "auto": (2048, 6144)},
    "gpt-4.1-mini": {"low": (2048, 6144), "high": (2048, 6144), "auto": (2048, 6144)},
}
OPENAI_MULTIPLIER = {"gpt-4.1-mini": 1.62}  # every other patch model listed: 1.2
OPENAI_TILE = {"gpt-5.1": (70, 140), "gpt-5": (70, 140), "gpt-4o-mini": (2833, 5667),
               "gpt-4o": (85, 170), "gpt-4.1": (85, 170)}  # (base, per tile)


def _family(model: str, table: dict) -> Optional[str]:
    for key in sorted(table, key=len, reverse=True):  # longest prefix wins (gpt-4o-mini before gpt-4o)
        if model == key or model.startswith(key + "-") or model.startswith(key):
            return key
    return None


def openai_image_tokens(w: int, h: int, model: str = "gpt-5.4-mini", detail: str = "auto") -> TokenEstimate:
    detail = detail or "auto"
    fam = _family(model, OPENAI_PATCH)
    if fam:
        rules = OPENAI_PATCH[fam]
        rule = rules.get(detail)
        if rule is None:
            raise ValueError(f"detail={detail!r} is not supported on {model}")
        if isinstance(rule, str):
            detail, rule = rule, rules[rule]
        max_dim, budget = rule
        rw, rh = _fit(w, h, max_dim, max_dim)
        patches = math.ceil(rw / 32) * math.ceil(rh / 32)
        if budget and patches > budget:
            s = math.sqrt(budget * 32 * 32 / (rw * rh))
            while True:
                nw, nh = max(1, int(rw * s)), max(1, int(rh * s))
                if math.ceil(nw / 32) * math.ceil(nh / 32) <= budget:
                    break
                s *= 0.99
            rw, rh = nw, nh
            patches = math.ceil(rw / 32) * math.ceil(rh / 32)
        if patches > LIMITS["openai"]["max_patches"]:
            raise ValueError(f"{patches} patches after resizing: the API rejects images above 30,000")
        mult = OPENAI_MULTIPLIER.get(fam, 1.2)
        return TokenEstimate(math.ceil(patches * mult), rw, rh,
                             f"patches: ceil({rw}/32) x ceil({rh}/32) = {patches} x {mult} (detail={detail})")
    fam = _family(model, OPENAI_TILE)
    if not fam:
        raise ValueError(f"no image token rule for {model!r}")
    base, per_tile = OPENAI_TILE[fam]
    if detail == "low":
        return TokenEstimate(base, *_fit(w, h, 512, 512), f"tiles: detail=low costs the base {base}")
    rw, rh = _fit(w, h, 2048, 2048)
    if min(rw, rh) > 768:
        s = 768 / min(rw, rh)
        rw, rh = int(rw * s), int(rh * s)
    tiles = math.ceil(rw / 512) * math.ceil(rh / 512)
    return TokenEstimate(base + tiles * per_tile, rw, rh, f"tiles: {base} + {tiles} x {per_tile}")


# ---- Gemini
GEMINI_LEVELS = {"low": 280, "medium": 560, "high": 1120, "ultra_high": 2240}
GEMINI_DEFAULT = 1120
GEMINI_LEVEL_SIDE = {"low": 512, "medium": 768, "high": 1536, "ultra_high": 3072}  # used only by the mock


def gemini_generation(model: str) -> int:
    m = re.match(r"gemini-(\d+)", model)
    return int(m.group(1)) if m else 3


def gemini_image_tokens(w: int, h: int, model: str = "gemini-3.6-flash",
                        media_resolution: Optional[str] = None) -> TokenEstimate:
    if gemini_generation(model) >= 3:
        level = media_resolution if media_resolution in GEMINI_LEVELS else None
        tok = GEMINI_LEVELS[level] if level else GEMINI_DEFAULT
        return TokenEstimate(tok, w, h, f"fixed budget per image: media_resolution={level or 'default'} -> {tok}")
    if w <= 384 and h <= 384:
        return TokenEstimate(258, w, h, "both sides <= 384 px: 258")
    crop = max(256, min(768, math.floor(min(w, h) / 1.5)))
    tiles = math.ceil(w / crop) * math.ceil(h / crop)
    return TokenEstimate(258 * tiles, w, h, f"crop unit {crop}: {math.ceil(w / crop)} x {math.ceil(h / crop)} tiles x 258")


def image_tokens(provider: str, model: str, w: int, h: int, detail: Optional[str] = None) -> TokenEstimate:
    """One entry point. detail: OpenAI detail (low/high/auto/original) or Gemini
    media_resolution (low/medium/high/ultra_high); ignored by Anthropic."""
    if provider == "anthropic":
        return anthropic_image_tokens(w, h, model)
    if provider == "openai":
        return openai_image_tokens(w, h, model, detail or "auto")
    if provider == "gemini":
        return gemini_image_tokens(w, h, model, detail)
    raise ValueError(f"unknown provider {provider!r}")


def image_cost_usd(tokens: int, model: str) -> Optional[float]:
    """Input price of `tokens` image tokens (images are billed as input tokens)."""
    from .pricing import PRICES
    p = PRICES.get(model)
    return None if not p else tokens * p["input"] / 1_000_000

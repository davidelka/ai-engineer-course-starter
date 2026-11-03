"""Shared bits for the lesson 21 scripts: paths, .env, model choice, the mock server, image prep."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Optional

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path[:0] = [str(ROOT), str(LAB)]

from llmkit import LLM, load_dotenv  # noqa: E402

DEFAULT_MODEL = "anthropic:claude-haiku-5-5"
RESULTS = LAB / "results"
RESULTS.mkdir(exist_ok=True)


def make_llm(spec: str, mock_cfg: Optional[dict] = None) -> LLM:
    """'mock' (or mock-openai / mock-gemini) starts an in-process mock server: free, no key."""
    load_dotenv(str(ROOT / ".env"))
    if spec.startswith("mock"):
        from mockllm import MockConfig, start_in_thread
        cfg = MockConfig(ttft=0, tps=0, seed=1, **(mock_cfg or {}))
        server, url = start_in_thread(cfg)
        provider = spec.split("-", 1)[1] if "-" in spec else "anthropic"
        llm = LLM(f"{provider}:mock-model", api_key="mock", base_url=url)
        llm._mock_server = server  # keep a reference; daemon thread dies with the process
        return llm
    return LLM(spec)


def is_mock(llm: LLM) -> bool:
    return hasattr(llm, "_mock_server")


def prepare_image(data: bytes, *, long_edge: Optional[int] = None, fmt: str = "PNG", quality: int = 85,
                  keep_oracle: bool = True) -> bytes:
    """Resize (never upscale) so the long edge is at most `long_edge`, re-encode as PNG / JPEG /
    WEBP, and drop ALL metadata (EXIF, GPS, text chunks): photos can carry where and when they
    were taken. keep_oracle=True copies only the mockllm oracle payload, for the offline path."""
    from PIL import Image as PILImage, PngImagePlugin
    from mockllm.vision import read_oracle

    oracle = read_oracle(data) if keep_oracle else None
    img = PILImage.open(io.BytesIO(data))
    img = img.convert("RGB") if fmt.upper() in ("JPEG", "WEBP") else img.convert("RGBA" if img.mode == "RGBA" else "RGB")
    if long_edge and max(img.size) > long_edge:
        s = long_edge / max(img.size)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), PILImage.LANCZOS)
    out = io.BytesIO()
    payload = json.dumps(oracle, ensure_ascii=False) if oracle else None
    if fmt.upper() == "PNG":
        info = PngImagePlugin.PngInfo()
        if payload:
            info.add_text("mockllm-oracle", payload)
        img.save(out, "PNG", pnginfo=info, optimize=True)
    elif fmt.upper() == "JPEG":
        kw = {"comment": b"mockllm-oracle:" + payload.encode()} if payload else {}
        img.save(out, "JPEG", quality=quality, **kw)
    elif fmt.upper() == "WEBP":
        kw = {"xmp": b"mockllm-oracle:" + payload.encode()} if payload else {}
        img.save(out, "WEBP", quality=quality, **kw)
    else:
        raise ValueError(fmt)
    return out.getvalue()


def for_model(data: bytes, llm: LLM) -> bytes:
    """What we actually send: the mock keeps its oracle; a real model gets a clean re-encode
    without any metadata (lossless for PNG, high quality for JPEG)."""
    if is_mock(llm):
        return data
    fmt = "PNG" if data[:4] == b"\x89PNG" else "JPEG"
    return prepare_image(data, fmt=fmt, quality=92, keep_oracle=False)

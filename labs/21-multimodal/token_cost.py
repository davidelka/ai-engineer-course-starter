"""Exercise 3: how many tokens (and dollars) an image costs, per provider.

    python labs/21-multimodal/token_cost.py                 # the reference calculator (llmkit.media)
    python labs/21-multimodal/token_cost.py --mine          # YOUR mine.image_tokens, side by side
    python labs/21-multimodal/token_cost.py --size 4032x3024 --per 10000
    python labs/21-multimodal/token_cost.py --live          # Anthropic count_tokens on our 3 images (free)
    python labs/21-multimodal/token_cost.py --live-openai   # OpenAI usage for one image, low vs high (~$0.002)

The sizes cover the common cases: a phone photo (4032x3024), a 1080p and a 4K screenshot, a
scanned A4 page at 150 dpi (1240x1754), a small thumbnail, and our three lab images.
Prices come from llmkit/pricing.py (input price per 1M tokens); images are billed as input.
"""

from __future__ import annotations

import argparse
import os

import httpx

import _lab  # noqa: F401
from _lab import ROOT, prepare_image
from acme_vision import FILES, IMAGES
from llmkit import load_dotenv
from llmkit.media import image_info, image_tokens, to_data_url
from llmkit.pricing import PRICES

SIZES = {"phone photo": (4032, 3024), "1080p screenshot": (1920, 1080), "4K screenshot": (3840, 2160),
         "A4 scan 150dpi": (1240, 1754), "thumbnail": (320, 240)}
TARGETS = [("anthropic", "claude-haiku-5-5", None), ("anthropic", "claude-haiku-4-5", None),
           ("openai", "gpt-5.4-mini", "low"), ("openai", "gpt-5.4-mini", "high"), ("openai", "gpt-5.4-mini", "original"),
           ("openai", "gpt-4o", "high"), ("gemini", "gemini-3.6-flash", "low"), ("gemini", "gemini-3.6-flash", None),
           ("gemini", "gemini-2.5-flash", None)]


def price_per_m(model: str) -> float | None:
    p = PRICES.get(model)
    return p["input"] if p else None


def table(sizes: dict, per: int, mine: bool) -> None:
    if mine:
        import mine as student
    for label, (w, h) in sizes.items():
        print(f"\n{label}: {w}x{h}")
        for provider, model, detail in TARGETS:
            est = image_tokens(provider, model, w, h, detail)
            price = price_per_m(model)
            money = f"${est.tokens * price / 1e6 * per:8.2f} per {per:,}" if price else "(no price in pricing.py)"
            line = f"   {provider:9} {model:17} {detail or '':9} {est.tokens:6} tokens  {money}   seen as {est.width}x{est.height}"
            if mine:
                try:
                    got = student.image_tokens(provider, model, w, h, detail)
                    line += "   mine: " + ("OK" if got == est.tokens else f"{got} (expected {est.tokens})")
                except NotImplementedError:
                    line += "   mine: not implemented"
                except ValueError as exc:
                    line += f"   mine: ValueError {exc}"
            print(line)


def live_anthropic() -> None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set in .env")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    model = "claude-haiku-5-5"

    def count(content) -> int:
        r = httpx.post("https://api.anthropic.com/v1/messages/count_tokens", headers=headers, timeout=60,
                       json={"model": model, "messages": [{"role": "user", "content": content}]})
        r.raise_for_status()
        return r.json()["input_tokens"]
    base = count("x")
    print(f"count_tokens (free) on {model}; text-only baseline: {base} tokens")
    for name, fname in FILES.items():
        raw = (IMAGES / fname).read_bytes()
        for long_edge in (None, 1000, 500):
            data = prepare_image(raw, long_edge=long_edge, fmt="PNG" if fname.endswith(".png") else "JPEG",
                                 quality=90, keep_oracle=False)
            info = image_info(data)
            n = count([{"type": "image", "source": {"type": "base64", "media_type": info.media_type,
                                                    "data": __import__("base64").b64encode(data).decode()}},
                       {"type": "text", "text": "x"}]) - base
            est = image_tokens("anthropic", model, info.width, info.height).tokens
            flag = "" if abs(n - est) <= max(5, est * 0.02) else "   <- differs from the formula: tell me"
            print(f"   {fname:17} {info.width:5}x{info.height:<5} measured {n:5}  formula {est:5}{flag}")


def live_openai() -> None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set in .env")
    data = (IMAGES / "whiteboard.jpg").read_bytes()
    data = prepare_image(data, fmt="JPEG", quality=90, keep_oracle=False)
    info = image_info(data)

    def usage(content) -> int:
        r = httpx.post("https://api.openai.com/v1/responses", timeout=120,
                       headers={"authorization": f"Bearer {key}"},
                       json={"model": "gpt-5.4-mini", "max_output_tokens": 16, "reasoning": {"effort": "low"},
                             "input": [{"role": "user", "content": content}]})
        r.raise_for_status()
        return r.json()["usage"]["input_tokens"]
    base = usage([{"type": "input_text", "text": "Say ok."}])
    print(f"gpt-5.4-mini, whiteboard {info.width}x{info.height}; text-only baseline {base} tokens")
    for detail in ("low", "high"):
        n = usage([{"type": "input_image", "image_url": to_data_url(info.media_type, data), "detail": detail},
                   {"type": "input_text", "text": "Say ok."}]) - base
        est = image_tokens("openai", "gpt-5.4-mini", info.width, info.height, detail).tokens
        print(f"   detail={detail:5} measured {n:5}  formula {est:5}")
    print("If low costs MORE than high, the docs' table (low: 6,144-patch budget) is what the API does.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", action="store_true")
    ap.add_argument("--size", help="WxH, e.g. 4032x3024")
    ap.add_argument("--per", type=int, default=1000, help="price per N images")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--live-openai", action="store_true")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    if a.live:
        return live_anthropic()
    if a.live_openai:
        return live_openai()
    sizes = dict(SIZES)
    for name, fname in FILES.items():
        info = image_info((IMAGES / fname).read_bytes())
        sizes[f"lab image {fname}"] = (info.width, info.height)
    if a.size:
        w, h = map(int, a.size.lower().split("x"))
        sizes = {"your size": (w, h)}
    table(sizes, a.per, a.mine)


if __name__ == "__main__":
    main()

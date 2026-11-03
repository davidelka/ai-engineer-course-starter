"""Exercise 4: resize and compress before sending. What does it save, and what does it break?

    python labs/21-multimodal/resize_sweep.py                       # free: mockllm, all sizes and formats
    python labs/21-multimodal/resize_sweep.py --image receipt
    python labs/21-multimodal/resize_sweep.py --model anthropic:claude-haiku-5-5 --image receipt   # live, ~1 cent
    python labs/21-multimodal/resize_sweep.py --provider openai     # same sweep, OpenAI's token rules (mock)

For each image and each (long edge, format, quality) it prints: bytes on the wire, the
image tokens the provider bills (after ITS OWN resize), the cost per 1,000 images, and the
field accuracy of a real extraction (exercise 2's pipeline). At the end: the cheapest setting
that keeps every legible field correct.

Offline, the mock decides legibility from the oracle in each image (font size vs the size the
provider looks at; heavy JPEG artifacts count as lost resolution). Live, the model decides.
The two will not agree exactly: that comparison is the point of running it live once.
"""

from __future__ import annotations

import argparse

import _lab  # noqa: F401
from _lab import make_llm, prepare_image
from acme_vision import FILES, IMAGES, KINDS, PROMPTS, SCHEMAS, SYSTEM, gold
from llmkit import ChatRequest, Image, Message
from llmkit.fields import field_accuracy
from llmkit.media import image_info, image_tokens
from llmkit.pricing import PRICES
from llmkit.structured import StructuredError, complete_structured

EDGES = [None, 1568, 1200, 1000, 800, 600, 400]
FORMATS = [("PNG", 0), ("JPEG", 85), ("JPEG", 40), ("WEBP", 75)]
LIVE_FORMATS = [("JPEG", 85)]  # live runs keep the call count small
MODEL_FOR = {"anthropic": "claude-haiku-5-5", "openai": "gpt-5.4-mini", "gemini": "gemini-3.6-flash"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock")
    ap.add_argument("--provider", choices=list(MODEL_FOR), default="anthropic", help="token rules for the mock")
    ap.add_argument("--image", choices=list(FILES))
    a = ap.parse_args()
    spec = a.model if a.model != "mock" else ("mock" if a.provider == "anthropic" else f"mock-{a.provider}")
    llm = make_llm(spec)
    live = not spec.startswith("mock")
    provider = llm.provider.name
    model = MODEL_FOR[provider] if not live else llm.model
    price = PRICES.get(model, {}).get("input", 0)
    golds = gold()
    cost = 0.0
    for name, fname in FILES.items():
        if a.image and name != a.image:
            continue
        raw = (IMAGES / fname).read_bytes()
        w0, h0 = image_info(raw).width, image_info(raw).height
        print(f"\n{fname} ({w0}x{h0}), {provider} {model}")
        print(f"   {'long edge':>9} {'format':8} {'KB':>7} {'tokens':>7} {'$/1000':>7}  accuracy  wrong fields")
        best = None
        for edge in EDGES:
            if edge and edge >= max(w0, h0):
                continue
            for fmt, q in (LIVE_FORMATS if live else FORMATS):
                data = prepare_image(raw, long_edge=edge, fmt=fmt, quality=q or 85, keep_oracle=not live)
                info = image_info(data)
                tok = image_tokens(provider, model, info.width, info.height).tokens
                req = ChatRequest(messages=[Message.user_with(Image(data=data), PROMPTS[name])], system=SYSTEM,
                                  max_tokens=800)
                try:
                    res = complete_structured(llm, req, SCHEMAS[name], max_repairs=1)
                    value, c = res.value, res.cost_usd
                except StructuredError as exc:
                    value, c = None, exc.result.cost_usd if exc.result else 0.0
                cost += c or 0.0
                rep = field_accuracy(value, golds[name], KINDS[name])
                label = f"{fmt}{'' if fmt == 'PNG' else ' q' + str(q)}"
                wrong = ", ".join(m[0] for m in rep.mismatches) or "-"
                print(f"   {str(edge or 'original'):>9} {label:8} {len(data) / 1024:7.0f} {tok:7} "
                      f"{tok * price / 1000:7.3f}  {rep.accuracy:7.0%}   {wrong}")
                # "every legible field": counting fields are wrong even at full size in the mock
                key = (round(rep.accuracy, 4), -tok, -len(data))
                if best is None or key > best[0]:
                    best = (key, edge, label, tok, len(data))
        if best:
            (_, edge, label, tok, size) = best
            print(f"   best accuracy at the lowest cost: long edge {edge or 'original'}, {label}: {tok} tokens, "
                  f"{size / 1024:.0f} KB")
    if live:
        print(f"\nlive cost: ${cost:.4f}")


if __name__ == "__main__":
    main()

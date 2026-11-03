"""Make the three synthetic Acme images and their gold answers (lesson 21).

    python labs/21-multimodal/make_images.py          # writes data/images/* and data/gold.json

The images are committed, so you only need this to change them. Every field is drawn with a
known font size; from it we compute the smallest long edge at which the field is still legible
(text about 9 px tall after scaling). That number goes into a small "oracle" payload inside the
file (PNG text chunk / JPEG comment) that ONLY mockllm reads, so the offline path behaves like a
model squinting at small text. Real models only see pixels. See mockllm/vision.py.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acme_vision import GOLD, IMAGES  # noqa: E402

LEGIBLE_PX = 9  # text smaller than this (after the provider's resize) is treated as unreadable
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/Library/Fonts", "C:/Windows/Fonts"]


def font(size: int, style: str = "Sans") -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        p = Path(d) / f"DejaVu{style}.ttf"
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size=size)  # Pillow >= 10.1 ships a scalable default font


def min_edge(long_edge: int, font_px: int) -> int:
    return math.ceil(long_edge * LEGIBLE_PX / font_px)


def field(value, long_edge: int, font_px: int, misread) -> dict:
    return {"value": value, "min_long_edge": min_edge(long_edge, font_px), "misread": misread, "font_px": font_px}


def never(value, misread) -> dict:
    """A field the mock always gets wrong (counting is a known weak spot of vision models)."""
    return {"value": value, "min_long_edge": 10**6, "misread": misread, "font_px": None}


# ---------------------------------------------------------------- receipt
def receipt() -> tuple[Image.Image, dict, dict]:
    W, H = 900, 1800
    bg = Image.new("RGB", (W, H), (120, 116, 110))
    paper = Image.new("RGB", (700, 1640), (250, 248, 242))
    d = ImageDraw.Draw(paper)
    mono, small, tiny, big = font(30, "SansMono"), font(24, "SansMono"), font(17, "SansMono"), font(56, "Sans-Bold")
    y = 40
    d.text((350, y), "Cafe Noir", font=big, fill=(20, 20, 20), anchor="ma")
    y += 80
    d.text((350, y), "12 Rothschild Blvd, Tel Aviv", font=small, fill=(40, 40, 40), anchor="ma")
    y += 36
    d.text((350, y), "Tax ID 515239870", font=tiny, fill=(60, 60, 60), anchor="ma")
    y += 60
    d.text((40, y), "Date: 14/10/2026   21:12", font=small, fill=(30, 30, 30))
    y += 36
    d.text((40, y), "Table 7        Guests: 2", font=small, fill=(30, 30, 30))
    y += 60
    d.line((40, y, 660, y), fill=(90, 90, 90), width=2)
    y += 30
    items = [("2 x Shakshuka", "116.00"), ("1 x Green salad", "46.00"), ("2 x Lemonade", "36.00"),
             ("2 x Glass of wine", "84.00"), ("1 x Malabi", "32.00")]
    for name, amount in items:
        d.text((40, y), name, font=mono, fill=(25, 25, 25))
        d.text((660, y), amount, font=mono, fill=(25, 25, 25), anchor="ra")
        y += 56
    y += 10
    d.line((40, y, 660, y), fill=(90, 90, 90), width=2)
    y += 30
    for name, amount in [("Subtotal", "314.00"), ("Service 10%", "31.40")]:
        d.text((40, y), name, font=mono, fill=(25, 25, 25))
        d.text((660, y), amount, font=mono, fill=(25, 25, 25), anchor="ra")
        y += 56
    d.text((40, y), "TOTAL NIS", font=font(38, "SansMono-Bold"), fill=(10, 10, 10))
    d.text((660, y), "345.40", font=font(38, "SansMono-Bold"), fill=(10, 10, 10), anchor="ra")
    y += 80
    d.text((40, y), "VAT 18% included: 52.69", font=tiny, fill=(70, 70, 70))
    y += 50
    d.text((40, y), "VISA  **** **** **** 4417", font=font(20, "SansMono"), fill=(50, 50, 50))
    y += 90
    d.text((350, y), "Thank you! Come again", font=small, fill=(40, 40, 40), anchor="ma")
    paper = paper.rotate(1.2, resample=Image.BICUBIC, expand=True, fillcolor=(120, 116, 110))
    bg.paste(paper, (90, 70))
    shade = Image.linear_gradient("L").resize((W, H)).point(lambda v: 255 - v // 6)
    bg = Image.composite(bg, Image.new("RGB", (W, H), (60, 58, 55)), shade)
    gold = {"merchant": "Cafe Noir", "date": "2026-10-14", "currency": "ILS", "subtotal": 314.00, "tip": 31.40,
            "total": 345.40, "vat": 52.69, "alcohol_total": 84.00, "card_last4": "4417", "item_lines": 5, "guests": 2}
    L = H
    oracle = {"caption": "A restaurant receipt from Cafe Noir, Tel Aviv, total 345.40 NIS.", "fields": {
        "merchant": field("Cafe Noir", L, 56, "Cafe Nair"),
        "date": field("2026-10-14", L, 24, "2026-10-11"),
        "currency": field("ILS", L, 38, "USD"),
        "subtotal": field(314.00, L, 30, 374.00),
        "tip": field(31.40, L, 30, 37.40),
        "total": field(345.40, L, 38, 346.40),
        "vat": field(52.69, L, 17, None),
        "alcohol_total": field(84.00, L, 30, 64.00),
        "card_last4": field("4417", L, 20, "4477"),
        "item_lines": never(5, 8),  # counts quantities (2+1+2+2+1) instead of lines
        "guests": field(2, L, 24, None),
    }}
    return bg, gold, oracle


# ---------------------------------------------------------------- whiteboard
def whiteboard() -> tuple[Image.Image, dict, dict]:
    W, H = 2400, 1600
    rng = random.Random(21)
    img = Image.new("RGB", (W, H), (236, 238, 232))
    vign = Image.radial_gradient("L").resize((W, H))
    img = Image.composite(Image.new("RGB", (W, H), (200, 203, 196)), img, vign.point(lambda v: min(255, v)))
    d = ImageDraw.Draw(img)
    hand, title_f, note_f, date_f = font(46, "Sans-Oblique"), font(70, "Sans-BoldOblique"), font(30, "Sans-Oblique"), font(28, "Sans-Oblique")
    blue, black, red, green = (30, 60, 160), (30, 30, 35), (180, 40, 40), (30, 120, 60)
    d.text((140, 90), "Company Brain v2 (draft)", font=title_f, fill=black)
    d.text((2140, 110), "28/10", font=date_f, fill=black)
    boxes = {"Web App": (160, 420), "API Gateway": (720, 420), "Company Brain": (1300, 420),
             "pgvector": (1300, 1050), "Claude Haiku 5.5": (1880, 760), "Audit Log": (720, 1050)}
    rects = {}
    for name, (x, y) in boxes.items():
        w = d.textlength(name, font=hand) + 70
        r = (x, y, x + w, y + 120)
        rects[name] = r
        jit = [(x + rng.randint(-6, 6), y + rng.randint(-6, 6)), (r[2] + rng.randint(-6, 6), y + rng.randint(-6, 6)),
               (r[2] + rng.randint(-6, 6), r[3] + rng.randint(-6, 6)), (x + rng.randint(-6, 6), r[3] + rng.randint(-6, 6))]
        d.line(jit + [jit[0]], fill=blue if name != "Company Brain" else green, width=7)
        d.text((x + 35, y + 32), name, font=hand, fill=black)

    def arrow(a, b):
        ra, rb = rects[a], rects[b]
        ax, ay = (ra[0] + ra[2]) / 2, (ra[1] + ra[3]) / 2
        bx, by = (rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2
        # start / end on the box edges
        def edge(r, cx, cy, tx, ty):
            dx, dy = tx - cx, ty - cy
            sx = (r[2] - r[0]) / 2 / abs(dx) if dx else 1e9
            sy = (r[3] - r[1]) / 2 / abs(dy) if dy else 1e9
            s = min(sx, sy) * 1.08
            return cx + dx * s, cy + dy * s
        x1, y1 = edge(ra, ax, ay, bx, by)
        x2, y2 = edge(rb, bx, by, ax, ay)
        d.line((x1, y1, x2, y2), fill=red, width=6)
        ang = math.atan2(y2 - y1, x2 - x1)
        for side in (-0.45, 0.45):
            d.line((x2, y2, x2 - 40 * math.cos(ang + side), y2 - 40 * math.sin(ang + side)), fill=red, width=6)

    for a, b in [("Web App", "API Gateway"), ("API Gateway", "Company Brain"), ("Company Brain", "pgvector"),
                 ("Company Brain", "Claude Haiku 5.5"), ("API Gateway", "Audit Log")]:
        arrow(a, b)
    note = Image.new("RGB", (430, 200), (250, 228, 90))
    nd = ImageDraw.Draw(note)
    nd.text((24, 40), "TODO: add rate", font=note_f, fill=black)
    nd.text((24, 90), "limiter", font=note_f, fill=black)
    note = note.rotate(-6, expand=True, fillcolor=(236, 238, 232))
    img.paste(note, (1800, 1180))
    noise = Image.effect_noise((W, H), 18).convert("RGB")
    img = Image.blend(img, noise, 0.06).filter(ImageFilter.GaussianBlur(0.8))
    gold = {"title": "Company Brain v2 (draft)",
            "components": ["Web App", "API Gateway", "Company Brain", "pgvector", "Claude Haiku 5.5", "Audit Log"],
            "arrows": 5, "todo_note": "TODO: add rate limiter", "date": "28/10"}
    L = W
    oracle = {"caption": "A whiteboard sketch of the Company Brain v2 architecture with six boxes.", "fields": {
        "title": field(gold["title"], L, 70, "Company Brain v2 (dratt)"),
        "components": field(gold["components"], L, 46,
                            ["Web App", "API Gateway", "Company Brain", "pg vector", "Claude Haiku 3.5", "Audit Log"]),
        "arrows": never(5, 4),
        "todo_note": field(gold["todo_note"], L, 30, "TODO: add rate limit"),
        "date": field("28/10", L, 28, None),
    }}
    return img, gold, oracle


# ---------------------------------------------------------------- error dialog
def error_dialog() -> tuple[Image.Image, dict, dict]:
    W, H = 1280, 800
    img = Image.new("RGB", (W, H), (34, 72, 110))
    d = ImageDraw.Draw(img)
    d.rectangle((0, H - 44, W, H), fill=(28, 28, 32))
    x0, y0, x1, y1 = 290, 200, 990, 560
    d.rectangle((x0 + 8, y0 + 10, x1 + 8, y1 + 10), fill=(15, 30, 50))
    d.rectangle((x0, y0, x1, y1), fill=(246, 246, 246), outline=(160, 160, 160))
    d.rectangle((x0, y0, x1, y0 + 44), fill=(225, 228, 232))
    d.text((x0 + 18, y0 + 11), "Spendwise - Error", font=font(22, "Sans-Bold"), fill=(30, 30, 30))
    d.text((x1 - 34, y0 + 9), "x", font=font(24, "Sans"), fill=(80, 80, 80))
    d.ellipse((x0 + 30, y0 + 80, x0 + 90, y0 + 140), fill=(210, 50, 50))
    d.text((x0 + 60, y0 + 110), "!", font=font(40, "Sans-Bold"), fill="white", anchor="mm")
    d.text((x0 + 115, y0 + 78), "Upload failed: the receipt image is larger", font=font(20, "Sans"), fill=(20, 20, 20))
    d.text((x0 + 115, y0 + 106), "than 10 MB (12.4 MB).", font=font(20, "Sans"), fill=(20, 20, 20))
    d.text((x0 + 115, y0 + 156), "Error code: SPW-4013", font=font(18, "SansMono"), fill=(60, 60, 60))
    d.text((x0 + 115, y0 + 196), "Request ID: 7f3a-91c2-e04b", font=font(14, "SansMono"), fill=(120, 120, 120))
    d.text((x0 + 115, y0 + 222), "2026-10-30 09:41:07", font=font(13, "Sans"), fill=(120, 120, 120))
    for i, label in enumerate(["Retry", "Cancel"]):
        bx = x1 - 260 + i * 125
        d.rounded_rectangle((bx, y1 - 70, bx + 110, y1 - 28), 6, fill=(0, 103, 192) if i == 0 else (225, 225, 225))
        d.text((bx + 55, y1 - 49), label, font=font(18, "Sans"), fill="white" if i == 0 else (30, 30, 30), anchor="mm")
    gold = {"app_name": "Spendwise", "error_code": "SPW-4013",
            "message": "Upload failed: the receipt image is larger than 10 MB (12.4 MB).",
            "request_id": "7f3a-91c2-e04b", "buttons": ["Retry", "Cancel"], "timestamp": "2026-10-30 09:41:07"}
    L = W
    oracle = {"caption": "A Spendwise error dialog: the receipt upload failed because the image is over 10 MB.", "fields": {
        "app_name": field("Spendwise", L, 22, "Spendwlse"),
        "error_code": field("SPW-4013", L, 18, "SPW-4018"),
        "message": field(gold["message"], L, 20, "Upload failed: the receipt image is larger than 10 MB (12.1 MB)."),
        "request_id": field("7f3a-91c2-e04b", L, 14, "7f3a-91e2-e04b"),
        "buttons": field(["Retry", "Cancel"], L, 18, ["Retry", "Cancel"]),
        "timestamp": field("2026-10-30 09:41:07", L, 13, "2026-10-30 09:41:01"),
    }}
    return img, gold, oracle


def save(img: Image.Image, path: Path, oracle: dict, **kw) -> None:
    payload = json.dumps(oracle, ensure_ascii=False)
    if path.suffix == ".png":
        info = PngImagePlugin.PngInfo()
        info.add_text("mockllm-oracle", payload)
        img.save(path, "PNG", pnginfo=info, optimize=True)
    else:
        img.save(path, "JPEG", quality=kw.get("quality", 88), comment=b"mockllm-oracle:" + payload.encode("utf-8"))


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    golds = {}
    for name, make, fname in [("receipt", receipt, "receipt.png"), ("whiteboard", whiteboard, "whiteboard.jpg"),
                              ("error_dialog", error_dialog, "error_dialog.png")]:
        img, gold, oracle = make()
        save(img, IMAGES / fname, oracle)
        golds[name] = gold
        size = (IMAGES / fname).stat().st_size
        print(f"{fname:18} {img.size[0]}x{img.size[1]}  {size / 1024:7.1f} KB")
        for k, spec in oracle["fields"].items():
            print(f"   {k:14} legible from long edge {spec['min_long_edge']}" if spec["font_px"] else
                  f"   {k:14} (the mock always miscounts this one)")
    GOLD.write_text(json.dumps(golds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"gold answers -> {GOLD.relative_to(GOLD.parents[3])}")


if __name__ == "__main__":
    main()

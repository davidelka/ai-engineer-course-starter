"""Exercise 8: a PDF two ways: extracted text (lesson 9) vs pages the model SEES.

    python labs/21-multimodal/pdf_pages.py                 # free: extraction, a "scanned" copy, token estimates
    python labs/21-multimodal/pdf_pages.py --live          # + Claude count_tokens (free) and one question per file (~1 cent)

The file is data/acme/corpus/docs/fin-travel-2026.pdf, Acme's Travel Policy v2.0 (2 pages). Its
section 4 has a per-diem TABLE (destination / per diem per day): Standard cities $85,
High-cost cities $110, Berlin office visits 65 EUR. Section 3 says the Berlin hotel cap is 170
EUR per night.

Steps:
1. Text extraction with ragkit's PDF loader (lesson 9). Look at how the table comes out.
2. A "scanned" copy: each page rendered to an image and saved as an image-only PDF
   (results/fin-travel-2026-scanned.pdf). Text extraction now returns almost nothing: a
   text-only ingestion pipeline would silently index an empty document.
3. What each way costs in tokens: the text alone; the PDF as a document block (the provider
   renders every page as an image AND extracts its text); page images you render yourself.
4. --live: Anthropic count_tokens for both PDFs (free), and the same question asked over the
   original and over the scanned PDF.
"""

from __future__ import annotations

import argparse
import base64
import io
import os

import httpx

import _lab  # noqa: F401
from _lab import RESULTS, ROOT
from llmkit import ChatRequest, Document, Image, LLM, Message, load_dotenv
from llmkit.media import image_tokens, pdf_page_count
from ragkit.tokens import ApproxTokenizer

PDF = ROOT / "data" / "acme" / "corpus" / "docs" / "fin-travel-2026.pdf"
QUESTION = ("According to this travel policy, what is the per diem per day for a Berlin office visit, "
            "and what is the hotel cap per night in Berlin? Answer in one sentence.")


def extract_text(data: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)


def render_pages(data: bytes, dpi: int = 110):
    """Pages -> PIL images. pypdfium2 renders the real page; without it we draw the extracted
    text on blank pages (enough to make an image-only PDF for the demo)."""
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(data)
        return [doc[i].render(scale=dpi / 72).to_pil().convert("RGB") for i in range(len(doc))]
    except ImportError:
        from PIL import Image as PILImage, ImageDraw, ImageFont
        print("   (pypdfium2 not installed: drawing the extracted text instead of rendering the page)")
        from pypdf import PdfReader
        pages = []
        for p in PdfReader(io.BytesIO(data)).pages:
            img = PILImage.new("RGB", (910, 1287), "white")
            d = ImageDraw.Draw(img)
            f = ImageFont.load_default(size=15)
            for k, line in enumerate((p.extract_text() or "").splitlines()[:70]):
                d.text((60, 60 + 17 * k), line, font=f, fill="black")
            pages.append(img)
        return pages


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    load_dotenv(str(ROOT / ".env"))
    tok = ApproxTokenizer()
    data = PDF.read_bytes()

    print(f"1) {PDF.relative_to(ROOT)}: {len(data):,} bytes, {pdf_page_count(data)} pages")
    from ragkit.loaders import load_document
    doc = load_document(PDF)
    i = doc.text.find("Per diem per day")
    print(f"   ragkit (lesson 9) extracted {len(doc.text):,} characters (~{tok.count(doc.text)} tokens).")
    print("   The per-diem table as extracted text:")
    for line in doc.text[max(0, i - 40):i + 230].splitlines():
        print("      | " + line)

    print("\n2) a scanned copy (pages as pictures, no text layer)")
    pages = render_pages(data)
    scanned = RESULTS / "fin-travel-2026-scanned.pdf"
    pages[0].save(scanned, "PDF", save_all=True, append_images=pages[1:], resolution=110)
    sdata = scanned.read_bytes()
    stext = extract_text(sdata)
    print(f"   {scanned.relative_to(ROOT)}: {len(sdata):,} bytes; text extraction finds {len(stext.strip())} "
          "characters. Lesson 9's pipeline would index an EMPTY document, with no error.")

    print("\n3) tokens, three ways (estimates; --live measures Claude's)")
    print(f"   a. extracted text only:                  ~{tok.count(doc.text):6} tokens (no layout, no images)")
    w, h = pages[0].size
    for provider, model, detail in [("anthropic", "claude-haiku-5-5", None), ("openai", "gpt-5.4-mini", "high"),
                                    ("gemini", "gemini-3.6-flash", "medium")]:
        per = image_tokens(provider, model, w, h, detail).tokens
        print(f"   b. {provider:9} page images you render ({w}x{h}): {per:5} per page x {len(pages)} = {per * len(pages)}")
    print("   c. the PDF as a document block: each page = page image + its extracted text "
          "(Anthropic documents 1,500-3,000 text tokens per dense page, plus the image)."
          " Gemini bills 560 per page by default and does not bill the native text.")

    if not a.live:
        print("\nRun with --live to measure Claude's numbers and compare the answers.")
        return
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set in .env")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    llm = LLM("anthropic:claude-haiku-5-5")
    print("\n4) live: count_tokens (free) and one question per file")
    for label, pdf in [("original (text layer)", data), ("scanned (image only)", sdata)]:
        content = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                   "data": base64.b64encode(pdf).decode()}},
                   {"type": "text", "text": QUESTION}]
        n = httpx.post("https://api.anthropic.com/v1/messages/count_tokens", headers=headers, timeout=60, json={
            "model": "claude-haiku-5-5", "messages": [{"role": "user", "content": content}]}).json().get("input_tokens")
        r = llm.complete(ChatRequest(messages=[Message.user_with(Document(data=pdf, filename="travel.pdf"), QUESTION)],
                                     max_tokens=120))
        print(f"   {label:22} count_tokens={n}  answer ({r.usage.input_tokens} in, ${r.cost_usd or 0:.5f}): {r.text}")
    # the page images themselves, sent as images
    imgs = []
    for p in pages:
        buf = io.BytesIO()
        p.save(buf, "PNG")
        imgs.append(Image(data=buf.getvalue()))
    r = llm.complete(ChatRequest(messages=[Message.user_with(*imgs, QUESTION)], max_tokens=120))
    print(f"   {'page images (PNG)':22} answer ({r.usage.input_tokens} in, ${r.cost_usd or 0:.5f}): {r.text}")


if __name__ == "__main__":
    main()

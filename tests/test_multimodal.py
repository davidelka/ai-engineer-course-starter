"""Lesson 21: images and documents in llmkit (three providers) and in mockllm.

Most tests build images with the standard library only (a tiny PNG writer below), so the
suite does not need Pillow. JPEG / WebP / GIF tests use Pillow when it is installed.
"""

import base64
import io
import json
import random
import struct
import zlib

import pytest
from pydantic import BaseModel

from llmkit import LLM, ChatRequest, Document, Image, LLMError, Message, RetryPolicy
from llmkit.media import (anthropic_image_tokens, anthropic_resize, gemini_image_tokens, image_cost_usd, image_info,
                          image_tokens, openai_image_tokens, parse_data_url, pdf_page_count, sniff_media_type,
                          to_data_url)
from llmkit.providers.anthropic import AnthropicProvider
from llmkit.providers.gemini import GeminiProvider
from llmkit.providers.openai import OpenAIProvider
from llmkit.structured import complete_structured
from mockllm import MockConfig, start_in_thread
from mockllm.vision import read_oracle


# ---------------------------------------------------------------- helpers
def png(w: int, h: int, color=(255, 255, 255), text: dict | None = None) -> bytes:
    """A valid RGB PNG built with zlib only. text: extra tEXt chunks."""
    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    row = b"\x00" + bytes(color) * w
    raw = zlib.compress(row * h, 9)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    for k, v in (text or {}).items():
        out += chunk(b"tEXt", k.encode() + b"\x00" + v.encode())
    return out + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def fake_png_header(w: int, h: int) -> bytes:
    """Only the header (enough for size checks; never sent to a server)."""
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", w, h) + b"\x08\x02\x00\x00\x00"


def tiny_pdf(pages: int, text: str = "Hello Acme") -> bytes:
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [" + b" ".join(f"{3 + i} 0 R".encode() for i in range(pages)) +
            f"] /Count {pages} >>".encode()]
    for _ in range(pages):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {3 + pages} 0 R >>".encode())
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    body = b"%PDF-1.4\n"
    for i, o in enumerate(objs, 1):
        body += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    return body + b"trailer << /Root 1 0 R >>\n%%EOF\n"


@pytest.fixture(scope="module")
def server():
    srv, url = start_in_thread(MockConfig(ttft=0, tps=0))
    yield srv, url
    srv.shutdown()


@pytest.fixture
def mock(server):
    srv, url = server
    srv.state.cfg = MockConfig(ttft=0, tps=0, seed=1)
    srv.state.reset()
    return srv, url


def llm_for(url, provider="anthropic", model="mock-model"):
    return LLM(f"{provider}:{model}", api_key="t", base_url=url,
               retry=RetryPolicy(sleep=lambda s: None, rng=random.Random(0)))


# ---------------------------------------------------------------- sniffing
def test_png_header_sniffing_without_pillow():
    data = png(37, 21)
    assert sniff_media_type(data) == "image/png"
    info = image_info(data)
    assert (info.media_type, info.width, info.height) == ("image/png", 37, 21)


def test_non_images_are_rejected():
    with pytest.raises(ValueError):
        image_info(b"hello world, not an image")
    with pytest.raises(ValueError):
        image_info(tiny_pdf(1))
    assert sniff_media_type(tiny_pdf(1)) == "application/pdf"


@pytest.mark.parametrize("fmt,mt,kw", [("JPEG", "image/jpeg", {"quality": 70}), ("GIF", "image/gif", {}),
                                      ("WEBP", "image/webp", {"quality": 60}),
                                      ("WEBP", "image/webp", {"lossless": True})])
def test_pillow_formats(fmt, mt, kw):
    PIL = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    PIL.new("RGB", (321, 123), "navy").save(buf, fmt, **kw)
    info = image_info(buf.getvalue())
    assert (info.media_type, info.width, info.height) == (mt, 321, 123)


def test_pdf_page_count_and_data_urls():
    assert pdf_page_count(tiny_pdf(3)) == 3
    url = to_data_url("image/png", b"abc")
    assert url.startswith("data:image/png;base64,")
    assert parse_data_url(url) == ("image/png", b"abc")


# ---------------------------------------------------------------- token formulas (doc examples)
def test_anthropic_examples_from_the_docs():
    # standard tier: 1920x1080 -> 1456x819 = 1560 tokens; 4K -> same
    assert anthropic_resize(1920, 1080, "standard") == (1456, 819)
    assert anthropic_image_tokens(1920, 1080, "claude-haiku-4-5").tokens == 1560
    assert anthropic_image_tokens(3840, 2160, "claude-haiku-4-5").tokens == 1560
    # high-resolution tier (Claude 4.7+): 1920x1080 not resized = 2691; 4K -> 2576x1449 = 4784
    assert anthropic_image_tokens(1920, 1080, "claude-haiku-5-5").tokens == 2691
    est = anthropic_image_tokens(3840, 2160, "claude-opus-5-5")
    assert (est.width, est.height, est.tokens) == (2576, 1449, 4784)
    # 1000x1000 = 36 x 36 = 1296 (the docs' $1.30 per thousand images at $1/M)
    assert anthropic_image_tokens(1000, 1000, "claude-haiku-4-5").tokens == 1296
    assert round(image_cost_usd(1296, "claude-haiku-4-5") * 1000, 2) == 1.30


def test_anthropic_portrait_and_limits_hold():
    for w, h in [(1080, 1920), (5000, 300), (300, 5000), (8000, 8000), (2577, 10)]:
        for model in ("claude-haiku-4-5", "claude-haiku-5-5"):
            est = anthropic_image_tokens(w, h, model)
            long_max, tok_max = (2576, 4784) if model.endswith("5-5") else (1568, 1568)
            assert max(est.width, est.height) <= long_max and est.tokens <= tok_max
            assert (est.width >= est.height) == (w >= h)


def test_openai_patch_examples_from_the_docs():
    assert openai_image_tokens(1024, 1024, "gpt-6-astra", "high").tokens == 1229
    est = openai_image_tokens(2048, 2048, "gpt-6-astra", "high")
    assert (est.width, est.height, est.tokens) == (1600, 1600, 3000)
    assert openai_image_tokens(4096, 512, "gpt-6-astra", "high").tokens == 2458
    # gpt-5.4-mini: auto behaves like high (2048 px, 2500 patches, x1.2)
    assert openai_image_tokens(4000, 3000, "gpt-5.4-mini", "auto") == openai_image_tokens(4000, 3000, "gpt-5.4-mini", "high")
    assert openai_image_tokens(4000, 3000, "gpt-5.4-mini", "high").tokens <= 3000


def test_openai_tile_examples():
    assert openai_image_tokens(1024, 1024, "gpt-4o", "high").tokens == 765  # 85 + 4 x 170
    assert openai_image_tokens(2048, 4096, "gpt-4o", "high").tokens == 1105  # 85 + 6 x 170
    assert openai_image_tokens(4000, 4000, "gpt-4o", "low").tokens == 85


def test_gemini_rules():
    assert gemini_image_tokens(960, 540, "gemini-2.5-flash").tokens == 1548  # crop 360: 3 x 2 tiles x 258
    assert gemini_image_tokens(300, 200, "gemini-2.5-flash").tokens == 258
    assert gemini_image_tokens(4000, 3000, "gemini-3.6-flash").tokens == 1120
    assert gemini_image_tokens(4000, 3000, "gemini-3.6-flash", "low").tokens == 280
    assert image_tokens("gemini", "gemini-3.6-flash", 10, 10, "ultra_high").tokens == 2240


# ---------------------------------------------------------------- the Image / Document types
def test_image_type_basics():
    data = png(10, 20)
    im = Image(data=data)
    assert im.media_type == "image/png" and im.size == (10, 20)
    assert "bytes" in repr(im) and len(repr(im)) < 120
    with pytest.raises(ValueError):
        Image()
    with pytest.raises(ValueError):
        Image(data=data, url="https://x/y.png")
    assert Image.from_url("https://x/y.png").size is None
    d = Document(data=tiny_pdf(2), filename="a.pdf")
    assert d.pages == 2 and "a.pdf" in repr(d)


def test_user_with_and_text_stays_text():
    m = Message.user_with(Image(data=png(4, 4)), "What is this?")
    assert m.text == "What is this?" and len(m.media) == 1
    assert Message("user", "plain").media == []


# ---------------------------------------------------------------- wire shapes
def _req(*parts, **kw):
    return ChatRequest(messages=[Message.user_with(*parts)], **kw)


def test_anthropic_wire_shapes():
    data = png(8, 8)
    req = _req(Image(data=data, cache="5m"), Image.from_url("https://e.com/a.jpg"), Image(file_id="file_1"),
               Document(data=tiny_pdf(1), title="Policy"), "Describe")
    blocks = AnthropicProvider().build(req, "claude-haiku-5-5", "k", False).body["messages"][0]["content"]
    assert blocks[0] == {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                     "data": base64.b64encode(data).decode()},
                         "cache_control": {"type": "ephemeral"}}
    assert blocks[1]["source"] == {"type": "url", "url": "https://e.com/a.jpg"}
    assert blocks[2]["source"] == {"type": "file", "file_id": "file_1"}
    assert blocks[3]["type"] == "document" and blocks[3]["title"] == "Policy"
    assert blocks[3]["source"]["media_type"] == "application/pdf"
    assert blocks[4] == {"type": "text", "text": "Describe"}  # order kept: image first, then text


def test_openai_wire_shapes():
    data = png(8, 8)
    req = _req(Image(data=data, detail="low"), "Describe", Document(data=tiny_pdf(1), filename="p.pdf"),
               Image(file_id="file-9"))
    items = OpenAIProvider().build(req, "gpt-5.4-mini", "k", False).body["input"]
    assert len(items) == 1 and items[0]["role"] == "user"
    parts = items[0]["content"]
    assert parts[0] == {"type": "input_image", "image_url": to_data_url("image/png", data), "detail": "low"}
    assert parts[1] == {"type": "input_text", "text": "Describe"}
    assert parts[2]["type"] == "input_file" and parts[2]["filename"] == "p.pdf"
    assert parts[2]["file_data"].startswith("data:application/pdf;base64,")
    assert parts[3] == {"type": "input_image", "file_id": "file-9"}
    # without media the content stays one string, as before lesson 21
    req2 = ChatRequest(messages=[Message("user", [__import__("llmkit").Block("a"), __import__("llmkit").Block("b")])])
    assert OpenAIProvider().build(req2, "gpt-5.4-mini", "k", False).body["input"] == [{"role": "user", "content": "a\n\nb"}]


def test_openai_rejects_media_in_assistant_turns():
    req = ChatRequest(messages=[Message("user", "hi"), Message("assistant", [Image(data=png(2, 2))])])
    with pytest.raises(ValueError):
        OpenAIProvider().build(req, "gpt-5.4-mini", "k", False)


def test_gemini_wire_shapes():
    data = png(8, 8)
    req = _req(Image(data=data, detail="high"), Image.from_url("https://e.com/x.webp"), "Describe",
               Document(data=tiny_pdf(1)))
    parts = GeminiProvider().build(req, "gemini-3.6-flash", "k", False).body["contents"][0]["parts"]
    assert parts[0] == {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(data).decode()},
                        "mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"}}
    assert parts[1] == {"fileData": {"mimeType": "image/webp", "fileUri": "https://e.com/x.webp"}}
    assert parts[2] == {"text": "Describe"}
    assert parts[3]["inlineData"]["mimeType"] == "application/pdf"


# ---------------------------------------------------------------- local limit checks
def test_anthropic_limits_checked_before_sending():
    big = Image(data=fake_png_header(9000, 100))
    with pytest.raises(ValueError, match="8000"):
        AnthropicProvider().build(_req(big, "x"), "claude-haiku-5-5", "k", False)
    many = [Image(data=fake_png_header(3001, 100))] + [Image(data=fake_png_header(10, 10)) for _ in range(20)]
    with pytest.raises(ValueError, match="3000"):
        AnthropicProvider().build(_req(*many, "x"), "claude-haiku-5-5", "k", False)
    with pytest.raises(ValueError, match="PDF pages"):
        AnthropicProvider().build(_req(Document(data=tiny_pdf(101)), "x"), "claude-haiku-5-5", "k", False)
    # the same 3001 px image alone is fine
    AnthropicProvider().build(_req(Image(data=fake_png_header(3001, 100)), "x"), "claude-haiku-5-5", "k", False)


# ---------------------------------------------------------------- mockllm end to end
@pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini"])
def test_mock_reports_images_and_bills_tokens(mock, provider):
    _, url = mock
    data = png(1200, 1600)
    plain = llm_for(url, provider).complete(_req("What is the total?"))
    r = llm_for(url, provider).complete(_req(Image(data=data), "What is the total?"))
    assert "1 image(s)" in r.text and "1200x1600" in r.text
    model = {"anthropic": "mock-model", "openai": "gpt-5.4-mini", "gemini": "gemini-3.6-flash"}[provider]
    expected = image_tokens(provider, model, 1200, 1600).tokens
    # the image costs (about) its formula: the base64 text itself is not counted as tokens
    assert abs((r.usage.input_tokens - plain.usage.input_tokens) - expected) < 40


def test_mock_smaller_image_costs_less(mock):
    _, url = mock
    llm = llm_for(url)
    big = llm.complete(_req(Image(data=png(2000, 2000)), "x")).usage.input_tokens
    small = llm.complete(_req(Image(data=png(500, 500)), "x")).usage.input_tokens
    assert small < big / 4


def test_mock_rejects_mismatched_and_broken_images(mock):
    _, url = mock
    with pytest.raises(LLMError) as e:
        llm_for(url).complete(_req(Image(data=png(4, 4), media_type="image/jpeg"), "x"))
    assert e.value.status == 400 and "does not match" in str(e.value)
    body = {"model": "m", "max_tokens": 10, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(b"junk").decode()}},
        {"type": "text", "text": "x"}]}]}
    import httpx
    resp = httpx.post(url + "/v1/messages", json=body, headers={"x-api-key": "t", "anthropic-version": "2023-06-01"})
    assert resp.status_code == 400 and "Could not process image" in resp.text


def test_mock_documents(mock):
    _, url = mock
    r = llm_for(url, "openai").complete(_req(Document(data=tiny_pdf(3), filename="t.pdf"), "Summarize"))
    assert "1 document(s)" in r.text and "3 page(s)" in r.text


def test_mock_streaming_with_an_image(mock):
    _, url = mock
    events = list(llm_for(url).stream(_req(Image(data=png(64, 64)), "describe")))
    assert events[-1].type == "done" and "64x64" in events[-1].result.text


class Receipt(BaseModel):
    merchant: str
    total: str
    note: str | None = None


ORACLE = {"caption": "a receipt", "fields": {
    "merchant": {"value": "Cafe Noir", "min_long_edge": 300, "misread": "Cafe Nair"},
    "total": {"value": "412.50", "min_long_edge": 900, "misread": "412.80"}}}


def test_oracle_payload_round_trip_and_resolution(mock):
    _, url = mock
    sharp = png(1000, 1300, text={"mockllm-oracle": json.dumps(ORACLE)})
    assert read_oracle(sharp)["caption"] == "a receipt"
    small = png(500, 650, text={"mockllm-oracle": json.dumps(ORACLE)})
    llm = llm_for(url)
    v1 = complete_structured(llm, _req(Image(data=sharp), "extract"), Receipt).value
    v2 = complete_structured(llm, _req(Image(data=small), "extract"), Receipt).value
    assert (v1.merchant, v1.total) == ("Cafe Noir", "412.50")
    assert (v2.merchant, v2.total) == ("Cafe Noir", "412.80")  # small text misread at low resolution


def test_oracle_in_jpeg_comment(mock):
    PIL = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    PIL.new("RGB", (1200, 1500), "white").save(buf, "JPEG", comment=b"mockllm-oracle:" + json.dumps(ORACLE).encode())
    assert read_oracle(buf.getvalue())["fields"]["total"]["value"] == "412.50"


def test_gemini_cache_tells_images_apart(mock):
    srv, url = mock
    llm = llm_for(url, "gemini")
    pad = "policy text " * 2000  # above Gemini's implicit cache minimum
    a = png(32, 32, (255, 0, 0))
    b = png(32, 32, (0, 0, 255))
    llm.complete(_req(Image(data=a), pad + " Q1"))
    r = llm.complete(_req(Image(data=b), pad + " Q1"))
    assert r.usage.cached_input_tokens == 0  # a different image is a different prompt

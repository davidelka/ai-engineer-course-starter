"""Exercise 3: the image token calculator (mine.image_tokens), checked against the providers'
documented examples and against the reference (llmkit.media) on a grid of sizes."""

import pytest

import mine
from llmkit.media import image_tokens as reference

SIZES = [(1, 1), (28, 28), (29, 29), (320, 240), (384, 384), (385, 200), (900, 1800), (1000, 1000),
         (1080, 1920), (1240, 1754), (1280, 800), (1568, 1568), (1920, 1080), (2400, 1600), (2577, 10),
         (3840, 2160), (4032, 3024), (5000, 300), (300, 5000), (8000, 8000)]


def test_anthropic_doc_examples():
    assert mine.image_tokens("anthropic", "claude-haiku-4-5", 1000, 1000) == 1296
    assert mine.image_tokens("anthropic", "claude-haiku-4-5", 1920, 1080) == 1560
    assert mine.image_tokens("anthropic", "claude-haiku-5-5", 1920, 1080) == 2691
    assert mine.image_tokens("anthropic", "claude-opus-5-5", 3840, 2160) == 4784
    assert mine.image_tokens("anthropic", "mock-model", 1920, 1080) == 2691


def test_openai_doc_examples():
    assert mine.image_tokens("openai", "gpt-4o", 1024, 1024, "high") == 765
    assert mine.image_tokens("openai", "gpt-4o", 2048, 4096, "high") == 1105
    assert mine.image_tokens("openai", "gpt-4o", 4000, 4000, "low") == 85
    assert mine.image_tokens("openai", "gpt-5.4-mini", 1024, 1024, "high") == 1229  # 1024 patches x 1.2


def test_gemini_rules():
    assert mine.image_tokens("gemini", "gemini-2.5-flash", 960, 540) == 1548
    assert mine.image_tokens("gemini", "gemini-2.5-flash", 384, 384) == 258
    assert mine.image_tokens("gemini", "gemini-3.6-flash", 4000, 3000) == 1120
    assert mine.image_tokens("gemini", "gemini-3.6-flash", 10, 10, "low") == 280
    assert mine.image_tokens("gemini", "gemini-3.6-flash", 10, 10, "ultra_high") == 2240


@pytest.mark.parametrize("provider,model,detail", [
    ("anthropic", "claude-haiku-5-5", None), ("anthropic", "claude-haiku-4-5", None),
    ("openai", "gpt-5.4-mini", "low"), ("openai", "gpt-5.4-mini", "high"), ("openai", "gpt-5.4-mini", "auto"),
    ("openai", "gpt-5.4", "original"), ("openai", "gpt-5.4-nano", "high"), ("openai", "gpt-4o", "high"),
    ("openai", "gpt-4o", "low"), ("gemini", "gemini-2.5-flash", None), ("gemini", "gemini-3.6-flash", "medium"),
])
def test_matches_reference_on_a_grid(provider, model, detail):
    for w, h in SIZES:
        assert mine.image_tokens(provider, model, w, h, detail) == reference(provider, model, w, h, detail).tokens, (w, h)


def test_unknown_provider_or_model():
    with pytest.raises(ValueError):
        mine.image_tokens("acme", "x", 10, 10)
    with pytest.raises(ValueError):
        mine.image_tokens("openai", "davinci", 10, 10)

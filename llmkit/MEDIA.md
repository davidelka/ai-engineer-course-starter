# llmkit images and documents (lesson 21)

API reference for multimodal input in llmkit and mockllm. Wire shapes, limits and token
rules were checked against the provider docs in November 2026 (sources at the end). Token
numbers are estimates until you measure them: Anthropic `count_tokens` is free, and OpenAI and
Gemini report usage on every call.

## Types (llmkit/types.py)

- `Image(data=bytes | url=str | file_id=str, media_type="", detail=None, cache=None)`: exactly one
  source. `media_type` is sniffed from the bytes when empty (PNG, JPEG, GIF, WebP), so a mislabeled
  file is still sent correctly. `Image.from_path(p)`, `Image.from_url(u)`, `.size` (read from the
  header, no Pillow), `.base64`. `repr` never prints the bytes.
- `Document(data | url | file_id, media_type="application/pdf", filename="document.pdf", title=None,
  detail=None, cache=None)`: a PDF. `Document.from_path(p)`, `.pages` (rough count).
- `detail`: OpenAI `low | high | auto | original`; Gemini media resolution
  `low | medium | high | ultra_high` (sent as the part's `mediaResolution`). Anthropic has no such
  knob and ignores it.
- They are message parts like `Block`: `Message("user", [Image(...), Block("question")])`, or
  `Message.user_with(Image.from_path("r.png"), "What is the total?")` (strings become Blocks).
  `Message.media` lists them. `content_text()` still returns only the text.
- Plain-string messages and text-only part lists produce exactly the same wire format as before.
- `llmkit.structured.complete_structured(llm, ChatRequest(...with images...), Model)` works
  unchanged: structured extraction from images is just a request with an image part.

## llmkit/media.py

- `image_info(bytes) -> ImageInfo(media_type, width, height)`, `sniff_media_type`, `pdf_page_count`,
  `to_data_url`, `parse_data_url`.
- `image_tokens(provider, model, w, h, detail=None) -> TokenEstimate(tokens, width, height, method)`
  and the per-provider functions `anthropic_image_tokens`, `openai_image_tokens`, `gemini_image_tokens`,
  `anthropic_resize`. `image_cost_usd(tokens, model)` uses `pricing.PRICES`.
- `LIMITS`: the documented limits used by the adapters' local checks.

## Provider mapping

- **Anthropic** (`/v1/messages`): `{"type": "image", "source": {"type": "base64", "media_type", "data"}}`,
  or `{"type": "url", "url"}`, or `{"type": "file", "file_id"}` (Files API). PDFs:
  `{"type": "document", "source": {...same three...}, "title"?}`. `cache_control` on the block when
  `cache` is set. Order is kept: put images before the question (documented as best).
- **OpenAI Responses** (`/v1/responses`): a user item whose `content` is a list:
  `{"type": "input_text", "text"}`, `{"type": "input_image", "image_url": <https URL or data URL>, "detail"?}`
  or `{"type": "input_image", "file_id"}`, and `{"type": "input_file", "filename", "file_data": <data URL>}`
  / `file_url` / `file_id`. Media in an assistant turn raises ValueError.
- **Gemini** (`generateContent`): `{"inlineData": {"mimeType", "data"}}` for bytes,
  `{"fileData": {"mimeType", "fileUri"}}` for a Files API URI or an external URL, plus
  `"mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"}` when `detail` is set.

## Limits (checked locally before sending; ValueError)

- Anthropic: 10 MB per image as base64 (5 MB on Bedrock), 8000 px per side, up to 100 images per
  request on 200k-context models (600 on others), and above 20 image/document blocks every image must
  be at most 3000 px per side. PDFs: 100 pages per request under a 1M context (600 otherwise), 128 MB
  request. Formats: JPEG, PNG, GIF (first frame), WebP.
- OpenAI: 512 MB request, 1,500 images, 30,000 patches per image after resizing (rejected, not
  shrunk), files up to 50 MB in total per request. Formats: PNG, JPEG, WebP, non-animated GIF.
- Gemini: inline request 20 MB on the image page (the newer file-input page says 100 MB, 50 MB for
  PDFs; we use the stricter number), 3,600 images, PDFs up to 1000 pages and 50 MB. External URLs:
  15 MB, and a forum thread reports 403s on Gemini 3.5+, so prefer bytes or the Files API.

## Image tokens (how an image becomes input tokens)

- **Anthropic**: `ceil(w/28) * ceil(h/28)`, one token per 28x28 patch, after an automatic downscale.
  High-resolution tier (Claude 4.7 and later, so all 5.x models): long edge up to 2576 px and up to
  4784 tokens. Standard tier (older models): 1568 px and 1568 tokens. Examples from the docs:
  1000x1000 = 1296 tokens; 1920x1080 = 1560 (standard, resized to 1456x819) or 2691 (high-res);
  3840x2160 = 4784 (high-res, resized to 2576x1449). The resize steps are reconstructed from these
  examples; verify with `count_tokens`.
- **OpenAI**, patch models (gpt-5.2 and later, gpt-4.1-mini): fit the detail level's maximum
  dimension, count 32x32 patches, shrink to the patch budget, tokens = ceil(patches x multiplier)
  (1.2 for the gpt-5.x family, 1.62 for gpt-4.1-mini). gpt-5.4 / 5.4-mini / 5.4-nano: high and auto =
  2048 px and 2,500 patches; original = 6000 px and 10,000 patches; low = 2048 px and a 6,144-patch
  budget as documented (larger than high, which looks odd: measure it). Tile models (gpt-5.1, gpt-5,
  gpt-4o, gpt-4.1): fit 2048x2048, shortest side to 768, base + 512-px tiles x per-tile
  (85 + 170 per tile for gpt-4o), low = base only.
- **Gemini 3 and later**: a fixed budget per image set by media resolution: low 280, medium 560,
  high 1120, ultra_high 2240 (per part only); the default is 1120. PDFs: 560 per page by default
  (native text not billed). Gemini 2.x: 258 tokens for images up to 384 px, else 258 per tile.

## mockllm

`mockllm/vision.py`: image/document blocks in all three shapes are decoded, measured from their
bytes, validated like the real APIs (400 for a media_type mismatch, a broken image, more than 100
images, over-size, too many PDF pages) and billed with the formulas above (base64 text is not counted
as tokens). The answer lists what it saw: `mockllm saw 1 image(s): #1 image image/png 1200x1600,
2494 tokens`. URL / file sources are not fetched: they are billed a fixed 1000 tokens.

The **oracle**: a PNG tEXt chunk or JPEG comment with keyword `mockllm-oracle` holding
`{"caption", "fields": {name: {"value", "min_long_edge", "misread"}}}`. With structured output, the
mock fills matching top-level schema fields from it; a field whose `min_long_edge` is above the size
the provider actually looks at (after its resize) returns `misread`. This makes offline extraction
and resize experiments behave plausibly. Real models have no oracle.

## Not done yet

- Images inside tool results (`tool_result` content blocks with images; computer use), Anthropic
  Files API uploads and OpenAI file uploads (pass a `file_id` you uploaded yourself), audio input to
  LLMs (see voicekit for speech), video, and image generation.
- Async (servekit/async_llm.py) has no media support.

Sources: platform.claude.com/docs/en/build-with-claude/vision and /pdf-support;
developers.openai.com/api/docs/guides/images-vision and /file-inputs;
ai.google.dev/gemini-api/docs/image-understanding, /media-resolution, /document-processing,
/interactions/file-input-methods, and ai.google.dev/api/generate-content (Part, Blob, FileData,
MediaResolution).

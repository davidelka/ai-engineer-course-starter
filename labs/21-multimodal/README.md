# מעבדה 21: Multimodal AI Applications

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r labs/21-multimodal/requirements.txt   # Pillow, pypdf, pypdfium2, jiwer
python -m pytest -q                                      # בדיקות הסביבה, כולל tests/test_multimodal*.py
python -m pytest -q labs/21-multimodal/tests             # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

כל התרגילים רצים בחינם מול mockllm ומתאמים מדומים. הרצה חיה של כל המעבדה (Claude Haiku 5.5 ו-OpenAI לאודיו) עולה בערך 5 עד 8 סנטים.

## מה חדש

- **llmkit מקבל תמונות ו-PDF** בשלושת הספקים. המסמך המלא הוא `llmkit/MEDIA.md`. בקצרה:
  - `Image(data=..., url=..., file_id=..., detail=...)` ו-`Document(...)` הם חלקים של הודעה, בדיוק כמו `Block`. הדרך הנוחה: `Message.user_with(Image.from_path("r.png"), "What is the total?")`.
  - סוג הקובץ נקרא מתוך הבייטים עצמם, לא משם הקובץ. גודל התמונה נקרא מהכותרת, בלי Pillow.
  - לפני השליחה llmkit בודק את המגבלות המתועדות (גודל, מספר תמונות, עמודי PDF) ונכשל מקומית עם הודעה ברורה, במקום 400 אחרי העלאה של 30 MB.
  - `llmkit.media.image_tokens(provider, model, w, h, detail)` מחשב כמה טוקנים תמונה עולה, לפי הנוסחה של כל ספק.
  - `llmkit.structured.complete_structured` עובד עם תמונות בלי שינוי: מעבירים `ChatRequest` שיש בו תמונה.
- **mockllm רואה תמונות**: הוא קורא את הגודל האמיתי מהבייטים, מחייב טוקנים לפי הנוסחה של הספק, מחזיר את שגיאות ה-400 של ה-API האמיתי (סוג קובץ שלא תואם, תמונה שבורה, יותר מדי עמודים), ועונה "mockllm saw 1 image(s): ...". בתמונות של המעבדה יש "oracle" קטן שרק ה-mock קורא: הוא אומר מאיזה גודל כל שדה קריא, כך שגם בלי מודל אמיתי הקטנה מוגזמת מורידה דיוק.
- **החבילה החדשה `voicekit/`** (התיעוד ב-`voicekit/README.md`): שני ports, `STT` ו-`TTS`, ומתאמים מאחוריהם: OpenAI (תמלול ודיבור), מקומי (faster-whisper עם מודל עברית של ivrit.ai, ו-Piper עם הקול העברי היחיד שלו), ו-Fake שרץ בלי רשת. יש בה גם `VoicePipeline` שמודד כל שלב, `wer` ו-`normalize_hebrew`, ו-`reading_feedback` למשוב קריאה. זו התשתית של פרויקט הגמר F2, המורה לעברית מדוברת.
- **`llmkit/fields.py`**: ניקוד של חילוץ שדה אחרי שדה (קוד הייחוס של תרגיל 2).
- **`mine.py`**: הקוד שלך לתרגילים 2, 3 ו-5.

## הנתונים שהתרגילים עובדים עליהם

- **שלוש תמונות סינתטיות של Acme** ב-`labs/21-multimodal/data/images/`, והתשובות הנכונות ב-`data/gold.json`. הסכמות של כל אחת ב-`acme_vision.py`. את התמונות יוצר `make_images.py` (הן כבר בריפו):
  - `receipt.png`, 900x1800: קבלה מ-Cafe Noir בתל אביב. תאריך 14/10/2026 (יום לפני חודש), 5 שורות פריטים, Subtotal 314.00, Service 10% 31.40, TOTAL NIS 345.40, שורת מע"מ קטנה "VAT 18% included: 52.69", כרטיס VISA שמסתיים ב-4417, Guests: 2, ושתי כוסות יין ב-84.00.
  - `whiteboard.jpg`, 2400x1600: צילום של לוח עם הכותרת "Company Brain v2 (draft)", שש קופסאות (Web App, API Gateway, Company Brain, pgvector, Claude Haiku 5.5, Audit Log), חמישה חצים, פתק צהוב "TODO: add rate limiter" ותאריך 28/10.
  - `error_dialog.png`, 1280x800: צילום מסך של שגיאה ב-Spendwise, מערכת ההוצאות של Acme: קוד SPW-4013, ההודעה "Upload failed: the receipt image is larger than 10 MB (12.4 MB).", Request ID קטן ואפור, חותמת זמן, וכפתורים Retry ו-Cancel.
- **כללי הארוחות של Acme**, מתוך `data/acme/corpus/docs/hr-expenses.md`: ארוחה עם לקוחות עד 250 ש"ח לאדם כולל טיפ, ואלכוהול רק בארוחה עם לקוחות ולא יותר מ-30% מסכום הארוחה.
- **מדיניות הנסיעות** `data/acme/corpus/docs/fin-travel-2026.pdf` (שני עמודים): בסעיף 4 טבלת per diem: ערים רגילות $85, ערים יקרות $110, ביקור במשרד בברלין 65 EUR. בסעיף 3: תקרת מלון בברלין 170 EUR ללילה.

## התרגילים

**1. תמונה ל-Claude, ב-HTTP גולמי וב-llmkit.** הסקריפט מדפיס את ה-JSON של הבקשה (ה-base64 מקוצר), את התשובה ואת ה-usage, ליד ההערכה של הנוסחה. `--count-only` משתמש ב-count_tokens, שהוא חינמי.

```bash
python labs/21-multimodal/send_image.py --mock
python labs/21-multimodal/send_image.py
python labs/21-multimodal/send_image.py --count-only --image whiteboard.jpg
python labs/21-multimodal/send_image.py --mock --provider openai --image error_dialog.png --question "What error code is shown?"
```

**2. חילוץ מובנה מתמונות, עם דיוק לכל שדה.** ממש את `normalize_field` ואת `field_accuracy` ב-`mine.py`. אחר כך הרץ את החילוץ על שלוש התמונות. בסוף הוא בודק את הקבלה מול כללי הארוחות.

```bash
python -m pytest -q labs/21-multimodal/tests/test_ex2_fields.py
python labs/21-multimodal/extract_eval.py --mine
python labs/21-multimodal/extract_eval.py --model anthropic:claude-haiku-5-5 --runs 3
```

**3. מחשבון עלות של תמונה.** ממש את `image_tokens` ב-`mine.py`: Anthropic (שתי הרמות), OpenAI (מודלים של patches ומודל של tiles), ו-Gemini (2.x ו-3). אחר כך השווה את המחשבון שלך למדידה: count_tokens של Anthropic בחינם, ו-usage של OpenAI בפחות מסנט.

```bash
python -m pytest -q labs/21-multimodal/tests/test_ex3_tokens.py
python labs/21-multimodal/token_cost.py --mine
python labs/21-multimodal/token_cost.py --live
python labs/21-multimodal/token_cost.py --live-openai
```

**4. הקטנה ודחיסה: מה חוסכים ומה נשבר.** לכל תמונה, שבעה גדלים וארבעה פורמטים: גודל הקובץ, הטוקנים, העלות לאלף תמונות, והדיוק של חילוץ אמיתי. שים לב מה משנה טוקנים (פיקסלים) ומה משנה רק בייטים (פורמט ואיכות).

```bash
python labs/21-multimodal/resize_sweep.py
python labs/21-multimodal/resize_sweep.py --provider openai --image error_dialog
python labs/21-multimodal/resize_sweep.py --model anthropic:claude-haiku-5-5 --image receipt
```

**5. WER בעברית.** ממש את `normalize_hebrew` ואת `wer` ב-`mine.py`. אחר כך הרץ את הדוגמאות, ובדוק אילו "שגיאות" נעלמות אחרי נרמול ואילו אמיתיות.

```bash
python -m pytest -q labs/21-multimodal/tests/test_ex5_wer.py
python labs/21-multimodal/wer_demo.py --mine
```

**6. הלוך-חזור קולי בעברית.** משפט של "תלמיד" עובר TTS, אחר כך STT, ציון WER ומשוב קריאה. אחר כך מורה (LLM) עונה, והתשובה עוברת שוב TTS. קובצי האודיו נשמרים ב-`results/`, ושווה להקשיב להם.

```bash
python labs/21-multimodal/voice_roundtrip.py
python labs/21-multimodal/voice_roundtrip.py --live
python labs/21-multimodal/voice_roundtrip.py --live --stt-model whisper-1 --words
python labs/21-multimodal/voice_roundtrip.py --live --stt-model gpt-4o-mini-transcribe --confidence
```

**7. תקציב השהיה של תור קולי.** אותו תור, פעם ברצף ופעם ב-streaming, עם מדידה של כל שלב וציר זמן. נסה מודל איטי יותר (`--llm-ttft 1.2`), וחפש איזה שלב הכי משתלם לקצר.

```bash
python labs/21-multimodal/latency_budget.py
python labs/21-multimodal/latency_budget.py --llm-ttft 1.2 --tts-ttfb 0.6
python labs/21-multimodal/latency_budget.py --live
```

**8. PDF: טקסט שחולץ מול עמודים שהמודל רואה.** מדיניות הנסיעות עוברת חילוץ טקסט עם ragkit משיעור 9. אחר כך נוצר עותק "סרוק" בלי שכבת טקסט, והחילוץ מחזיר מסמך ריק בלי שום שגיאה. עם `--live` שואלים את Claude אותה שאלה על שני הקבצים.

```bash
python labs/21-multimodal/pdf_pages.py
python labs/21-multimodal/pdf_pages.py --live
```

## כללים

- הרצה חיה של כל המעבדה עולה בערך 5 עד 8 סנטים: Haiku 5.5 זול מאוד לתמונות, ו-TTS של OpenAI הוא החלק היקר.
- את קוד הייחוס ב-`llmkit/fields.py`, ב-`llmkit/media.py` וב-`voicekit/text.py` אל תקרא לפני שהבדיקות שלך עוברות.
- `results/` לא נכנס ל-git.
- תמונות וקולות הם מידע אישי. התמונות כאן סינתטיות. בתמונות אמיתיות, `prepare_image` ב-`_lab.py` מוחק את כל ה-metadata (EXIF, מיקום GPS) לפני השליחה.
- ה-TTS של OpenAI (`gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`) מפסיק לעבוד ב-6 בינואר 2027. אם תריץ אחרי התאריך הזה, תרגילים 6 ו-7 יעבדו רק עם `--tts fake` או `--tts piper`.

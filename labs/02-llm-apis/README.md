# מעבדה 2: LLM APIs and Model Integration

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
git pull
source .venv/bin/activate
uv pip install -r requirements.txt
python -m pytest -q                       # בדיקות הסביבה: llmkit מול השרת המדומה, חינם
python -m pytest -q labs/02-llm-apis/tests   # הבדיקות של התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

## מה יש כאן

- **`llmkit/`** (בשורש הריפו): ה-adapter האחיד לשלושת הספקים. httpx ישיר, בלי SDK, כדי שכלום לא יוסתר: גרסת ה-API מקובעת בקוד, ה-retries במקום אחד, וכל תוצאה מחזירה טקסט, סיבת עצירה מנורמלת, טוקנים, עלות, זמן, TTFT ו-request-id. ישמש אותנו בכל הקורס.
- **`mockllm/`** (בשורש הריפו): שרת מקומי שמדבר בפורמט של Anthropic, OpenAI ו-Gemini, כולל סטרימינג, ונכשל בדיוק איך שתבקש: `--fail-rate`, `--fail-first`, `--status`, `--retry-after`, `--truncate-after`, `--error-after`, `--malformed-rate`, `--latency`, `--ttft`, `--tps`. אפשר לשנות תקלות תוך כדי ריצה ב-`POST /__admin/config`, ולראות מונים ב-`GET /__admin/stats`.
- **`mine.py`**: הקוד שלך. שלוש פונקציות עם TODO, לתרגילים 3, 4 ו-5.
- **`raw_http.py`** ו-**`curl_examples.sh`**: אותה בקשה בלי SDK, עם כל ה-headers וכל אירוע בזרם.
- **`bench.py`**: מדידת TTFT, זמן כולל (p50, p95), טוקנים לשנייה ועלות ל-1,000 משימות.
- **`retry_demo.py`**: מריץ את מדיניות ה-retry שלך מול שרת שנכשל, ומדפיס כל המתנה.
- **`hr_via_llmkit.py`**: עוזר ה-HR משיעור 1, דרך llmkit.

### מחרוזת המודל

כל הכלים מקבלים מודל בפורמט `provider:model`:

- `anthropic:claude-haiku-5-5`, `openai:gpt-5.4-mini`, `gemini:gemini-3.6-flash`: הספקים האמיתיים (צריך מפתח ב-`.env`).
- `mock:mock-model`, `mock-openai:mock-model`, `mock-gemini:mock-model`: השרת המדומה בפורמט של כל ספק. בלי מפתח ובלי עלות. צריך שהשרת ירוץ: `python -m mockllm`.
- ב-bench אפשר להוסיף מאמץ: `anthropic:claude-haiku-5-5@high`.

## התרגילים

**1. בקשה גולמית.** הרץ, וקרא את כל ה-headers שחזרו. מצא את `request-id` ואת מגבלות הקצב. כמה טוקני פלט מותר לך לדקה, ומה היחס למגבלת הקלט?
```bash
python labs/02-llm-apis/raw_http.py --provider anthropic --show-body
```

**2. קורא SSE.** הרץ עם `--stream` וראה את סדר האירועים ואת הזמן של כל אחד. אחר כך, בטרמינל אחר, הפעל את השרת המדומה עם זרם שנקטע, ושלח אליו. מה חסר בסוף הזרם, ואיך קוד היה יודע שהתשובה לא שלמה?
```bash
python labs/02-llm-apis/raw_http.py --provider anthropic --stream
python -m mockllm --truncate-after 5                                   # טרמינל 2
python labs/02-llm-apis/raw_http.py --provider anthropic --stream --mock
```

**3. סיווג שגיאות.** ממש את `classify_error` ב-`mine.py`.
```bash
python -m pytest -q labs/02-llm-apis/tests/test_ex3_errors.py
```

**4. Backoff עם jitter.** ממש את `backoff_delay`. כשהבדיקות עוברות, הרץ את המדיניות שלך מול שרת שנכשל ב-40% מהבקשות וצפה בהמתנות.
```bash
python -m pytest -q labs/02-llm-apis/tests/test_ex4_backoff.py
python -m mockllm --fail-rate 0.4 --status 529                         # טרמינל 2
python labs/02-llm-apis/retry_demo.py --calls 20
```
נסה גם `--status 429 --retry-after 3`, ו-`--status 400`. מה ההבדל בהתנהגות?

**5. סטרימינג אחיד.** ממש את `openai_event_to_item`. הבדיקה האחרונה מריצה את אותה תשובה בפורמט של Anthropic ובפורמט של OpenAI, ודורשת תוצאה זהה.
```bash
python -m pytest -q labs/02-llm-apis/tests/test_ex5_stream.py
```

**6. Benchmark.** השווה effort נמוך מול גבוה ב-Haiku 5.5 (ואם יש לך מפתחות, גם ספק נוסף). כתוב שלוש שורות: מה משתנה ב-TTFT, מה בזמן הכולל, ומה בעלות ל-1,000 משימות.
```bash
python labs/02-llm-apis/bench.py --models anthropic:claude-haiku-5-5@low,anthropic:claude-haiku-5-5@high --runs 10
```

**7. החלפת ספק.** הרץ את עוזר ה-HR שלך מול Claude, ואז החלף ספק רק ב-`--model`. בלי מפתח נוסף, השתמש ב-`mock-openai:mock-model` (התשובות מזויפות, אבל רואים שהצנרת עובדת). כמה שורות קוד שינית?
```bash
python labs/02-llm-apis/hr_via_llmkit.py --model anthropic:claude-haiku-5-5
python labs/02-llm-apis/hr_via_llmkit.py --model mock-openai:mock-model
```

## כללים

- המפתחות רק ב-`.env`. הסקריפטים מסתירים אותם בהדפסה (`sk-ant-…`).
- `bench.py` עם `--runs 10` על Haiku 5.5 עולה פחות מסנט. בכל זאת, התחל עם `--runs 3`.
- את קוד הייחוס ב-`llmkit/` אל תקרא לפני שהבדיקות שלך עוברות.

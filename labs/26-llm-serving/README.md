# מעבדה 26: LLM Serving and API Design

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל. כמעט כל המעבדה רצה בחינם מול השרת המדומה. רק תרגיל 8 קורא ל-Claude Haiku 5.5, בבקשה אחת שעולה בערך שתי עשיריות של סנט.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r labs/26-llm-serving/requirements.txt   # fastapi, uvicorn, locust, matplotlib
python -m pytest -q tests/test_servekit.py                # בדיקות הסביבה של servekit
python -m pytest -q labs/26-llm-serving/tests             # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

ברוב התרגילים צריך שני טרמינלים פתוחים, ולפעמים שלושה:

- **טרמינל 1, השרת המדומה:** `python -m servekit.mock`. זה mockllm הרגיל, עם תוספת אחת: הוא סופר, לכל תשובת סטרימינג, אם היא הגיעה עד הסוף (`completed`) או שהלקוח התנתק באמצע (`aborted`). הספירה מופיעה ב-`GET http://127.0.0.1:8765/__admin/stats`, תחת `streams_detail`.
- **טרמינל 2, השירות:** `python -m servekit`. זה Company Brain API, על פורט 8000.
- **טרמינל 3:** הפקודות של התרגיל.

## מה חדש

- **`servekit/`**: חבילה חדשה, שהיא השירות עצמו. אלה המודולים שלה:
  - `app.py`: אפליקציית FastAPI עם `POST /v1/answer` (JSON), `POST /v1/answer/stream` (SSE), `GET /healthz`, `GET /readyz` ו-`GET /admin/stats`.
  - `async_llm.py`: שלוש דרכים לקרוא ל-llmkit מתוך שרת async. `AsyncLLM` הוא לקוח async אמיתי מעל אותם adapters של llmkit. `threaded_stream` מריץ את llmkit הסינכרוני ב-threadpool. `leaky_stream` הוא הבאג שהשיעור עוסק בו, והוא שם כדי שתוכל למדוד אותו.
  - `ratelimit.py`, `gate.py`, `idempotency.py`: מימושי הייחוס של שלושת התרגילים שלך.
  - `problems.py`: חוזה השגיאות. כל שגיאה חוזרת כ-`application/problem+json` לפי RFC 9457.
  - `logs.py`: מזהה בקשה (request id) ושורת לוג אחת ב-JSON לכל בקשה.
  - `brain.py`: הלוגיקה של Company Brain v0. חיפוש מילות מפתח פשוט במסמכי Acme שב-`data/acme/`, ופרומפט שמבקש תשובה עם מקורות. בשלב 2 של הפרויקט מחליפים את החיפוש ב-ragkit, וה-API לא משתנה.
  - `mock.py`: השרת המדומה עם ספירת הסטרימים.
  - `loadtest.py`: קריאת ה-CSV של locust, מציאת נקודת הברך, וציור הגרף.
- **`labs/26-llm-serving/`**:
  - `mine.py`: הקוד שלך לתרגילים 2, 3 ו-6.
  - `serve.py`: מריץ את השירות על הקוד שלך מ-`mine.py`.
  - `client.py`: לקוח Python קטן, שמודד TTFT מצד הלקוח.
  - `burst.py`: שולח פרץ של בקשות ומראה מה חזר.
  - `cancel_demo.py`: מתנתק באמצע סטרים ובודק מה קרה למעלה, אצל ספק המודל.
  - `locustfile.py` ו-`sweep.py`: בדיקת עומס.
  - `errors_tour.py`: מפעיל כל סוג שגיאה ומדפיס את מה שהלקוח רואה.

## החוזה של השירות, בקצרה

- **אימות:** `Authorization: Bearer <key>`. מפתחות הפיתוח הם `dev-key-alice` ו-`dev-key-bob`. עם `--load-test-keys N` השירות מקבל גם את `load-0` עד `load-(N-1)`, מפתח אחד לכל משתמש מדומה בבדיקת העומס.
- **גוף הבקשה בשני ה-endpoints:** `{"question": "...", "max_tokens": 400}`. שדה לא מוכר נדחה עם 422.
- **אירועי הסטרים:** `meta` (מזהה, מודל, מקורות), הרבה `token`, ובסוף `done` (usage, עלות, latency, ttft). אם משהו נשבר אחרי שהסטרים התחיל, מגיע אירוע `error` עם גוף problem+json, כי את ה-200 כבר אי אפשר לשנות.
- **סדר הבדיקות בכל בקשה:** אימות, rate limit לפי מפתח, idempotency, שער מקביליות, ואז הקריאה למודל עם deadline. כל סירוב קורה לפני שהוצאנו כסף, ולפני שנשלח 200.
- **ברירות מחדל:** `--max-concurrency 8 --max-queue 16 --queue-timeout 2 --rate 2 --burst 5`.

## התרגילים

**1. להריץ את השירות ולהזרים תשובה.** הרם את השרת המדומה ואת השירות, ושלח שאלה פעם עם curl ופעם עם הלקוח ב-Python. הדגל `-N` של curl מכבה את ה-buffering שלו, וכך האירועים מודפסים ברגע שהם מגיעים. בלעדיו תראה את כל התשובה בבת אחת בסוף. פתח גם את `http://127.0.0.1:8000/docs` וראה את הסכמות ש-FastAPI הפיק מהמודלים של Pydantic, כולל תגובות השגיאה. ענה: מה ההפרש בין ה-TTFT שהלקוח מדד לבין ה-TTFT שהשירות מדד מול השרת המדומה, ומה יושב בהפרש הזה?

```bash
python -m servekit.mock                         # טרמינל 1
python -m servekit                              # טרמינל 2
curl -N -X POST http://127.0.0.1:8000/v1/answer/stream \
  -H 'Authorization: Bearer dev-key-alice' -H 'Content-Type: application/json' \
  -d '{"question": "How many vacation days do I get in my first year?"}'
python labs/26-llm-serving/client.py "How many vacation days do I get in my first year?"
python labs/26-llm-serving/client.py --json "Who approves admin access to GitHub?"
```

**2. Rate limiter לפי מפתח (קוד).** ממש את `TokenBucket` ב-`mine.py`. הדלי מחזיק עד `burst` אסימונים ומתמלא בקצב של `rate` אסימונים לשנייה. כל בקשה לוקחת אסימון אחד. כשאין, הבקשה נדחית, והתשובה אומרת בדיוק כמה זמן לחכות. כל הכללים כתובים ב-docstring. כשהבדיקות עוברות, הרץ את השירות על הדלי שלך ושלח 12 בקשות ברצף ממפתח אחד. אמורות לעבור 5, אחריהן 429 עם `Retry-After`, ואז שוב בקשה עוברת מדי פעם, כשהדלי מתמלא. נסה שוב עם `--sleep 0.5`: למה עכשיו כמעט הכל עובר?

```bash
python -m pytest -q labs/26-llm-serving/tests/test_ex2_bucket.py
python labs/26-llm-serving/serve.py --mine limiter          # טרמינל 2, במקום python -m servekit
python labs/26-llm-serving/burst.py --n 12
python labs/26-llm-serving/burst.py --n 12 --sleep 0.5
```

**3. שער מקביליות עם תור חסום (קוד).** ממש את `acquire` ואת `retry_after` ב-`ConcurrencyGate`. עד `limit` בקשות רצות במקביל. עד `max_queue` נוספות מחכות, כל אחת לכל היותר `queue_timeout` שניות, וכל השאר נדחות מיד. בתשובה עם 429 צריך לבוא `Retry-After`. כשהבדיקות עוברות, הרץ את השירות על השער שלך עם 4 מקומות ותור של 4, עם rate limit גבוה כדי שהוא לא יפריע, ושלח 20 סטרימים בבת אחת. אמורים להגיע 4 שרצו מיד, 4 שחיכו בתור, ו-12 שנדחו מיד. ואם השרת המדומה איטי יותר (`--tps 10`), חלק מאלה שבתור יידחו אחרי שתי שניות של המתנה. למה זה גרוע יותר מדחייה מיידית?

```bash
python -m pytest -q labs/26-llm-serving/tests/test_ex3_gate.py
python labs/26-llm-serving/serve.py --mine gate --max-concurrency 4 --max-queue 4 --rate 100 --burst 100 --load-test-keys 64
python labs/26-llm-serving/burst.py --n 20 --parallel --load-keys
```

**4. להוכיח שניתוק עוצר את הזרם למעלה.** משתמש שסגר את הלשונית באמצע תשובה לא צריך לעלות לך עוד טוקנים. תריץ את השרת המדומה עם תשובה של 5 שניות, ואת השירות בשלושה מצבים, אחד אחרי השני. `cancel_demo.py` קורא 10 טוקנים, מתנתק, ובודק את המונים בשני הצדדים:
- **`async`:** הלקוח האסינכרוני של servekit. מצפים ל-`aborted: 1` כמעט מיד.
- **`thread`:** llmkit הסינכרוני ב-threadpool. גם כאן `aborted: 1`, אבל רק אחרי שה-thread מסיים את הטוקן הנוכחי.
- **`leaky`:** משימת רקע שקוראת מהספק לתוך תור לא חסום. השירות מדווח `closed_early: 1` ונראה תקין, אבל אצל השרת המדומה הסטרים מסומן `completed` עם כל 100 הטוקנים.

שים לב במיוחד למצב השלישי: המדדים של השירות עצמו משקרים, והאמת נמצאת רק אצל ה-upstream. ענה: באיזו שורה ב-`servekit/async_llm.py` נמצא הבאג, ומה הייתה התיקון המינימלי?

```bash
python -m servekit.mock --ttft 0.2 --tps 20 --words 100            # טרמינל 1: תשובה של 5 שניות
python -m servekit --stream-mode async                              # טרמינל 2 (אחר כך thread, ואחר כך leaky)
python labs/26-llm-serving/cancel_demo.py --after 10
```

**5. בדיקת עומס: p50, p95, TTFT ונקודת הברך.** locust מריץ משתמשים מדומים, שכל אחד מהם שואל שאלה, קורא את הסטרים עד הסוף, חושב רגע, וחוזר חלילה. ה-locustfile מודד בעצמו שני מספרים: TTFT, כלומר הזמן עד אירוע ה-`token` הראשון, ו-`stream total`, כלומר הזמן עד `done`. הוא מודד אותם בעצמו, כי עם `stream=True` הטיימר של locust עוצר כבר כשמגיעות הכותרות. `sweep.py` מריץ את locust ב-1, 2, 4, 8, 16, 32 ו-64 משתמשים, 20 שניות לכל רמה, וכותב את `results/sweep.csv` ואת `results/sweep.png`.

עם ההגדרות למטה, כל תשובה לוקחת בערך 1.8 שניות: 0.3 שניות עד הטוקן הראשון, ועוד 60 טוקנים בקצב של 40 לשנייה. השער מאפשר 8 בקשות במקביל. לפני שאתה מריץ, חשב לפי חוק Little (שקופית 13) מה התפוקה המקסימלית, ובאיזו רמה של משתמשים תופיע הברך. אחר כך הרץ, והשווה. בהרצה שלנו, בארגז החול, הברך הופיעה ב-8 משתמשים, עם 3.5 סטרימים לשנייה ו-p95 של 2 שניות. ב-16 משתמשים התפוקה נשארה בערך 4 לשנייה, אבל ה-TTFT קפץ מ-0.3 ל-1.8 שניות, כי בקשות חיכו בתור. מ-32 משתמשים התחילו דחיות 429.

```bash
python -m servekit.mock --ttft 0.3 --tps 40 --words 60                                       # טרמינל 1
python -m servekit --max-concurrency 8 --max-queue 16 --rate 100 --burst 100 --load-test-keys 128   # טרמינל 2
python labs/26-llm-serving/sweep.py
locust -f labs/26-llm-serving/locustfile.py --host http://127.0.0.1:8000   # רשות: ממשק הדפדפן ב-http://localhost:8089
```

**6. Idempotency-Key (קוד).** ממש את `fingerprint` ואת `IdempotencyStore` ב-`mine.py`, לפי הטיוטה של IETF:
- אותו מפתח עם אותו גוף, אחרי שהבקשה הראשונה הסתיימה: מחזירים את התשובה השמורה.
- אותו מפתח עם אותו גוף, כשהראשונה עוד רצה: 409.
- אותו מפתח עם גוף אחר: 422.

כשהבדיקות עוברות, הרץ את השירות על הקוד שלך ושלח את אותה בקשה פעמיים. בפעם השנייה צריכה להופיע הכותרת `Idempotent-Replayed: true`, וב-`/__admin/stats` של השרת המדומה מונה הבקשות לא אמור לעלות. ענה: למה השירות **לא** שומר תשובה של 502, אלא שוכח את המפתח?

```bash
python -m pytest -q labs/26-llm-serving/tests/test_ex6_idempotency.py
python labs/26-llm-serving/serve.py --mine idem
curl -i -X POST http://127.0.0.1:8000/v1/answer -H 'Authorization: Bearer dev-key-alice' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: order-42' -d '{"question": "Where is the Haifa office?"}'
# הרץ את אותה פקודה שוב, ואז שוב עם question אחר
```

**7. חוזה השגיאות.** הרץ את הסיור, שמפעיל כל סוג שגיאה ומדפיס אותה כמו שהלקוח רואה אותה: בלי מפתח, גוף לא תקין, נתיב לא קיים, שיטה לא נכונה, מפתח idempotency עם גוף אחר, הספק עמוס (529), הספק דוחה את הבקשה (400), ושגיאה באמצע סטרים. הסקריפט מדליק את התקלות בשרת המדומה דרך `/__admin/config`, ומכבה אותן בסוף. ענה: על איזה שדה לקוח צריך לעשות `switch`? אילו שגיאות שווה לנסות שוב, ואחרי כמה זמן? ולמה השגיאה האחרונה מגיעה כאירוע `error` ולא כ-status?

```bash
python labs/26-llm-serving/errors_tour.py
```

**8. בקשה חיה אחת מול Claude Haiku 5.5.** הרץ את השירות מול המודל האמיתי, ושלח בקשה אחת בסטרימינג. השווה את ה-TTFT מצד הלקוח ל-TTFT שהשירות מדד מול Anthropic, ואת ה-TTFT ל-1.8 השניות של השרת המדומה. אחר כך הסתכל בשורת הלוג של הבקשה בטרמינל של השירות: האם יש בה כל מה שצריך כדי לחקור תלונה של משתמש, בלי המפתח ובלי תוכן השאלה? עלות: בקשה של כ-1,000 טוקני קלט וכ-200 טוקני פלט עולה בערך $0.0002.

```bash
python -m servekit --model anthropic:claude-haiku-5-5        # טרמינל 2. קורא את ANTHROPIC_API_KEY מ-.env
python labs/26-llm-serving/client.py "How many vacation days do I get in my first year?"
```

## כללים

- כל התרגילים חוץ מ-8 רצים מול השרת המדומה, ועולים 0.
- את קוד הייחוס ב-`servekit/ratelimit.py`, `servekit/gate.py` ו-`servekit/idempotency.py` אל תקרא לפני שהבדיקות שלך עוברות.
- המפתחות `dev-key-*` ו-`load-*` הם מפתחות פיתוח בלבד. בפרודקשן המפתחות מגיעים ממאגר סודות (שיעור 27), ונשמרים כ-hash.

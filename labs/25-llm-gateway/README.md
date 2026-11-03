# מעבדה 25: LLM Gateway and AI Governance

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל. כל התרגילים חוץ מתרגיל 8 חינמיים: הם רצים מול שרתי mockllm מקומיים. תרגיל 7 דורש Docker. תרגיל 8 עולה פחות מעשירית סנט.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/25-llm-gateway/requirements.txt   # fastapi, uvicorn
python -m pytest -q tests/test_gatewaykit.py           # בדיקות הסביבה של gatewaykit (כ-30 שניות)
python -m pytest -q labs/25-llm-gateway/tests          # התרגילים שלך: בהתחלה הכל נכשל, וזה תקין
python labs/25-llm-gateway/setup_keys.py               # יוצר את המפתחות הווירטואליים של המעבדה
```

הסקריפט `setup_keys.py` כותב שני קבצים לתיקייה `labs/25-llm-gateway/state/`, שנמצאת ב-`.gitignore`:

- `keys.yaml`: מה שה-gateway קורא. לכל מפתח יש רשומה עם ה-SHA-256 שלו, אף פעם לא המפתח עצמו.
- `demo_keys.env`: המפתחות הגולמיים, כדי שהסקריפטים של המעבדה יוכלו להשתמש בהם. בחברה אמיתית הקובץ הזה לא היה קיים: כל צוות מקבל את המפתח שלו פעם אחת, לתוך ה-secret store שלו.

ארבעת המפתחות מייצגים ארבע אפליקציות של Acme:

- **support-bot** (צוות support): רק `haiku`, תקציב $2 ל-30 יום, אזהרה ב-$1.50, עד 120 בקשות בדקה, רמת סיווג מינימלית internal.
- **hr-assistant** (צוות hr): `haiku` ו-`sonnet`, תקציב $5, רמת סיווג מינימלית **confidential**.
- **eng-copilot** (צוות engineering): `haiku`, `sonnet`, `gpt` ו-`haiku-flaky`, תקציב $20, אזהרה ב-$15.
- **finance-reports** (צוות finance): רק `sonnet`, תקציב זעיר של $0.002 בשביל תרגיל 2, רמת סיווג מינימלית confidential.

## מה חדש

- **`gatewaykit/`**: gateway קטן שאפשר לקרוא בישיבה אחת. הוא מקבל בקשות בשני פורמטים: OpenAI Chat Completions (`POST /v1/chat/completions`) ו-Anthropic Messages (`POST /v1/messages`). את הבקשה הוא מעביר לספק דרך llmkit. בדרך הוא עובר את כל השלבים, בסדר הזה:
  - מפתח וירטואלי (401).
  - מגבלת קצב לכל מפתח (429 עם `retry-after`).
  - רשימת המודלים שהמפתח מורשה להשתמש בהם (403).
  - סיווג מידע ומדיניות, שקובעים לאילו deployments מותר לשלוח את הבקשה (403 `policy_denied`).
  - תקציב, כולל הערכה של העלות הגרועה ביותר של הבקשה (402).
  - השחרה של מידע אישי (PII) לפי רמת הסיווג.
  - cache (כבוי כברירת מחדל).
  - ניתוב עם fallback ו-circuit breaker לכל deployment (503 כשאין לאן ללכת).
  - חישוב עלות מתוך ה-usage, עדכון התקציב ורשומת audit אחת לכל בקשה.
- **`gatewaykit/gateway.py`**: הצנרת עצמה, בלי שום framework. בראש הקובץ יש רשימה של כל קוד סטטוס ולמה בחרנו בו.
- **`labs/25-llm-gateway/gateway.yaml`**: הקונפיגורציה של המעבדה. היא בנויה בכוונה כמו `config.yaml` של LiteLLM: שם מודל ציבורי, ומתחתיו רשימה של deployments שמנוסים לפי הסדר. כל ה-deployments הם שרתי mockllm מקומיים:
  - פורט 8765 (`mock-a`): ספק ראשי תקין.
  - פורט 8766 (`mock-b`): ספק גיבוי תקין.
  - פורט 8767 (`mock-down`): כל בקשה נכשלת עם 529.
- **`labs/25-llm-gateway/policy.yaml`**: מדיניות הממשל של Acme, כפי שה-gateway אוכף אותה. היא נגזרת משני מסמכים בקורפוס: `sec-data-classification.md` ו-`it-ai-usage-he.md`. בקיצור:
  - public ו-internal: מותר ל-anthropic ול-openai.
  - confidential: רק anthropic, ורק באזורים us או eu.
  - restricted: אסור לכל מודל.
  - ההשחרה: ברמת public כל שלושת הסוגים. ברמות internal ו-confidential רק טלפונים ותעודות זהות, כי מיילים של עובדים הם מידע פנימי, ותהליך בקשות הגישה משיעור 3 צריך את המייל של המבקש.
- **`litellm/`**: קובץ docker compose עם LiteLLM proxy, Postgres ושני שרתי mock, בשביל תרגיל 7.
- **`mine.py`**: ארבעה חלקים שלך, לתרגילים 2 עד 5. אחרי שהבדיקות עוברות, אפשר להריץ את ה-gateway **עם הקוד שלך בפנים**: `run_gateway.py --mine all`.

## התרגילים

**1. להריץ gateway ולקרוא לו בשלוש דרכים.** בטרמינל 1 מריצים את ה-gateway עם שרתי ה-mock. בטרמינל 2 מריצים את הדמו, שקורא לו בפורמט של OpenAI, בפורמט של Anthropic, ודרך llmkit עם `base_url`. אחר כך הוא גורם ל-gateway לסרב בחמש דרכים שונות. אחרי הריצה פתח את `state/audit.jsonl` וענה על שלוש שאלות:
- למה ב-llmkit יוצא `cost_usd = None`, ואיפה העלות האמיתית?
- איזו בקשה סורבה עם 400 ולא "תוקנה" בשקט, ולמה זה חשוב?
- מה רשום ב-audit על הבקשה עם מספר הטלפון, ומה לא רשום שם?

אם יש זמן, הפעל מחדש עם `--cache`, שלח את אותה שאלה פעמיים מ-curl, ובדוק את הכותרת `x-gateway-cache`.

```bash
python labs/25-llm-gateway/run_gateway.py --with-mocks      # טרמינל 1
python labs/25-llm-gateway/call_demo.py                     # טרמינל 2
```

**2. תקציב לכל מפתח (mine.py).** ממש שלושה דברים:
- `spend_from_usage`: עלות מתוך ה-usage שהספק החזיר. מודל בלי מחיר זורק `UnknownPriceError`, ואף פעם לא נחשב חינמי.
- `estimate_max_cost`: הערכה של העלות הגרועה ביותר לפני הקריאה. אורך הפרומפט חלקי 4 בטוקני קלט, ועוד `max_tokens` בטוקני פלט.
- `MyBudgetLedger`: מגבלה קשיחה שמחזירה 402, מגבלה רכה שמוסיפה אזהרה, ואיפוס לפי תקופה.

אחר כך הרץ את ה-gateway עם הקוד שלך, ושרוף את התקציב של finance-reports. בסוף עצור את ה-gateway, הפעל אותו שוב, והרץ `budget_demo.py --info`. ההוצאה שרדה את האתחול, כי ה-gateway בונה אותה מחדש מקובץ ה-audit.

```bash
python -m pytest -q labs/25-llm-gateway/tests/test_ex2_budget.py
python labs/25-llm-gateway/run_gateway.py --with-mocks --mine budget   # טרמינל 1
python labs/25-llm-gateway/budget_demo.py                              # טרמינל 2
```

**3. Fallback עם circuit breaker (mine.py).** ממש שני דברים:
- `MyCircuitBreaker`: שלושה מצבים, closed, open ו-half_open, עם בקשת ניסיון אחת בלבד.
- `route_with_fallback`: שגיאה זמנית עוברת ל-deployment הבא. שגיאה של הבקשה, כמו 400, נזרקת מיד, בלי fallback.

אחר כך הרץ את הדמו. בחלק A הוא שולח בקשות ל-`haiku-flaky`, שהספק הראשי שלו תמיד נופל. בחלק B הוא מפיל את mock-a באמצע תנועה, ואז מרפא אותו. שים לב לבקשה ה-confidential של hr-assistant בחלק B: היא נכשלת עם 503 למרות שיש ספק גיבוי תקין. למה?

```bash
python -m pytest -q labs/25-llm-gateway/tests/test_ex3_router.py
python labs/25-llm-gateway/run_gateway.py --with-mocks --mine router   # טרמינל 1
python labs/25-llm-gateway/fallback_demo.py                            # טרמינל 2 (כ-30 שניות)
```

**4. השחרת PII (mine.py).** ממש שני דברים:
- `israeli_id_valid`: ספרת ביקורת של תעודת זהות.
- `redact`: השחרה של מיילים, טלפונים ישראליים ומספרי זהות. הכללים:
  - placeholders ממוספרים לפי סוג.
  - אותו ערך מקבל תמיד אותו placeholder.
  - סדר עדיפויות בין הסוגים.
  - fingerprint במקום הערך עצמו.
  - מספור משותף לכל ההודעות של בקשה אחת.

הדמו מריץ gateway משלו, ומראה בשורה אחת אחרי השנייה מה האפליקציה שלחה, מה הספק קיבל, מה האפליקציה קיבלה בחזרה, ומה נשאר ב-audit.

```bash
python -m pytest -q labs/25-llm-gateway/tests/test_ex4_redact.py
python labs/25-llm-gateway/redact_demo.py
```

**5. מדיניות ממשל (mine.py ו-policy.yaml).** ממש שתי פונקציות:
- `decide`: האם מותר לשלוח סיווג מסוים ל-deployment מסוים, ואיזה כלל החליט.
- `effective_classification`: הרמה הגבוהה מבין מה שהבקשה ביקשה לבין הרצפה של המפתח. בקשה בלי תווית נחשבת internal.

אחר כך הרץ את `policy_check.py`, שמדפיס את מטריצת ההחלטות ואת שרשראות ה-fallback שנשארות אחרי הסינון. ראה שבשביל confidential, למודל `haiku` אין fallback. הוסף ל-`gateway.yaml` deployment בשם `anthropic-eu` למודל `haiku`: `anthropic:mock-model`, `base_url` של mock-b, ו-`region: eu`. הרץ שוב, ובדוק שהבדיקות עדיין עוברות. עכשיו נסה לשנות את `policy.yaml` כך ש-confidential יורשה גם ל-openai. איזו בדיקה נכשלת, ומה זה אומר על התפקיד של בדיקות למדיניות?

```bash
python -m pytest -q labs/25-llm-gateway/tests/test_ex5_policy.py
python labs/25-llm-gateway/policy_check.py
```

**6. דוח עלויות ותרגיל מפתח שדלף.** החלק הראשון: `traffic.py` מריץ שבוע מדומה של תנועה של Acme דרך gateway, ו-`cost_report.py` מפיק ממנו דוח. בשבוע הזה מוסתרים כמה אירועים. ענה על השאלות בסוף הדוח:
- איזה צוות משלם הכי הרבה?
- איזה מפתח, ובאילו שעות, נראה חריג? מצא שלושה סימנים בלתי תלויים בדוח שמחזקים את זה.
- מה קרה ביום שלישי?
- למה צוות finance לא קיבל אף תשובה?

החלק השני הוא התרגול עצמו, מול ה-gateway שרץ: בטל את המפתח, הוכח שהוא מת, צור מפתח חלופי עם אותן הרשאות, ובדוק מה ה-audit אומר. בסוף כתוב פתק אירוע של חמש שורות: מה זוהה, מתי, מה נעשה, מה עוד צריך לבדוק, ומה משנים כדי שזה לא יחזור.

```bash
python labs/25-llm-gateway/traffic.py
python labs/25-llm-gateway/cost_report.py
python labs/25-llm-gateway/run_gateway.py --with-mocks                     # טרמינל 1
python labs/25-llm-gateway/keys_admin.py revoke eng-copilot                # טרמינל 2
python labs/25-llm-gateway/keys_admin.py try eng-copilot
python labs/25-llm-gateway/keys_admin.py create eng-copilot-2 --team engineering --models haiku,sonnet,gpt --budget 20 --soft 15
python labs/25-llm-gateway/keys_admin.py audit eng-copilot
```

**7. אותם תרחישים על LiteLLM proxy (Docker).** בתרגיל הזה מריצים את המוצר האמיתי, עם Postgres. בלי מסד נתונים, ל-LiteLLM אין מפתחות וירטואליים ואין אכיפת תקציב. ה-compose מריץ ארבעה שירותים:
- `litellm`: הגרסה נעוצה ל-`v1.106.6`. אם התגית לא נמשכת, בחר את הגרסה החדשה ביותר מתוך release notes ורשום איזו בחרת.
- `db`: Postgres 16.
- `mock-ok` ו-`mock-down`: ה-mockllm של הריפו, בתוך image של Python.

הסקריפט `scenarios.py` מריץ את אותם שישה תרחישים על שני ה-gateways, ושומר מה כל אחד עשה. הוא לא בודק נכונות. הוא רושם: קודי סטטוס, סוגי שגיאה, כותרות, הוצאה וזמן. ענה על השאלות:
- באיזה קוד LiteLLM מסרב כשתקציב של מפתח נגמר? התיעוד מראה כמה תשובות שונות: הודעת auth error, 422 לתקציב של צוות, ואפשרות להגדיר 429 עם `budget_exceeded_status_code`.
- כמה בקשות עברו לפני הסירוב, אצל כל אחד מהם? מה ההבדל, ולמה?
- האם ה-fallback עבד גם כשה-מפתח לא כולל את `haiku-backup` ברשימת המודלים שלו? נסה.
- כמה זמן מוסיף כל gateway?

```bash
cd labs/25-llm-gateway/litellm
./make_env.sh                       # יוצר .env עם מפתחות אקראיים (לא מודפסים)
docker compose up -d
docker compose logs -f litellm      # חכה ל-"Uvicorn running"; ב-mock-ok תראה את הנתיבים שהגיעו
cd -
python labs/25-llm-gateway/scenarios.py --target litellm
python labs/25-llm-gateway/run_gateway.py --with-mocks                      # טרמינל אחר
python labs/25-llm-gateway/scenarios.py --target gatewaykit
python labs/25-llm-gateway/scenarios.py --compare
# ממשק הניהול: http://127.0.0.1:4000/ui (התחברות עם LITELLM_MASTER_KEY מתוך litellm/.env)
docker compose -f labs/25-llm-gateway/litellm/compose.yaml down          # בסוף. הוסף -v כדי למחוק גם את המסד
```

אם ב-log של mock-ok מופיע `unknown path`, סימן ש-LiteLLM בונה את ה-URL של Anthropic אחרת ממה שהנחנו. במקרה כזה שנה את `api_base` ב-`litellm/config.yaml` ורשום מה גילית.

**8. Claude אמיתי, ישירות ודרך ה-gateway.** הסקריפט מריץ חמש קריאות ישירות ל-Haiku 5.5 עם llmkit, וחמש קריאות דרך gatewaykit עם `gateway.live.yaml`, ומשווה את ה-latency. אחר כך הוא שולח בקשה אחת עם טלפון ומספר זהות: פעם עם השבת הערכים בתשובה, ופעם בלי. העלות הכוללת פחות מעשירית סנט. ה-gateway דורש בעלייה גם `OPENAI_API_KEY`, כי הוא ספק הגיבוי. כתוב פסקה: מתי היית מסתפק ב-llmkit לבד, ומתי היית שם gateway לפניו?

```bash
python labs/25-llm-gateway/live_compare.py
```

## מה gatewaykit לא עושה (בכוונה)

- **אין סטרימינג, כלים, תמונות או פרמטרים מעבר לטקסט.** כל פרמטר לא מוכר נדחה עם 400, ולא נזרק בשקט.
- **המצב נשמר בזיכרון של תהליך אחד:** התקציבים, ה-breakers, מגבלת הקצב וה-cache. ההוצאה נבנית מחדש מה-audit באתחול, אבל שני מופעים של ה-gateway לא יודעים זה על זה. LiteLLM משתמש ב-Postgres וב-Redis בדיוק בשביל זה.
- **ההשחרה מבוססת regex.** היא לא תזהה שם של אדם או כתובת. Presidio, Bedrock Guardrails או AI Sanitizer של Kong משתמשים במודלים לזיהוי, וגם הם הסתברותיים.
- **אין SSO, ממשק ניהול או התראות.** כל אלה קיימים במוצרים, וחלקם בתשלום.

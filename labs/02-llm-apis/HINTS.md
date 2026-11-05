# רמזים לשיעור 2

**איך להשתמש בקובץ הזה.** קודם נסה לבד, רק לפי ה-docstring ב-`mine.py` והבדיקות בתיקייה `tests/`. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, וחזור לנסות. אם עדיין לא הולך, קרא את **רמז 2**, ונסה שוב. **רמז 3** מתאר את האלגוריתם המלא במילים; השאר אותו למקרה שבאמת אין דרך אחרת, ואחריו כתוב את הקוד בעצמך. כל רמז נמצא תחת כותרת משלו, כך שאפשר לעצור אחרי כל אחד.

המימושים של הקורס נמצאים ב-`llmkit/errors.py`, `llmkit/retry.py` ו-`llmkit/providers/openai.py`. כדאי להשוות אליהם רק אחרי שהבדיקות שלך עוברות.

בדיקה: `python -m pytest -q labs/02-llm-apis/tests`

## classify_error

### רמז 1: כיוון

השאלה היא אחת: אם שולחים **בדיוק את אותה בקשה** שוב, האם יש סיכוי שהתשובה תשתנה? שגיאה שנובעת מהבקשה עצמה (בקשה שבורה, מפתח שגוי, אין הרשאה, בקשה גדולה מדי) תחזור שוב ושוב. שגיאה שנובעת ממצב זמני אצל הספק (עומס, הגבלת קצב, תקלת שרת, timeout, ניתוק) עשויה לעבור. המלכודת: יש שגיאות **בלי** `status`, כי הן הגיעו בתוך stream אחרי HTTP 200 או בלי תשובת HTTP בכלל, ואז צריך להחליט לפי `err.kind`.

### רמז 2: מבנה

החזק שתי קבוצות קבועות (`set`): קבוצה של קודי HTTP שכדאי לנסות שוב, וקבוצה של ערכי `kind` זמניים. אחר כך שתי בדיקות: אם יש `status` והוא בקבוצת הקודים, מנסים שוב. אם אין `status` וה-`kind` בקבוצת הסוגים הזמניים, מנסים שוב. בכל מקרה אחר לא מנסים שוב. כשמנסים שוב, מעבירים הלאה את `err.retry_after` כמו שהוא.

### רמז 3: האלגוריתם המלא

1. קודי HTTP שכדאי לנסות שוב: `408` (request timeout), `409` (conflict, OpenAI משתמשת בו לקונפליקטים זמניים), `429` (rate limit), `500`, `502`, `503`, `504`, ו-`529` (ה-"overloaded" של Anthropic). כל קוד 4xx אחר, למשל `400`, `401`, `403`, `404`, `413`, `422`, הוא שגיאה של הבקשה ולא מנסים שוב.
2. ערכי `kind` זמניים, למקרה ש-`status` הוא `None`: `"overloaded_error"`, `"rate_limit_error"`, `"api_error"`, `"server_error"`, `"timeout"`, `"network"`, ובנוסף `"stream_truncated"` ו-`"malformed_response"`.
3. אם `err.status` אינו `None` והוא בקבוצה של סעיף 1: החזר `RetryDecision(True, err.retry_after)`.
4. אם `err.status` הוא `None` ו-`err.kind` בקבוצה של סעיף 2: החזר `RetryDecision(True, err.retry_after)`.
5. אחרת: `RetryDecision(False)`. שים לב שמקרה כמו `status=None, kind="invalid_request_error"` (שגיאת בקשה שהגיעה בתוך stream) נופל לכאן.

המימוש של הקורס: `llmkit/errors.py` (הפונקציה `classify_error` והקבועים `RETRYABLE_STATUS`, `RETRYABLE_KINDS`).

## backoff_delay

### רמז 1: כיוון

יש כאן שלושה רעיונות שמתחברים: **exponential backoff** (ההמתנה מוכפלת בכל ניסיון), **cap** (תקרה שההמתנה לא עוברת), ו-**full jitter** (במקום להמתין בדיוק את הזמן המחושב, מגרילים ערך בין 0 לבינו, כדי שלקוחות רבים לא יחזרו כולם באותו רגע). המלכודת: להשתמש ב-`random.uniform` במקום ב-`rng.uniform`, ואז הבדיקות לא ניתנות לשחזור.

### רמז 2: מבנה

שלושה שלבים בשורות ספורות: חשב את הגבול העליון האקספוננציאלי עבור `attempt` וחתוך אותו ב-`cap`. הגרל ערך אחיד בין 0 לגבול הזה בעזרת `rng`. ולבסוף, אם התקבל `retry_after`, ודא שהתוצאה לא קטנה ממנו. אין צורך בלולאה.

### רמז 3: האלגוריתם המלא

1. הגבול העליון: `min(cap, base * 2 ** attempt)`. עם `base=0.5` זה 0.5, 1, 2, 4, 8, ... עד ה-`cap`.
2. `delay = rng.uniform(0, upper)`. זה ה-full jitter: התפלגות אחידה, ולכן הממוצע הוא חצי מהגבול (למשל עבור `attempt=3`, `base=0.5`: `uniform(0, 4)` עם ממוצע 2, וזה מה שהבדיקה מודדת).
3. אם `retry_after is not None`: `delay = max(delay, retry_after)`. השרת ביקש לחכות לפחות כך, וזו רצפה.
4. החזר `delay`.

שים לב: הרצפה של `retry_after` יכולה להיות גבוהה מ-`cap`, וזה בסדר; השרת קובע. הבדיקה של ה-cap לא מעבירה `retry_after`.

המימוש של הקורס: `llmkit/retry.py`. הנוסחה מופיעה גם בראש הקובץ, עם קישור למאמר של AWS על backoff ו-jitter.

## openai_event_to_item

### רמז 1: כיוון

ב-Responses API של OpenAI, כל אירוע ב-stream נושא שם (`event_type`) וגוף JSON. רק מעט מהם מעניינים: האירוע שמביא חתיכת טקסט, האירועים שמסמנים סוף (רגיל או קטוע), והאירועים שמדווחים על כשל. כל השאר הם "ניהול חשבונות" ואפשר להתעלם מהם. הפונקציות `raw_stop_from()` ו-`usage_from()` שכבר מיובאות בראש הקובץ עושות את רוב העבודה של אירוע הסיום.

### רמז 2: מבנה

שרשרת של בדיקות לפי `event_type`: אירוע ה-delta מחזיר `TextDelta`. שני אירועי הסיום מחזירים `StreamEnd`, שבנוי מאובייקט ה-response שבתוך `data`. שני אירועי הכשל זורקים `LLMError`. כל דבר אחר מחזיר `None`. השתמש ב-`.get()` עם ברירות מחדל, כי שדות יכולים לחסור.

### רמז 3: האלגוריתם המלא

1. `"response.output_text.delta"`: החזר `TextDelta(data.get("delta", ""))`.
2. `"response.completed"` או `"response.incomplete"`: קח `resp = data.get("response", {})` והחזר `StreamEnd(raw_stop_from(resp), usage_from(resp.get("usage")), resp.get("id"))`. הפונקציה `raw_stop_from` מחזירה `"completed"`, או עבור response חלקי את הסיבה מתוך `incomplete_details`, למשל `"max_output_tokens"`.
3. `"response.failed"`: השגיאה נמצאת ב-`data["response"]["error"]` (היזהר, כל אחת מהרמות יכולה להיות חסרה או `None`). זרוק `LLMError(message, provider=provider, kind=...)`, כשההודעה היא `error["message"]` (ברירת מחדל `"response failed"`) וה-`kind` הוא `error["code"]` (ברירת מחדל `"server_error"`).
4. `"error"`: ההודעה נמצאת ישירות ב-`data["message"]` (ברירת מחדל `"stream error"`). זרוק `LLMError` עם `provider=provider` ו-`kind` מתוך `data["code"]`, אחרת `data["type"]`, אחרת `"server_error"`.
5. כל אירוע אחר (`response.created`, `response.in_progress`, `response.output_item.added`, `response.content_part.added`, `response.output_text.done`, ...): החזר `None`.

המימוש של הקורס: `llmkit/providers/openai.py`, הפונקציה `event_to_item`.

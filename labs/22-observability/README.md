# מעבדה 22: AI Observability and Tracing

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

הרעיון של המעבדה: מערכת LLM שאין לה traces היא קופסה שחורה. כשמשתמש כותב "התשובה שגויה", בלי trace אפשר רק לנחש: האם השליפה החזירה מסמך ישן? האם המודל נכשל ומישהו החזיר תשובת גיבוי? האם זה בכלל היה איטי ולא שגוי? במעבדה הזו תוסיף spans של OpenTelemetry לפי ה-GenAI semantic conventions לשירות RAG קטן, תסתכל עליהם (בדפדפן, ב-Phoenix או ב-Langfuse), תכתוב בעצמך את הקוד שמחשב מהם latency ועלות, מסיר מהם מידע אישי ומחשב burn rate של SLO, ותמצא את סיבת השורש של תשובות שגויות **מתוך ה-traces בלבד**.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r labs/22-observability/requirements.txt     # opentelemetry-sdk ו-OTLP exporter, גרסה 1.45
python -m pytest -q                                          # בדיקות הסביבה, כולל tests/test_obskit.py
python -m pytest -q labs/22-observability/tests              # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

אופציונלי, לתרגיל 2: Docker, בשביל Arize Phoenix (או Langfuse).

## מה חדש

- **`obskit/`**: חבילה חדשה בריפו. היא מוסיפה tracing ל-llmkit ול-ragkit **מבחוץ**, בלי לשנות אותם:
  - `semconv.py`: כל שמות ה-attributes במקום אחד. ה-GenAI conventions עדיין בסטטוס Development ושמות משתנים (למשל `gen_ai.usage.cache_creation.input_tokens` שונה ל-`gen_ai.usage.cache_write.input_tokens`), ולכן כשהתקן זז משנים קובץ אחד.
  - `instrument.py`: `InstrumentedLLM` עוטף כל אובייקט עם `complete()` ומייצר span בשם `chat <model>` עם מודל, טוקנים, cache, עלות, TTFT, סיבת עצירה, ניסיונות, ו-event לכל retry.
  - `tracing.py`: `setup_tracing()` (exporters, sampling, redaction, content capture), ו-helpers ל-spans מסוג agent, retrieval ו-tool, וגם `InstrumentedRetriever`.
  - `exporters.py`: `JsonlSpanExporter`, exporter מקומי ששומר span לכל שורה, וקוראים שעובדים בלי ה-SDK.
  - `redact.py`, `analyze.py`, `slo.py`: קוד הייחוס לתרגילים 4, 3 ו-6. אל תקרא לפני שהבדיקות שלך עוברות.
  - `replay.py`: בונה מחדש בקשה למודל מתוך span ושולח אותה שוב. `viewer.py`: מציג trace כ-waterfall בקובץ HTML אחד.
- **`acme_app.py`**: "שירות התשובות של Acme", מערכת RAG קטנה שה-traces שלה הם חומר העבודה במעבדה. פירוט מלא בהמשך.
- **`fixtures/forensic.jsonl`**: 12 traces מוקלטים (48 spans) מבוקר אחד של השירות, עם תקלות שהוכנסו בכוונה. `fixtures/feedback.jsonl`: משוב של משתמשים על חלק מהתשובות. איך הם נוצרו: `make_forensic.py` (לא צריך להריץ).
- **`collector/`**: קובץ compose עם Phoenix ו-OpenTelemetry Collector, וקונפיגורציה של Collector עם tail sampling ו-redaction.
- **`mine.py`**: הקוד שלך לתרגילים 3, 4 ו-6.
- **הסקריפטים**: `trace_demo.py`, `trace_view.py`, `trace_stats.py`, `forensic_check.py`, `make_day.py`, `slo_report.py`, `replay_trace.py`. כל סקריפט שמשתמש בפונקציה שלך מ-`mine.py` עובר לגרסת הייחוס כל עוד היא TODO, ומודיע על זה. עם `--reference` הוא משתמש רק בגרסת הייחוס.

## השירות שה-traces מתארים (acme_app.py)

בכל בקשה השירות עובר את השלבים האלה, וכל שלב הוא span:

- **`invoke_workflow acme_answer`**: ה-span הראשי (root) של הבקשה. עליו נרשמים השאלה, התשובה, סוג התשובה (`obskit.answer.kind`: `llm`, `cache`, `fallback_model` או `canned`), גרסת הפרומפט, והאם התשובה עברה בדיקת עיגון (`obskit.grounded`).
- **`cache.lookup`**: מטמון תשובות לפי טקסט השאלה (`obskit.cache.hit`). רק תשובה מעוגנת נכנסת למטמון.
- **`retrieval acme-kb`**: חיפוש BM25 (מ-ragkit) על 9 מסמכי מדיניות של Acme, 3 התוצאות הטובות. נרשמים: המסמכים והציונים (`gen_ai.retrieval.documents`, `obskit.retrieval.results`), גרסת האינדקס (`obskit.retrieval.index_version`) ו-ה-replica שענה (`obskit.retrieval.replica`). יש שני replicas: `kb-1` נבנה ב-2026-10-30, ו-`kb-2` הוא snapshot מ-2025-05-30.
- **`execute_tool lookup_employee`**: רק בשאלות "מי אחראי על...". מחפש את בעל המסמך ב-`data/acme/corpus/structured/employees.csv`.
- **`chat <model>`**: הקריאה למודל דרך llmkit. ה-system prompt (גרסה `v3`, כ-4,900 תווים) כולל 8 כללים, ביניהם: לענות רק מהמקורות, לצטט כל משפט כ-[n], להעדיף את המקור עם ה-effective_date המאוחר, ואם אין תשובה לענות בדיוק "I could not find this in the Acme documents.". הפרומפט מסומן ל-prompt caching.
- **כשהקריאה נכשלת אחרי כל ה-retries** (שלושה ניסיונות): על rate limit או overload השירות עובר ל-**מודל גיבוי** (`mock-small`), עם פרומפט קצר **בלי המקורות** (`fallback@v1`). על timeout הוא מחזיר את התשובה הקבועה "I could not find this in the Acme documents.". בשני המקרים נרשם event בשם `fallback` על ה-root.

המסמכים במאגר: `hr-vacation-2024`, `hr-vacation-2026`, `hr-sick-leave`, `hr-remote-work-2026`, `it-password-policy-2024`, `it-password-mfa-2026`, `sup-refund-policy`, `hr-expenses`, `it-laptop-policy` (כולם ב-`data/acme/corpus/docs/`). העובדות שתצטרך לתרגיל 5:

- **חופשה**: לפי מדיניות 2024, אפשר להעביר עד 3 ימים לשנה הבאה, והם פגים ב-28 בפברואר. לפי מדיניות 2026 (בתוקף מ-1 בינואר 2026, מחליפה את 2024), עד 5 ימים, והם פגים ב-31 במרץ.
- **מחלה**: אישור רפואי נדרש להיעדרות של 3 ימים רצופים או יותר (ולכל היעדרות אחרי שנוצלו 6 ימי הצהרה עצמית בשנה).
- **סיסמאות**: מדיניות 2026: לפחות 14 תווים, ואין חובת החלפה כל 90 יום.

**על המודל במצב offline:** במעבדה, "המודל" הוא mockllm שמחזיר תשובה שמחושבת מתוך המקורות בפרומפט (ragkit `ExtractiveAnswerer`: המשפטים עם הכי הרבה מילים משותפות לשאלה). הוא דטרמיניסטי ולא חושב, ולכן תשובות שלו לפעמים מגושמות. ה-traces עצמם אמיתיים: llmkit, HTTP, retries, timeouts, ושדות ה-cache של ה-mock שמחקים את ה-API של Anthropic.

## התרגילים

**1. ה-spans הראשונים.** הרץ את השירות על ארבע שאלות. קרא את הפלט של `--console` עבור span אחד מכל סוג. ענה:
- אילו attributes על ה-span `chat mock-model` באים מה-GenAI conventions (מתחילים ב-`gen_ai.`), ואילו הם של obskit? למה, לדעתך, עלות היא לא חלק מהתקן?
- הרץ שוב עם `--no-content`. מה נעלם מה-spans? מה כבר לא תוכל לעשות עם trace כזה (רמז: תרגיל 7)?
- למה לשאלה הרביעית אין span של `chat` בכלל?

```bash
python labs/22-observability/trace_demo.py --console
python labs/22-observability/trace_demo.py --no-content
```

**2. לראות traces.** קודם, הדרך שלא צריכה כלום: צור waterfall ב-HTML ופתח בדפדפן. אחר כך, אם יש לך Docker, הרם את Phoenix ושלח אליו את אותם spans ב-OTLP. ב-Phoenix, בדוק שמספרי הטוקנים, המודל וההודעות מוצגים בתצוגת ה-LLM (Phoenix ממיר `gen_ai.*` לפורמט שלו מגרסה 15.10). נסה גם דרך ה-Collector (פורט 4318), שמפעיל tail sampling: הרץ את הדמו כמה פעמים ובדוק אילו traces הגיעו ל-Phoenix ואילו לא, ולמה.

```bash
python labs/22-observability/trace_demo.py
python labs/22-observability/trace_view.py results/traces.jsonl
docker run -d --name phoenix -p 6006:6006 -p 4317:4317 arizephoenix/phoenix:latest      # UI: http://localhost:6006
python labs/22-observability/trace_demo.py --otlp http://localhost:6006/v1/traces
docker compose -f labs/22-observability/collector/compose.yaml up -d                     # Phoenix + Collector
python labs/22-observability/trace_demo.py --otlp http://localhost:4318/v1/traces
```

Langfuse (v4) במקום Phoenix: `git clone https://github.com/langfuse/langfuse.git && cd langfuse && docker compose up` (מומלץ לשנות את הסודות שמסומנים `CHANGEME`). ה-UI בפורט 3000. צור פרויקט ומפתחות, ואז שלח ל-`http://localhost:3000/api/public/otel/v1/traces` עם `--otlp-header "Authorization=Basic <base64 של public_key:secret_key>"`. שים לב: Langfuse v4 מריץ כמה שירותים (Postgres, ClickHouse, Redis, MinIO), והתיעוד שלו ממליץ על 16GB זיכרון לשרת.

**3. מה ה-traces אומרים במספרים.** ממש את `percentile` ואת `summarize` ב-`mine.py`: p50 ו-p95 לכל סוג span, עלות לכל trace, ו-N ה-traces האיטיים. הרץ על ה-traces של הבוקר וענה: מה ה-p95 של בקשה, ואיזה סוג span אחראי כמעט לכל הזמן? מה ההבדל בין p50 ל-p95, ומה הוא אומר? כמה מה-input הגיע מה-prompt cache?

```bash
python -m pytest -q labs/22-observability/tests/test_ex3_stats.py
python labs/22-observability/trace_stats.py labs/22-observability/fixtures/forensic.jsonl
```

**4. מידע אישי לא יוצא מהתהליך.** ממש את `israeli_id_valid`, `redact_text` ו-`redact_attributes`: מיילים, טלפונים ישראליים ומספרי תעודת זהות (9 ספרות עם ספרת ביקורת). הדמו עם `--pii` שואל שאלות שמכילות ת"ז, טלפון ומייל, ומעביר כל span דרך `RedactingSpanProcessor` עם ה-`redact_text` שלך לפני ה-exporter. ודא ב-`results/traces.jsonl` שאין שם אף ערך גולמי. ענה: למה בודקים ספרת ביקורת, ומה המחיר של זה? למה ה-redaction ב-Collector (`collector/otel-collector.yaml`) לא מספיק לבד?

```bash
python -m pytest -q labs/22-observability/tests/test_ex4_redact.py
python labs/22-observability/trace_demo.py --pii
grep -c "123456782" labs/22-observability/results/traces.jsonl     # צריך להיות 0
```

**5. פורנזיקה: ארבעה משובים שליליים.** בבוקר של 2026-10-29 השירות ענה על 12 שאלות (`fixtures/forensic.jsonl`). ארבעה משתמשים נתנו משוב שלילי (`fixtures/feedback.jsonl`):
- "That's wrong. Since January it's 5 days, and they expire at the end of March."
- "Not true, the policy says 3 or more consecutive days. Where did this come from?"
- "Right answer, but much slower than usual."
- "It's in the password policy! Why can't it find it?"

לכל אחד מהם, מצא את סיבת השורש **מתוך ה-traces בלבד**, ותכתוב אילו attributes או events הוכיחו אותה. היעזר ב-waterfall (עם המשוב), בסטטיסטיקות מתרגיל 3, וב-traces התקינים להשוואה: מה שונה ב-trace הרע מה-trace הטוב? שים לב שיש בסט גם traces איטיים בלי משוב, ושלא כל משוב שלילי הוא בעיית איכות. בדוק כל תשובה עם `forensic_check.py`, שמציג את רשימת הסיבות האפשריות. הנתונים על המסמכים והשירות שאתה צריך מופיעים למעלה, בסעיף "השירות שה-traces מתארים".

```bash
python labs/22-observability/trace_view.py labs/22-observability/fixtures/forensic.jsonl --feedback labs/22-observability/fixtures/feedback.jsonl
python labs/22-observability/trace_stats.py labs/22-observability/fixtures/forensic.jsonl
python labs/22-observability/forensic_check.py
python labs/22-observability/forensic_check.py <trace_id prefix> <cause>
```

**6. SLO ו-burn rate.** ממש את `is_good`, `burn_rate` ו-`alerts_at`. `make_day.py` מייצר יום סינתטי של כ-3,500 בקשות (2026-10-28, UTC), שבו נפרס פרומפט v4 ב-02:00 (והוחזר ל-v3 ב-09:30), והספק היה בעומס בין 11:20 ל-11:50. ה-SLOs: זמינות 99.5%, 95% מהבקשות המוצלחות מתחת ל-8 שניות, ו-97% מהתשובות שנבדקו מעוגנות. כללי ההתראה: page על 14.4x בחלון 1h/5m, page על 6x בחלון 6h/30m, ו-ticket על 3x בחלון 24h/2h. ענה:
- אילו התראות נורו, מתי, וכמה זמן אחרי תחילת כל תקלה?
- תקלת העומס שרפה גם את תקציב ה-latency. למה היא לא הוציאה התראת latency?
- יש התראה אחת בלילה שהיא כנראה רעש. מה גרם לה, ואיך היית מונע אותה?

```bash
python -m pytest -q labs/22-observability/tests/test_ex6_slo.py
python labs/22-observability/make_day.py
python labs/22-observability/slo_report.py --hourly
```

**7. Replay: אותה בקשה בדיוק.** `replay_trace.py` בונה מחדש את הבקשה למודל מתוך ה-span (system prompt, הודעות, max_tokens), ושולח אותה דרך llmkit לשרת מדומה תקין. הרץ על שלושה מה-traces של תרגיל 5 (את ה-prefix שלהם מצאת שם). ענה לכל אחד: האם ה-replay מחזיר אותה תשובה? מה זה מוכיח על סיבת השורש (בעיה בקלט, או בתשתית)? אחר כך הרץ את ה-trace של תשובת החופשה עם `--fresh-retrieval`: מה השתנה במקורות, ומה עדיין לא תקין בתשובה? (רמז: הסתכל על המקור [1].)

```bash
python labs/22-observability/replay_trace.py <trace_id prefix>
python labs/22-observability/replay_trace.py <trace_id prefix> --fresh-retrieval
```

**8. (רשות, חי) traces של Claude אמיתי.** הרץ את הדמו מול Claude Haiku 5.5, עם Phoenix פתוח. השווה ל-traces של ה-mock: TTFT, טוקני cache read בקריאה השנייה, עלות, ואיכות התשובה לשאלה על בעל מדיניות המחלה (שם יש tool call). אחר כך הרץ replay של אחד ה-traces עם `--live` שלוש פעמים: האם התשובה זהה בכל פעם?

```bash
python labs/22-observability/trace_demo.py --live --otlp http://localhost:6006/v1/traces
python labs/22-observability/replay_trace.py <trace_id prefix> --live
```

## כללים

- תרגילים 1 עד 7 לא עולים כסף: הכול רץ מול mockllm. תרגיל 8 הוא ארבע עד שש קריאות קצרות ל-Haiku 5.5, הרבה פחות מסנט.
- `results/traces.jsonl` נכתב מחדש בכל הרצה של הדמו. ה-fixtures לא משתנים.
- אל תשלח traces עם content capture פעיל לשירות חיצוני בלי redaction. זה בדיוק מה שתרגיל 4 עוסק בו.
- את קוד הייחוס ב-`obskit/` אל תקרא לפני שהבדיקות שלך עוברות.

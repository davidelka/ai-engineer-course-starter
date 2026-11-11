# פרויקט סיום F3: סוכן משרות, גרסת פרודקשן

כל הפקודות רצות מתוך `projects/f3-job-agent/`, עם ה-venv של הריפו פעיל, אלא אם כתוב אחרת.

## על הפרויקט

**מה המערכת עושה.** סוכן משרות שעובד בשביל מחפש עבודה אחד. שלוש פעמים ביום (08:30, 15:00 ו-21:00, שעון ישראל) הוא קורא את ההודעות החדשות בקבוצות משרות בוואטסאפ ובלוח משרות ב-Airtable, מחלץ מכל פוסט את המשרות שבו בעזרת מודל שפה (כותרת, חברה, מיקום, מצב עבודה, בכירות, שנות ניסיון, קטגוריה, איך מגישים), מסיר כפילויות, נותן לכל משרה ציון לפי הקריטריונים של מחפש העבודה עם הסבר לכל נקודה, ושולח סיכום בעברית לקבוצת וואטסאפ פרטית בשם "משרות". למשרות המתאימות ביותר הוא מכין גם טיוטת מייל (בלי לשלוח אותה).

**מי מחפש העבודה בדוגמה.** הקריטריונים ב-`data/preferences.yaml` שייכים לדמות בדויה: מהנדס עם חמש שנות ניסיון באוטומציה ו-backend, שגר בדרום, ומחפש משרות backend, אוטומציה (עדיף מול חומרה), embedded או Rust. כל הקבוצות, החברות, האנשים והקישורים בנתונים מומצאים. אם תרצה שהסוכן יעבוד בשבילך, באבן דרך 1 תיצור עותק עם הקריטריונים שלך.

**למה זה פרויקט טוב לסיום.** כל מי שחיפש עבודה בישראל מכיר את הבעיה: עשרות הודעות ביום, חצי מהן כפולות, חלקן לא רלוונטיות, ומדי פעם מישהו מנסה "לדבר" עם הכלים האוטומטיים שקוראים את הקבוצה. זו בעיה אמיתית וקטנה מספיק כדי לבנות אותה עד הסוף, ועדיין יש בה כמעט כל מה שמערכת AI בפרודקשן צריכה: קלט לא מהימן, פלט מובנה, החלטות שצריך להסביר, ריצות מתוזמנות שאסור שירוצו פעמיים, מדידה, ניטור ופריסה. בסוף יש לך מערכת שאפשר להראות בראיון עבודה ולהסביר כל החלטה בה.

**מה כבר בנוי, ומה אתה בונה.** החלקים ה"רגילים" מוכנים: קריאת המקורות (קבצי ייצוא של וואטסאפ, Airtable), ה-state ב-SQLite, הסיכום, המשלוח, הדוחות, ה-API הניהולי וקבצי הפריסה. אתה כותב ב-`mine.py` את אחת עשרה הפונקציות שהן לב הנושאים של הקורס:
- **כפילויות בשתי רמות** (`find_repost`, `job_fingerprint`, `near_duplicate`): פוסט שפורסם שוב נתפס לפני שמשלמים למודל, ומשרה שהגיעה משני מקורות מופיעה פעם אחת.
- **הגנה מפני קלט עוין** (`screen_post`, `spotlight`, `validate_job`): סינון ניסיונות הזרקה, סימון הטקסט הלא מהימן בפרומפט, ובדיקה של כל שדה שהמודל החזיר מול הפוסט המקורי.
- **חילוץ מובנה** (`extract_post`): קריאה אחת למודל עם schema, תיקון אוטומטי, מטמון לפרומפט, וכישלון "סגור".
- **ה-matcher** (`score_job`): כללים דטרמיניסטיים מתוך קובץ YAML, עם הסבר לכל נקודה.
- **תזמון אידמפוטנטי** (`due_slot`): איזה slot להריץ עכשיו, כך שניסיון חוזר או טריגר כפול לא ישלחו סיכום פעמיים.
- **ה-eval** (`align`, `relevance`): איזו משרה חזויה מתאימה לאיזו משרה מתויגת, ו-precision ו-recall של מה שמגיע לסיכום.

בדרך משתמשים כמעט בכל מה שהקורס בנה: `llmkit` ו-`llmkit.structured` (שיעורים 2-3), `guardkit` (24), `obskit` (22), `evalkit` (23), דפוסי `servekit` (26) ו-Terraform של שיעור 27.

## מה עולה כסף, ומה לא

- **כמעט הכול חינם.** ה-extractor ברירת המחדל הוא `heuristic` (regex ומילות מפתח), והבדיקות משתמשות ב-`GoldOracleLLM`, מודל מזויף שעונה מתוך התוויות. אין צורך במפתח עד אבן דרך 5, וגם שם ההרצה האמיתית אופציונלית.
- **אבני דרך 5, 8 ו-9: Claude Haiku 5.5.** הרצה מלאה של ה-eval (70 פוסטים) עולה בערך **3 סנט** לפי המחירים ב-`llmkit/pricing.py` (0.10$ למיליון טוקני קלט, 0.50$ לפלט). התקרה שקבענו לפרויקט: פחות מ-0.20$ להרצה מלאה.
- **אבן דרך 10, AWS (אופציונלי):** משימת ECS מתוזמנת רצה שלוש פעמים ביום כדקה-שתיים. לפי `python -m jobagent cost` זה בערך **0.09$ לחודש** של AWS ועוד כ-0.90$ של טוקנים (25 פוסטים חדשים לריצה). אין load balancer ואין שירות שרץ כל הזמן, ולכן אין חיוב שעתי כשהמערכת לא רצה. את ה-API key שומרים ב-SSM Parameter Store (פרמטר standard הוא בחינם, Secrets Manager עולה 0.40$ לסוד לחודש).

## הכנה

```bash
cd ~/ai-engineer-course-starter && source .venv/bin/activate
uv pip install -r projects/f3-job-agent/requirements.txt
python -m pytest -q                              # בדיקות הסביבה, כולל tests/test_f3_job_agent.py
cd projects/f3-job-agent
python -m pytest -q tests                        # אבני הדרך שלך: בהתחלה רובן נכשלות, וזה תקין
python -m jobagent demo                          # עוצר ומראה איזו אבן דרך חסרה; אחרי אבן דרך 7 זו הדגמה מלאה, בחינם
```

## מה יש בתיקייה

- **`jobagent/`**: המערכת עצמה. החלקים שאתה כותב נקראים מ-`mine.py` דרך `jobagent/hooks.py`.
  - `models.py`: שלוש שכבות מידע. `RawPost` (מה שהמקור נתן, טקסט לא מהימן), `PostExtraction` ו-`JobPosting` (מה שהמודל קרא מהפוסט, הסכמה של `llmkit.structured`), ו-`Job` (מה שהקוד הוסיף: אזור, טביעת אצבע, ממצאי בטיחות, ציון, דרגה, קורות חיים).
  - `sources.py`: מקורות כ-ports. `WhatsAppExportSource` (ייצוא צ'אט כ-.txt, או JSON מה-bridge), `AirtableAPISource` (REST API עם pagination ו-429), `AirtableCSVSource` (CSV מ-shared view), ו-fixtures. **אין כאן קוד שמתחבר לוואטסאפ**: מי שמריץ bridge מקומי לוואטסאפ מייצא ממנו קבצים, והמערכת קוראת קבצים.
  - `dedup.py`: כפילויות בשתי רמות. פוסט שפורסם שוב (shingles ו-Jaccard, לפני כל קריאה למודל), ומשרה שהגיעה משני מקורות (טביעת אצבע ו-near-duplicate).
  - `extract.py`: `LLMExtractor` (Haiku 5.5 דרך `complete_structured`, עם spotlighting והקלטה), `ReplayExtractor`, `HeuristicExtractor` (קו הבסיס החינמי), ו-`GoldOracleLLM` (מודל מזויף לבדיקות).
  - `safety.py`: סינון הזרקות (`guardkit.HeuristicDetector` ועוד שני סימנים מבניים), spotlighting, ולידציה של הפלט, ו-redaction של מידע אישי.
  - `prefs.py` ו-`match.py`: הקריטריונים של מחפש העבודה כ-YAML, וכללים דטרמיניסטיים עם הסבר לכל כלל.
  - `digest.py` ו-`delivery.py`: הסיכום בעברית, ו-ports למשלוח (קובץ, קונסול, וואטסאפ דרך ה-bridge) ולטיוטות (קבצי `.eml`, או Gmail drafts בלבד, בלי שליחה).
  - `store.py`: SQLite עם runs, posts, cache של חילוצים ו-jobs. וגם `S3StateSync` (העלאה עם If-Match) ו-`S3Folder` (inbox ו-outbox) לפריסה בענן.
  - `schedule.py`: השעות במקום אחד, ותרגום שלהן ל-APScheduler, ל-systemd ול-EventBridge Scheduler.
  - `pipeline.py`: ריצה אחת של slot, עם span לכל שלב. `report.py`: דוח HTML לכל ריצה. `evaluate.py`: ה-eval. `api.py`: ה-API הניהולי. `config.py`: הגדרות מהסביבה.
- **`data/`**: `preferences.yaml` (הקריטריונים של מחפש העבודה), `posts.jsonl` (סט ה-eval), `make_evalset.py` (המקור שממנו הוא נבנה), `whatsapp/` ו-`airtable/` (אותם פוסטים כקבצי מקור להדגמה), ו-`recorded/` (הקלטות של מודל אמיתי, נוצרות באבן דרך 9).
- **`mine.py`**: אחת עשרה הפונקציות שאתה כותב, באבני דרך 3, 4, 5, 6, 7 ו-9. כל docstring הוא חוזה: מה הפונקציה מקבלת, מה היא מחזירה ומה היא מבטיחה. כל פקודה של `python -m jobagent` משתמשת בפונקציות שלך, ופקודה שצריכה פונקציה שעוד לא כתבת עוצרת ואומרת באיזו אבן דרך היא. **`HINTS.md`**: שלושה רמזים מדורגים לכל פונקציה. מימושי הייחוס נמצאים רק ב-branch בשם `solutions`, להשוואה אחרי שהטסטים שלך עוברים.
- **`tests/`**: בדיקות לאבני הדרך, ושער הרגרסיה (`test_m9_regression_gate.py`).
- **`deploy/`**: `Dockerfile` ו-`Dockerfile.dockerignore`, `pyproject.toml` ו-`uv.lock`, `systemd/` (timer למחשב Linux), ו-`terraform/` (ECS scheduled task עם EventBridge Scheduler). **`compose.yaml`** בתיקייה הראשית.

## סט ה-eval בקצרה

70 פוסטים סינתטיים, 69 משרות עם תוויות זהב. כל החברות, האנשים, הטלפונים והקישורים מומצאים (דומיינים `.example`). הפוסטים מחקים את הסגנון של הקבוצות: עברית ואנגלית, אימוג'ים, שורות שבורות.

- 8 פוסטים שאינם משרות: 7 רגילים (שאלות, "מחפשת עבודה", פרסומת לקורס, תודה) ואחד שכולו ניסיון הזרקה.
- 6 פוסטים עם ניסיון הזרקה: 4 "רועשים" (ignore previous instructions, עברית, סמני post מזויפים) ו-2 "מנומסים" ("Note to AI tools...", "Note to automated screeners...").
- 5 פוסטים עם כמה משרות, 2 פרסומים חוזרים כמעט זהים, ו-5 משרות שהופיעו שוב בניסוח אחר או ממקור אחר (Airtable מול וואטסאפ).
- לכל משרה: השדות של `JobPosting`, ו-`tier`, הדרגה שאדם החליט לפי הקריטריונים שבדוגמה (לא לפי ה-matcher), ו-`group`, קבוצת כפילויות.
- מוסכמות התיוג (וגם ההוראות למודל): seniority רק ממילה מפורשת, years_required הוא המספר המינימלי, work_mode רק אם נכתב, ו-company יכול להיות רשימה של איותים מקובלים.

## אבני הדרך

**1. סיור: מה בנוי ומה תבנה (חינם).** הרץ את ה-demo ואת הטסטים, וראה איפה הם עוצרים: זה מסלול העבודה שלך. אחר כך קרא, בסדר הזה, את `jobagent/models.py` (שלוש שכבות המידע), את `jobagent/pipeline.py` (ריצה אחת של slot, שלב אחרי שלב: fetch, פוסט חוזר, screen, חילוץ, ולידציה, כפילויות, ציון, משלוח), ואת `data/preferences.yaml`. אם אתה רוצה שהסוכן יעבוד בשבילך, צור עותק עם הקריטריונים שלך (קטגוריות, אזור, שנות ניסיון ושמות קבצי קורות החיים) והפנה אליו עם `PREFS_PATH` ב-`.env`. אל תשנה את `data/preferences.yaml` עצמו: הטסטים וסט ה-eval מתויגים לפיו, ושינוי שלו ישבור אותם.

```bash
python -m jobagent demo                                # stops: "milestone 3: mine.find_repost is still a TODO"
python -m pytest -q tests                              # most fail with NotImplementedError: expected
cp data/preferences.yaml ~/my-preferences.yaml         # optional: your own criteria; then PREFS_PATH=~/my-preferences.yaml in .env
```

ענה: עבור כל אחת מאחת עשרה הפונקציות ב-`mine.py`, באיזה שלב של `pipeline.py` היא נקראת? איזו מהן נקראת לפני הקריאה למודל, ולמה זה חשוב לעלות?

**2. המקורות (חינם, קוד מוכן).** קרא את `sources.py`. הרץ את שלושת המקורות על קבצי ההדגמה. אם יש לך לוח משרות ב-Airtable, אפשר לחבר אותו (חינם): אם ה-"New Jobs" הוא shared view של base שאתה לא חבר בו, ה-REST API לא יראה אותו, אז הורד CSV מה-view והשתמש ב-`AIRTABLE_CSV`. בשביל וואטסאפ אמיתי צריך bridge מקומי (למשל שרת MCP מעל whatsmeow): כתוב סקריפט קטן מחוץ לפרויקט שמייצא ממנו את ההודעות החדשות לקובץ JSON בפורמט שבראש `sources.py`, ושים אותו ב-`WHATSAPP_DIR`.

```bash
python -c "from jobagent.sources import *; print(len(WhatsAppExportSource('data/whatsapp').fetch()))"
python -c "from jobagent.sources import *; print(AirtableFixtureSource('data/airtable/new_jobs.json').fetch()[0].text)"
# live, after putting AIRTABLE_BASE_ID / AIRTABLE_TABLE / AIRTABLE_TOKEN in .env:
python -c "from jobagent.config import Settings; s=Settings.from_env(); print([len(x.fetch()) for x in s.sources()])"
```

בדיקת קבלה: 64 פוסטי וואטסאפ ו-6 רשומות Airtable מההדגמה. ענה: למה ה-id של הודעה מקובץ .txt בנוי מהשעה ומספר סידורי, ומה יקרה אם תייצא את אותו צ'אט פעמיים?

**3. כפילויות (קוד: `find_repost`, `job_fingerprint`, `near_duplicate`).** שתי רמות. `find_repost` תופסת פוסט שפורסם שוב כמעט מילה במילה (בקבוצה אחרת, או למחרת עם אימוג'י אחר) לפי דמיון של רצפי תווים, **לפני** שמשלמים למודל על חילוץ. `job_fingerprint` ו-`near_duplicate` תופסות משרה שהגיעה פעמיים בניסוח אחר או ממקור אחר, **אחרי** החילוץ. שלושה מקרים שקל לפספס, וכולם קרו באמת בזמן בניית הפרויקט: "Junior Rust Developer" ו-"Rust Engineer" באותה חברה הם לא אותה משרה; שתי משרות "Backend Engineer" בתל אביב בלי שם חברה הן לא אותה משרה; ו-"Senior Backend Engineer" מ-Airtable ו-"Senior Backend Developer" מוואטסאפ כן.

```bash
python -m pytest -q tests/test_m3_repost.py tests/test_m3_dedup.py
```

ענה: למה `find_repost` משווה רצפי תווים, ו-`near_duplicate` משווה שדות מחולצים? מה היה קורה אם היינו משתמשים רק באחת מהן?

**4. פוסטים הם קלט לא מהימן (קוד: `screen_post`, `spotlight`, `validate_job`).** שלוש שכבות הגנה מהשיעור על אבטחה. `screen_post` מסמנת פוסט שמנסה לדבר עם המודל (ה-detector של guardkit ועוד שני סימנים מבניים של הפורמט שלנו), ופוסט מסומן לא יכול לקבל דרגה "התאמה" ולא מקבל טיוטה. `spotlight` עוטפת את הפוסט בסימונים עם nonce אקראי ומחליפה רווחים בתו סימון, כדי שהמודל יידע איפה הנתונים נגמרים. `validate_job` בודקת כל שדה שהמודל החזיר מול הפוסט המקורי: כתובת הגשה שלא מופיעה בפוסט נמחקת, וכך גם קישור בתוך שם החברה.

```bash
python -m pytest -q tests/test_m4_screens.py tests/test_m4_validate.py
```

ענה: למה nonce חדש לכל פוסט, ולא סימון קבוע? איזו מהשכבות היית משאיר אם היה מותר לך רק אחת, ולמה?

**5. חילוץ מובנה (קוד: `extract_post`).** קרא את `SYSTEM_PROMPT` ב-`extract.py` ואת `PostExtraction` ב-`models.py`, וממש קריאה אחת ל-`complete_structured` (שיעור 3): system prompt שנשמר במטמון, הפוסט אחרי spotlighting, תיקון אחד אם ה-JSON לא תקין, ואם גם זה נכשל, אפס משרות ושגיאה, אף פעם לא חצי משרה. הטסטים משתמשים ב-`GoldOracleLLM`, מודל מזויף שעונה מתוך התוויות. אחר כך הרץ את ה-eval עם "מודל נאיבי" שמציית לכל הזרקה (`obey_injections=True`), וראה מה אבן דרך 4 עוצרת: ה-screen עוצר את ארבע ההזרקות הרועשות (הדרגה יורדת ל"אולי" ואין טיוטה), אבל שתי ההזרקות המנומסות עוברות, כי אין בהן אף מילה שה-detector מכיר.

```bash
python -m pytest -q tests/test_m5_extract.py
python -c "
from jobagent.evaluate import *; from jobagent.extract import *
r = evaluate_extractor(LLMExtractor(GoldOracleLLM(load_posts(), obey_injections=True)))
print(r.injection)"
# optional, paid (less than a cent): the real model on 10 posts
python -m jobagent eval --extractor llm --limit 10 --no-digest --misses
```

ענה: למה כישלון "סגור" (אפס משרות) עדיף כאן על ניסיון להציל שדות? למה הבדיקה "הכתובת מופיעה בפוסט" לא עוצרת את p062, שבו כתובת התוקף כתובה בפוסט, ואיזו שכבה כן עוצרת אותו? מה היית מוסיף כדי לתפוס את p039 ו-p056?

**6. ה-matcher (קוד: `score_job`).** ממש את `score_job`: ציון של 0 עד 100 מקטגוריה, מיקום וניסיון, דרגה (התאמה, אולי, אחר), קורות החיים המתאימים, ושורת הסבר בעברית לכל רכיב. כל מספר מגיע מ-`data/preferences.yaml`. ההחלטה כאן מכוונת: המודל קורא את הפוסט, אבל **הקוד** מחליט מה מתאים, כי החלטה שצריך להסביר ולבדוק עדיף שתהיה כלל.

```bash
python -m pytest -q tests/test_m6_score.py
```

ענה: אילו שורות הסבר מסומנות "[מודל]" ואילו "[כלל]", ולמה ההבחנה חשובה למי שקורא את הסיכום?

**7. תזמון, והריצה המלאה (קוד: `due_slot`).** ממש את `due_slot`. עכשיו כל החלקים קיימים, וה-demo רץ מתחילתו ועד סופו: הוא מריץ את 1 בנובמבר 2026 slot אחרי slot, על state חדש, מקבצי המקור ב-`data/`, עם ה-extractor החינמי (`heuristic`). קרא את הסיכום של 08:30, פתח את הדוח של אחת הריצות בדפדפן, ואת מפל ה-spans שלידו. אחר כך הרץ ריצה "אמיתית" ל-slot שמגיע עכשיו, פעמיים (השנייה צריכה לדלג), ואם תרצה, התקן את ה-timer של systemd כדי שהסוכן ירוץ לבד. משלוח אמיתי לוואטסאפ: `WhatsAppGroupDelivery` מקבל `send_fn` שקורא לכלי `send_message` של ה-bridge, ומסרב לכל יעד חוץ מהקבוצה "משרות".

```bash
python -m pytest -q tests/test_m7_schedule.py
python -m jobagent demo
python -m jobagent demo -v | less                      # all three digests
xdg-open results/demo/runs/2026-11-01T0830.html
xdg-open results/demo/runs/2026-11-01T0830.traces.html
ls results/demo/drafts/                                # .eml drafts for jobs with an email address
python -m jobagent schedule --show
python -m jobagent run --slot auto && python -m jobagent run --slot auto
cp deploy/systemd/job-agent.* ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now job-agent.timer
```

בדיקת קבלה: שלוש ריצות, הריצה הרביעית (21:00 שוב) "skipped, already done", ובסיכום של 15:00 אין אף משרה שכבר הופיעה ב-08:30. ענה: כמה פוסטים חדשים היו בכל ריצה, וכמה מהם הפכו למשרות חדשות? למה המספרים שונים? למה הסדר הוא "שולחים, ורק אחר כך מסמנים כנשלח", ומה המחיר שלו? מה עושה `Persistent=true` אם המחשב היה כבוי ב-08:30?

**8. ניטור: traces, עלות ודוח.** כל ריצה כותבת `results/traces.jsonl` ודוח HTML. הרץ את ה-demo עם המודל האמיתי (בערך סנט אחד; זה מריץ את `extract_post` שלך), וקרא את ה-spans של פוסט אחד: screen, קריאת ה-LLM עם טוקנים ועלות, ובסוף deliver. בדוק שאין מספר טלפון באף span.

```bash
EXTRACTOR=llm python -m jobagent demo
python -m obskit.viewer results/demo/traces.jsonl -o results/demo/all.html
grep -c "050-555" results/demo/traces.jsonl            # should print 0: PII is redacted before export
```

**9. Eval ושער רגרסיה (קוד: `align`, `relevance`; ההרצה האמיתית בתשלום, כ-3 סנט).** ממש את שתי הפונקציות שה-eval בנוי עליהן: `align` מחליטה איזו משרה חזויה היא איזו משרה מתויגת (בלי זה אי אפשר לבדוק שדות בפוסט עם כמה משרות), ו-`relevance` מחשבת precision ו-recall של מה שמגיע לסיכום. אחר כך הרץ את ה-eval עם ה-heuristic, ואז עם המודל והקלט אותו. ההקלטה (`data/recorded/claude-haiku-5-5.jsonl`) מפעילה את הבדיקה השנייה בשער, כך שכל שינוי בפרומפט או בקוד נמדד מול המודל האמיתי בלי לשלם שוב. בסוף שנה את הקריטריונים (למשל `thresholds.match` ל-85, או מרכז מהמשרד ל-20 נקודות) והרץ שוב: ה-precision וה-recall של "relevance (gold facts)" זזים, והאינטראקציה בחלק "מגרש משחקים" במרכז הלמידה מראה את אותו trade-off.

```bash
python -m pytest -q tests/test_m9_metrics.py
python -m jobagent eval --json results/eval_heuristic.json
python -m jobagent eval --extractor llm --record --json results/eval_llm.json
python -m pytest -q tests/test_m9_regression_gate.py
```

ענה: באילו שדות המודל טוב יותר, ובאילו ה-heuristic לא נופל ממנו? מה הפער בין "relevance (gold facts)" ל-"relevance (predicted)", ומה הוא אומר לך על איפה כדאי להשקיע? ברווח הסמך של 69 משרות, האם הפרש של 3 נקודות בין שני extractors הוא אמיתי?

**10. API, Docker ו-AWS (קוד מוכן).** הרם את ה-API הניהולי, ואז את כל המערכת ב-compose. השלב האחרון אופציונלי: Terraform ל-ECS scheduled task. קרא קודם את ההערות ב-`deploy/terraform/versions.tf` וב-`storage.tf`: ה-bridge של וואטסאפ נשאר במחשב המקומי (הוא מחזיק את ה-session), ולכן בענן הקבצים עוברים דרך S3. ה-bridge דוחף ייצוא ל-`inbox/`, המשימה כותבת סיכום ל-`outbox/`, ומשהו במחשב המקומי שולח אותו לקבוצה.

```bash
ADMIN_TOKEN=dev python -m jobagent serve &
curl -s localhost:8080/runs | python -m json.tool | head -20
curl -s "localhost:8080/jobs?tier=match&limit=3" | python -m json.tool | head -30
docker compose up --build -d && docker compose ps && docker compose logs agent | tail
docker compose run --rm agent run --slot auto --force
cd deploy/terraform && cp terraform.tfvars.example terraform.tfvars
terraform init && terraform fmt -check && terraform validate && terraform plan -out=tfplan
```

בדיקת קבלה: `/healthz` מחזיר 200, `PUT /preferences` בלי token מחזיר 403, ו-`terraform plan` מציג את ה-schedules עם `Asia/Jerusalem`. אם החלטת לעשות `apply`: הכנס את המפתח ל-SSM עם ה-CLI (הפקודה ב-`storage.tf`), דחוף image, הרץ `terraform output -raw run_now` כדי לבדוק ריצה אחת, קרא את הלוגים, ו-`terraform destroy` בסוף.

## מה לבדוק אצלך, כי כאן לא היה אפשר

- הרצה אמיתית של Haiku 5.5 (אבני דרך 5, 8, 9): העלות בפועל ומספרי הדיוק. המספרים שבדוח הם של ה-heuristic ושל המודל המזויף.
- `docker build` ו-`docker compose up` (בסביבת הבנייה לא היה registry זמין). הקבצים עברו את הבודק הסטטי של שיעור 27.
- `terraform validate` ו-`plan` מול חשבון AWS. הקבצים נקראו עם python-hcl2 ועברו את בדיקות ה-IAM של deploykit.

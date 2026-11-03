# פרויקט סיום F3: סוכן משרות, גרסת פרודקשן

כל הפקודות רצות מתוך `projects/f3-job-agent/`, עם ה-venv של הריפו פעיל, אלא אם כתוב אחרת.

הסוכן שבנית לעצמך עובד: הוא קורא כל בוקר את קבוצות המשרות בוואטסאפ ואת לוח Airtable, מסנן לפי הקריטריונים שלך, ושולח סיכום לקבוצה "משרות" ב-08:30, 15:00 ו-21:00. הפרויקט הזה הופך אותו למערכת שאפשר להראות בראיון עבודה: כל שלב נמדד, כל החלטה מוסברת, קלט זדוני לא שובר אותה, ריצה כפולה לא שולחת פעמיים, ויש לה eval, ניטור, API ניהולי ופריסה. בדרך משתמשים כמעט בכל מה שהקורס בנה: `llmkit` ו-`llmkit.structured` (שיעורים 2-3), `guardkit` (24), `obskit` (22), `evalkit` (23), דפוסי `servekit` (26) ו-Terraform של שיעור 27.

## מה עולה כסף, ומה לא

- **כמעט הכול חינם.** ה-extractor ברירת המחדל הוא `heuristic` (regex ומילות מפתח), והבדיקות משתמשות ב-`GoldOracleLLM`, מודל מזויף שעונה מתוך התוויות. אין צורך במפתח עד אבן דרך 4.
- **אבן דרך 4 ו-9: Claude Haiku 5.5.** הרצה מלאה של ה-eval (70 פוסטים) עולה בערך **3 סנט** לפי המחירים ב-`llmkit/pricing.py` (0.10$ למיליון טוקני קלט, 0.50$ לפלט). התקרה שקבענו לפרויקט: פחות מ-0.20$ להרצה מלאה.
- **אבן דרך 10, AWS (אופציונלי):** משימת ECS מתוזמנת רצה שלוש פעמים ביום כדקה-שתיים. לפי `python -m jobagent cost` זה בערך **0.09$ לחודש** של AWS ועוד כ-0.90$ של טוקנים (25 פוסטים חדשים לריצה). אין load balancer ואין שירות שרץ כל הזמן, ולכן אין חיוב שעתי כשהמערכת לא רצה. את ה-API key שומרים ב-SSM Parameter Store (פרמטר standard הוא בחינם, Secrets Manager עולה 0.40$ לסוד לחודש).

## הכנה

```bash
cd ~/ai-engineer-course-starter && source .venv/bin/activate
uv pip install -r projects/f3-job-agent/requirements.txt
python -m pytest -q                              # בדיקות הסביבה, כולל tests/test_f3_job_agent.py
cd projects/f3-job-agent
python -m pytest -q tests                        # אבני הדרך שלך: בהתחלה רובן נכשלות, וזה תקין
python -m jobagent demo                          # הדגמה מלאה, בחינם
```

## מה יש בתיקייה

- **`jobagent/`**: המערכת עצמה (קוד הייחוס).
  - `models.py`: שלוש שכבות מידע. `RawPost` (מה שהמקור נתן, טקסט לא מהימן), `PostExtraction` ו-`JobPosting` (מה שהמודל קרא מהפוסט, הסכמה של `llmkit.structured`), ו-`Job` (מה שהקוד הוסיף: אזור, טביעת אצבע, ממצאי בטיחות, ציון, דרגה, קורות חיים).
  - `sources.py`: מקורות כ-ports. `WhatsAppExportSource` (ייצוא צ'אט כ-.txt, או JSON מה-bridge), `AirtableAPISource` (REST API עם pagination ו-429), `AirtableCSVSource` (CSV מ-shared view), ו-fixtures. **אין כאן קוד שמתחבר לוואטסאפ**: ה-bridge שכבר רץ אצלך מייצא קבצים, והמערכת קוראת קבצים.
  - `dedup.py`: כפילויות בשתי רמות. פוסט שפורסם שוב (shingles ו-Jaccard, לפני כל קריאה למודל), ומשרה שהגיעה משני מקורות (טביעת אצבע ו-near-duplicate).
  - `extract.py`: `LLMExtractor` (Haiku 5.5 דרך `complete_structured`, עם spotlighting והקלטה), `ReplayExtractor`, `HeuristicExtractor` (קו הבסיס החינמי), ו-`GoldOracleLLM` (מודל מזויף לבדיקות).
  - `safety.py`: סינון הזרקות (`guardkit.HeuristicDetector` ועוד שני סימנים מבניים), spotlighting, ולידציה של הפלט, ו-redaction של מידע אישי.
  - `prefs.py` ו-`match.py`: הקריטריונים שלך כ-YAML, וכללים דטרמיניסטיים עם הסבר לכל כלל.
  - `digest.py` ו-`delivery.py`: הסיכום בעברית, ו-ports למשלוח (קובץ, קונסול, וואטסאפ דרך ה-bridge) ולטיוטות (קבצי `.eml`, או Gmail drafts בלבד, בלי שליחה).
  - `store.py`: SQLite עם runs, posts, cache של חילוצים ו-jobs. וגם `S3StateSync` (העלאה עם If-Match) ו-`S3Folder` (inbox ו-outbox) לפריסה בענן.
  - `schedule.py`: השעות במקום אחד, ותרגום שלהן ל-APScheduler, ל-systemd ול-EventBridge Scheduler.
  - `pipeline.py`: ריצה אחת של slot, עם span לכל שלב. `report.py`: דוח HTML לכל ריצה. `evaluate.py`: ה-eval. `api.py`: ה-API הניהולי. `config.py`: הגדרות מהסביבה.
- **`data/`**: `preferences.yaml` (הקריטריונים שלך), `posts.jsonl` (סט ה-eval), `make_evalset.py` (המקור שממנו הוא נבנה), `whatsapp/` ו-`airtable/` (אותם פוסטים כקבצי מקור להדגמה), ו-`recorded/` (הקלטות של מודל אמיתי, נוצרות באבן דרך 9).
- **`mine.py`**: ארבע אבני דרך שאתה כותב (3, 5, 6, 7). כל פקודה של `python -m jobagent` משתמשת בפונקציה שלך ברגע שהיא מפסיקה לזרוק `NotImplementedError`, ובגרסת הייחוס עד אז (ומודיעה על זה). `--reference` מכריח את גרסאות הייחוס.
- **`tests/`**: בדיקות לאבני הדרך, ושער הרגרסיה (`test_m9_regression_gate.py`).
- **`deploy/`**: `Dockerfile` ו-`Dockerfile.dockerignore`, `pyproject.toml` ו-`uv.lock`, `systemd/` (timer למחשב Linux), ו-`terraform/` (ECS scheduled task עם EventBridge Scheduler). **`compose.yaml`** בתיקייה הראשית.

## סט ה-eval בקצרה

70 פוסטים סינתטיים, 69 משרות עם תוויות זהב. כל החברות, האנשים, הטלפונים והקישורים מומצאים (דומיינים `.example`). הפוסטים מחקים את הסגנון של הקבוצות: עברית ואנגלית, אימוג'ים, שורות שבורות.

- 8 פוסטים שאינם משרות: 7 רגילים (שאלות, "מחפשת עבודה", פרסומת לקורס, תודה) ואחד שכולו ניסיון הזרקה.
- 6 פוסטים עם ניסיון הזרקה: 4 "רועשים" (ignore previous instructions, עברית, סמני post מזויפים) ו-2 "מנומסים" ("Note to AI tools...", "Note to automated screeners...").
- 5 פוסטים עם כמה משרות, 2 פרסומים חוזרים כמעט זהים, ו-5 משרות שהופיעו שוב בניסוח אחר או ממקור אחר (Airtable מול וואטסאפ).
- לכל משרה: השדות של `JobPosting`, ו-`tier`, הדרגה שאדם החליט לפי הקריטריונים שלך (לא לפי ה-matcher), ו-`group`, קבוצת כפילויות.
- מוסכמות התיוג (וגם ההוראות למודל): seniority רק ממילה מפורשת, years_required הוא המספר המינימלי, work_mode רק אם נכתב, ו-company יכול להיות רשימה של איותים מקובלים.

## אבני הדרך

**1. הרצה ראשונה: יום שלם במחשב שלך (חינם).** `demo` מריץ את 1 בנובמבר 2026 slot אחרי slot, על state חדש, מקבצי המקור ב-`data/`. קרא את הסיכום של 08:30 שמודפס, פתח את הדוח של אחת הריצות בדפדפן, ואת מפל ה-spans שלידו.

```bash
python -m jobagent demo
python -m jobagent demo -v | less                      # כל שלושת הסיכומים
xdg-open results/demo/runs/2026-11-01T0830.html
xdg-open results/demo/runs/2026-11-01T0830.traces.html
ls results/demo/drafts/                                # טיוטות .eml למשרות עם כתובת מייל
```

בדיקת קבלה: שלוש ריצות, הריצה הרביעית (21:00 שוב) "skipped, already done", ובסיכום של 15:00 אין אף משרה שכבר הופיעה ב-08:30. ענה: כמה פוסטים חדשים היו בכל ריצה, וכמה מהם הפכו למשרות חדשות? למה המספרים שונים?

**2. המקורות.** קרא את `sources.py`. הרץ את שלושת המקורות על קבצי ההדגמה, ואז (אופציונלי, חינם) את ה-Airtable האמיתי שלך. אם ה-"New Jobs" הוא shared view של base שאתה לא חבר בו, ה-REST API לא יראה אותו: הורד CSV מה-view והשתמש ב-`AIRTABLE_CSV`. בשביל וואטסאפ: כתוב סקריפט קטן מחוץ לפרויקט שמייצא מה-bridge את ההודעות החדשות של שלוש הקבוצות לקובץ JSON בפורמט שבראש `sources.py`, ושים אותו ב-`WHATSAPP_DIR`.

```bash
python -c "from jobagent.sources import *; print(len(WhatsAppExportSource('data/whatsapp').fetch()))"
python -c "from jobagent.sources import *; print(AirtableFixtureSource('data/airtable/new_jobs.json').fetch()[0].text)"
# live, after putting AIRTABLE_BASE_ID / AIRTABLE_TABLE / AIRTABLE_TOKEN in .env:
python -c "from jobagent.config import Settings; s=Settings.from_env(); print([len(x.fetch()) for x in s.sources()])"
```

בדיקת קבלה: 64 פוסטי וואטסאפ ו-6 רשומות Airtable מההדגמה. ענה: למה ה-id של הודעה מקובץ .txt בנוי מהשעה ומספר סידורי, ומה יקרה אם תייצא את אותו צ'אט פעמיים?

**3. כפילויות (קוד: `job_fingerprint`, `near_duplicate`).** ממש את שתי הפונקציות ב-`mine.py`. שלושה מקרים שקל לפספס, וכולם קרו באמת בזמן בניית הפרויקט: "Junior Rust Developer" ו-"Rust Engineer" באותה חברה הם לא אותה משרה; שתי משרות "Backend Engineer" בתל אביב בלי שם חברה הן לא אותה משרה; ו-"Senior Backend Engineer" מ-Airtable ו-"Senior Backend Developer" מוואטסאפ כן.

```bash
python -m pytest -q tests/test_m3_dedup.py
python -m jobagent eval --no-digest                    # still the same numbers: your functions are in use
```

**4. חילוץ מובנה עם מודל אמיתי (בתשלום: פחות מסנט).** קרא את `SYSTEM_PROMPT` ב-`extract.py` ואת `PostExtraction` ב-`models.py`. הרץ את Haiku 5.5 על 10 הפוסטים הראשונים, ואז השווה את השגיאות שלו לשגיאות של ה-heuristic על אותם פוסטים.

```bash
python -m jobagent eval --extractor llm --limit 10 --no-digest --misses
python -m jobagent eval --extractor heuristic --limit 10 --no-digest --misses
```

בדיקת קבלה: אין שגיאות `structured_*`, העלות מודפסת ונמוכה מסנט. ענה: באילו שדות המודל טוב יותר, ובאילו ה-heuristic לא נופל ממנו? איזה פוסט עברי היה הכי קשה, ולמה?

**5. בטיחות: ולידציה של הפלט (קוד: `validate_job`).** ממש את `validate_job`. אחר כך הרץ את ה-eval עם "מודל נאיבי" שמציית לכל הזרקה (`GoldOracleLLM(obey_injections=True)`), וראה מה עוצר מה: ה-screen עוצר את ארבע ההזרקות הרועשות (הדרגה יורדת ל"אולי" ואין טיוטה), אבל שתי ההזרקות המנומסות עוברות, כי אין בהן אף מילה שה-regex מכיר.

```bash
python -m pytest -q tests/test_m5_validate.py
python -c "
from jobagent.evaluate import *; from jobagent.extract import *
r = evaluate_extractor(LLMExtractor(GoldOracleLLM(load_posts(), obey_injections=True)))
print(r.injection, r.relevance_predicted['match'])"
```

ענה: למה הבדיקה "הכתובת מופיעה בפוסט" לא עוצרת את p062, שבו כתובת התוקף כתובה בפוסט? איזו שכבה כן עוצרת אותו? מה היית מוסיף כדי לתפוס את p039 ו-p056?

**6. ה-matcher (קוד: `score_job`).** ממש את `score_job`. כל מספר מגיע מ-`data/preferences.yaml`. אחר כך שנה את הקריטריונים (למשל `thresholds.match` ל-85, או מרכז מהמשרד ל-20 נקודות) והרץ שוב את ה-eval: ה-precision וה-recall של "relevance (gold facts)" זזים, והאינטראקציה בחלק "מגרש משחקים" במרכז הלמידה מראה את אותו trade-off.

```bash
python -m pytest -q tests/test_m6_score.py
python -m jobagent eval --no-digest
```

**7. State, תזמון ומשלוח (קוד: `due_slot`).** ממש את `due_slot`. אחר כך הרץ ריצה "אמיתית" ל-slot שמגיע עכשיו, פעמיים: השנייה צריכה לדלג. בסוף התקן את ה-timer של systemd (או הרם את ה-scheduler של APScheduler) כדי שהסוכן ירוץ לבד. חיבור למשלוח אמיתי לוואטסאפ: `WhatsAppGroupDelivery` מקבל `send_fn` שקורא לכלי `send_message` של ה-bridge, ומסרב לכל יעד חוץ מהקבוצה "משרות".

```bash
python -m pytest -q tests/test_m7_schedule.py
python -m jobagent schedule --show
python -m jobagent run --slot auto && python -m jobagent run --slot auto
cp deploy/systemd/job-agent.* ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now job-agent.timer
systemctl --user list-timers job-agent.timer
```

ענה: למה הסדר הוא "שולחים, ורק אחר כך מסמנים כנשלח", ומה המחיר שלו? מה עושה `Persistent=true` אם המחשב היה כבוי ב-08:30?

**8. ניטור: traces, עלות ודוח.** כל ריצה כותבת `results/traces.jsonl` ודוח HTML. הרץ את ה-demo עם המודל האמיתי (בערך סנט אחד), וקרא את ה-spans של פוסט אחד: screen, קריאת ה-LLM עם טוקנים ועלות, ובסוף deliver. בדוק שאין מספר טלפון באף span.

```bash
EXTRACTOR=llm python -m jobagent demo
python -m obskit.viewer results/demo/traces.jsonl -o results/demo/all.html
grep -c "050-555" results/demo/traces.jsonl            # should print 0: PII is redacted before export
```

**9. Eval ושער רגרסיה (בתשלום: כ-3 סנט).** הרץ את ה-eval המלא עם המודל והקלט אותו. ההקלטה (`data/recorded/claude-haiku-5-5.jsonl`) מפעילה את הבדיקה השנייה בשער, כך שכל שינוי בפרומפט או בקוד נמדד מול המודל האמיתי בלי לשלם שוב.

```bash
python -m jobagent eval --extractor llm --record --json results/eval_llm.json
python -m jobagent eval --json results/eval_heuristic.json
python -m pytest -q tests/test_m9_regression_gate.py
```

ענה: מה הפער בין "relevance (gold facts)" ל-"relevance (predicted)", ומה הוא אומר לך על איפה כדאי להשקיע? ברווח הסמך של 69 משרות, האם הפרש של 3 נקודות בין שני extractors הוא אמיתי?

**10. API, Docker ו-AWS.** הרם את ה-API הניהולי, ואז את כל המערכת ב-compose. השלב האחרון אופציונלי: Terraform ל-ECS scheduled task. קרא קודם את ההערות ב-`deploy/terraform/versions.tf` וב-`storage.tf`: ה-bridge של וואטסאפ נשאר אצלך במחשב (הוא מחזיק את ה-session), ולכן בענן הקבצים עוברים דרך S3. ה-bridge דוחף ייצוא ל-`inbox/`, המשימה כותבת סיכום ל-`outbox/`, ומשהו אצלך במחשב שולח אותו לקבוצה.

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

- הרצה אמיתית של Haiku 5.5 (אבני דרך 4, 8, 9): העלות בפועל ומספרי הדיוק. המספרים שבדוח הם של ה-heuristic ושל המודל המזויף.
- `docker build` ו-`docker compose up` (בסביבת הבנייה לא היה registry זמין). הקבצים עברו את הבודק הסטטי של שיעור 27.
- `terraform validate` ו-`plan` מול חשבון AWS. הקבצים נקראו עם python-hcl2 ועברו את בדיקות ה-IAM של deploykit.

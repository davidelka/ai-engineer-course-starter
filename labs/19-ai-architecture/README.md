# מעבדה 19: AI System Architecture

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

הרעיון של המעבדה: **ארכיטקטורה כנתונים**. במקום לצייר קופסאות בכלי ציור, מתארים את המערכת בקובץ YAML אחד: רכיבים, זרימות נתונים, גבולות אמון ותקציב. מאותו קובץ יוצאים ארבעה דברים: בדיקה אוטומטית של כללי ארכיטקטורה, מודל עלות וזמן, דיאגרמה, ובסיס מספרי ל-ADR. זה אותו עיקרון כמו מודל ה-Pydantic בשיעור 3: מקור אמת אחד, וכל השאר נגזר ממנו.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt        # אין חבילות חדשות בשיעור הזה
python -m pytest -q                       # בדיקות הסביבה, כולל tests/test_archkit.py
python -m pytest -q labs/19-ai-architecture/tests   # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

אופציונלי, לייצוא דיאגרמות ל-SVG: Node.js 18 ומעלה (בשביל `npx`).

## מה חדש

- **`archkit/`**: חבילה חדשה בריפו, עם קוד הייחוס של השיעור:
  - `spec.py`: מודל Pydantic של קובץ הארכיטקטורה, וטעינה עם בדיקת הפניות (רכיב בגבול שלא קיים, זרימה לרכיב שלא קיים, מזהה כפול).
  - `rules.py`: חמישה כללי ארכיטקטורה שרצים על הקובץ, כמו linter.
  - `cost.py` ו-`latency.py`: עלות לבקשה ולחודש לפי המחירים ב-`llmkit/pricing.py`, ותקציב p95 עם סימולציה.
  - `mermaid.py`: הקובץ הופך לדיאגרמת Mermaid.
  - `adr.py`: בדיקת מבנה ל-ADR. `critique.py`: מודל שקורא ADR מול מחוון ומחזיר ביקורת מובנית.
  - `examples/`: פתרונות ייחוס לתרגילים 4 ו-7. אל תקרא לפני שניסית.
- **`specs/company_brain.arch.yaml`**: הארכיטקטורה של Company Brain (שלבים 2 ו-3), עם כמה בעיות שהוכנסו בכוונה.
- **`specs/access_options.arch.yaml`**: שתי החלופות לזרימת בקשות הגישה, לתרגיל ה-ADR, רק עם תקציב.
- **`cases/ticket_triage/`**: מסמך דרישות לפרויקט חדש (מיון פניות תמיכה) וקובץ התחלה.
- **`adr/`**: תבנית, מחוון, ו-ADR לדוגמה מלא (`0000-example-response-cache.md`).
- **`mine.py`**: הקוד שלך לתרגילים 1, 2, 3 ו-5.
- **הסקריפטים**: `cost_model.py`, `arch_check.py`, `diagram.py`, `adr_check.py`, `critique_adr.py`. כל אחד מהם משתמש בפונקציות שלך מ-`mine.py`. כל עוד פונקציה היא TODO, הסקריפט משתמש בגרסת הייחוס ומודיע על זה. עם `--reference` הוא משתמש רק בגרסאות הייחוס.

## מבנה קובץ הארכיטקטורה, בקיצור

- `boundaries`: גבולות אמון. לכל גבול יש `trust`: `untrusted` (המשתמש, האינטרנט), `trusted` (השירותים שלנו), `third_party` (ספקים חיצוניים: ספק המודל, SaaS).
- `components`: הרכיבים. לכל אחד `id`, `name`, `kind`, `boundary`. ל-`kind: llm` יש גם `model`, `timeout_s`, `retry: {max_attempts}`, `fallback` ו-`traced`. רכיב צד שלישי שאושר למידע אישי מקבל `pii_allowed: true`. כלי שמשנה משהו בעולם מקבל `side_effects: write`.
- `flows`: זרימות נתונים, בכיוון שבו הנתונים זזים: `from`, `to`, `data`, ו-`classification` אחד מתוך `public`, `internal`, `confidential`, `pii`.
- `budget`: מסלולי בקשה (`paths`). לכל מסלול: נפח יומי, שיעורי פגיעה במטמון, רשימת קריאות למודל עם הערכת טוקנים, ושלבי latency עם p95 (ושלבים עם אותו `group` רצים במקביל).

## התרגילים

**1. מודל עלות.** ממש את `request_cost` ו-`monthly_cost` ב-`mine.py`. אחר כך הרץ את מודל העלות על Company Brain וענה: כמה עולה שאלה אחת, כמה עולה חודש, ומה המסלול היקר? מה קורה לעלות אם כל הקריאות רצות על Haiku 5.5, ומה קורה בלי שום מטמון? האם המערכת בתוך המגבלה של 800$?

```bash
python -m pytest -q labs/19-ai-architecture/tests/test_ex1_cost.py
python labs/19-ai-architecture/cost_model.py labs/19-ai-architecture/specs/company_brain.arch.yaml
python labs/19-ai-architecture/cost_model.py labs/19-ai-architecture/specs/company_brain.arch.yaml --scale 2
```

**2. תקציב latency.** ממש את `latency_budget`. בפלט של `cost_model.py` תראה שני מספרים לכל מסלול: סכום ה-p95 של השלבים, וה-p95 של סימולציה. הסבר במשפט אחד למה הסכום גבוה מהסימולציה, ומתי בכל זאת נכון לתכנן לפי הסכום. שים לב: הסכום בדרך כלל פסימי, אבל הוא לא חסם מתמטי, כי אחוזונים לא מתחברים כמו ממוצעים. כשלשלב יש זנב כבד (מהיר רוב הזמן ואיטי מאוד לפעמים), ה-p95 של הזמן הכולל יכול לעבור את סכום ה-p95. הסימולציה מניחה שהשלבים בלתי תלויים.

```bash
python -m pytest -q labs/19-ai-architecture/tests/test_ex2_latency.py
```

**3. כללי ארכיטקטורה.** קרא את `rule_external_input_guarded` ב-`mine.py` (דוגמה פתורה), וממש את `rule_llm_resilience` ו-`rule_pii_classified`.

```bash
python -m pytest -q labs/19-ai-architecture/tests/test_ex3_rules.py
```

**4. לתקן את Company Brain.** הרץ את הבודק על הקובץ. תקבל 8 שגיאות ואזהרה אחת. הן נובעות מ-4 סיבות שורש בלבד: מצא אותן. תקן את ה-YAML עד שאין שגיאות, ואז הרץ שוב את מודל העלות והחזר את המערכת אל מתחת ל-800$ בלי לפגוע באיכות במקום שהיא חשובה (רמז: ניתוב בין מודלים, `calls_per_request`).

```bash
python labs/19-ai-architecture/arch_check.py labs/19-ai-architecture/specs/company_brain.arch.yaml
```

**5. דיאגרמה מהקובץ.** ממש את `to_mermaid`, ואז צור את הדיאגרמה ופתח את ה-HTML בדפדפן (הוא טוען Mermaid 12.2.0 מ-CDN, אז צריך אינטרנט). אפשר גם להדביק את קובץ ה-`.mmd` ב-mermaid.live, או לייצא SVG עם Mermaid CLI.

```bash
python -m pytest -q labs/19-ai-architecture/tests/test_ex5_mermaid.py
python labs/19-ai-architecture/diagram.py labs/19-ai-architecture/specs/company_brain.arch.yaml
npx -y @mermaid-js/mermaid-cli@12.0.0 -i labs/19-ai-architecture/results/company-brain.mmd -o labs/19-ai-architecture/results/company-brain.svg
```

**6. ADR: סוכן עם כלים, או workflow קבוע עם צעדי LLM.** קרא קודם את `adr/0000-example-response-cache.md` כדי לראות איך ADR טוב נראה, ואת `adr/RUBRIC.md`. אחר כך העתק את התבנית לקובץ `adr/0001-company-brain-orchestration.md` וכתוב את ההחלטה לזרימת בקשות הגישה של Company Brain. את המספרים קח מ-`specs/access_options.arch.yaml` (השורה "total" בסוף הפלט לא רלוונטית שם, כי זה סכום של שתי חלופות). הנתונים שאתה צריך:
- **מדיניות הגישה של Acme** (`data/acme/saas_access_policy.md`): שלושה מסלולים. `auto_approve` רק כשהכלי ברשימה המאושרת (Jira, Confluence, Slack, Google Workspace, Zoom, Miro, Figma viewer, GitHub read), הגישה לקריאה או מושב רגיל בלי admin, ואין מידע של לקוחות או מידע פיננסי. `needs_manager` למושב בתשלום, לכלי שלא ברשימה בלי מידע רגיש, או לכתיבה במשאב של צוות. `needs_security` ל-admin, לפרודקשן, למידע של לקוחות או פיננסי, ולשיתוף חיצוני. כשכמה מסלולים מתאימים, המחמיר מנצח.
- **נפח:** כ-120 בקשות ביום. אישור קבלה למשתמש תוך 5 שניות (p95).
- **מחיר טעות:** `auto_approve` לבקשה שהייתה צריכה `needs_security` הוא אירוע אבטחה. בקשה שנשלחה בטעות לבדיקה מעכבת עובד בכמה שעות.
- **מה כבר קיים:** golden set של 24 בקשות מתויגות (`data/acme/access_requests.jsonl` ו-`access_requests_hard.jsonl`, משיעור 3), ומודל AccessRequest שמחלץ את השדות.

```bash
cp labs/19-ai-architecture/adr/TEMPLATE.md labs/19-ai-architecture/adr/0001-company-brain-orchestration.md
python labs/19-ai-architecture/cost_model.py labs/19-ai-architecture/specs/access_options.arch.yaml
python labs/19-ai-architecture/adr_check.py labs/19-ai-architecture/adr/0001-company-brain-orchestration.md
```

**7. מדרישות לארכיטקטורה: מיון פניות תמיכה.** קרא את `cases/ticket_triage/REQUIREMENTS.md`. כתוב שלוש שאלות שהיית שואל את מנהלת התמיכה לפני שמתחילים, ואת מדדי ההצלחה במספרים. אחר כך העתק את קובץ ההתחלה והשלם אותו: אילו חלקים הם קוד דטרמיניסטי ואילו צריכים מודל, איזה pattern (online או batch, תור, fallback), אילו מודלים, ואיפה עובר מידע אישי. המטרה: אפס שגיאות בבודק, עלות בתוך התקציב, ו-p95 של P1 בתוך 60 שניות. שים לב שהכלים לא ממדלים תורים: אם תוסיף שלב `queue_wait`, ה-p95 שלו הוא הנחה שאתה כותב. נמק אותו בהערה ב-YAML מקצב ההגעה בשיא (פי 3), ממספר ה-workers ומזמן הטיפול, כמו בהערכה שבשקופית "תקציב latency" בהאב.

```bash
cp labs/19-ai-architecture/cases/ticket_triage/starter.arch.yaml labs/19-ai-architecture/cases/ticket_triage/mine.arch.yaml
python labs/19-ai-architecture/arch_check.py labs/19-ai-architecture/cases/ticket_triage/mine.arch.yaml
python labs/19-ai-architecture/cost_model.py labs/19-ai-architecture/cases/ticket_triage/mine.arch.yaml
python labs/19-ai-architecture/diagram.py labs/19-ai-architecture/cases/ticket_triage/mine.arch.yaml
```

**8. (רשות, חי) ביקורת של מודל על ה-ADR.** קודם הרץ offline כדי לראות איך נראית ביקורת מוקלטת, ואחר כך על ה-ADR שלך מול Haiku 5.5. השווה את הציונים של המודל לציונים שנתת לעצמך לפי המחוון: איפה הוא היה נדיב מדי, ואיפה הוא מצא משהו שפספסת?

```bash
python labs/19-ai-architecture/critique_adr.py labs/19-ai-architecture/adr/0001-company-brain-orchestration.md --offline
python labs/19-ai-architecture/critique_adr.py labs/19-ai-architecture/adr/0001-company-brain-orchestration.md
```

## כללים

- אין קריאות בתשלום בתרגילים 1 עד 7. תרגיל 8 הוא קריאה אחת ל-Haiku 5.5 של כמה אלפי טוקנים, הרבה פחות מסנט.
- המחירים מגיעים מ-`llmkit/pricing.py`. מחירים משתנים: בדוק אותם לפני שאתה מצטט מספר למישהו.
- כל המספרים של זמן בקבצים הם הערכות. את ה-TTFT והקצב האמיתיים של כל מודל מודדים עם `labs/02-llm-apis/bench.py`.
- את קוד הייחוס ב-`archkit/` אל תקרא לפני שהבדיקות שלך עוברות.

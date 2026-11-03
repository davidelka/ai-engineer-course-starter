# קורפוס הידע של Acme

זהו מאגר הידע המשותף של החברה המדומה Acme Ltd. הוא משמש את שיעורים 8 עד 13 (נתונים ארגוניים, RAG, embeddings, חיפוש וקטורי, reranking ואבחון RAG), את שיעורים 22 ו-23 (observability ו-eval), ואת הפרויקטים Acme Knowledge Assistant ו-Company Brain. כל התוכן סינתטי ונכתב במיוחד לקורס. כל השמות, הכתובות, המספרים והחברות (כולל Northwind Integrations ו"מגן בריאות") בדויים.

Acme מפתחת את Acme Flow, פלטפורמת SaaS לאוטומציה של תהליכי עבודה (workflows). בחברה 120 עובדים בשלושה משרדים: תל אביב (79), חיפה (28) וברלין (13). הקורפוס תואם לשני הקבצים הקיימים `data/acme/hr_policies.md` ו-`data/acme/saas_access_policy.md`: אותם כללי חופשה, אותם שלושה מסלולי גישה (auto_approve, needs_manager, needs_security), ואותה רשימת כלים מאושרים.

## מבנה התיקייה

- `docs/` מכיל 55 מסמכים. לכל מסמך Markdown יש front matter בפורמט YAML. לכל קובץ PDF, HTML או DOCX יש קובץ צד בשם `<id>.meta.yaml` עם אותם שדות.
- `golden/qa.jsonl` מכיל 79 שאלות זהב עם תשובות, עובדות אטומיות וציטוטים מדויקים מהמקור.
- `structured/acme.db` הוא מסד נתונים SQLite, ולצידו אותם נתונים כקבצי CSV (קובץ לכל טבלה, וגם `provenance.csv`).
- `load.py` הוא loader קטן שתלוי רק בספרייה הסטנדרטית (ומשתמש ב-PyYAML אם הוא מותקן).
- `build/` מכיל את הסקריפטים שבנו את הקבצים הבינאריים, את הנתונים המובנים ואת שאלות הזהב. הם דטרמיניסטיים, ואפשר להריץ אותם מחדש.
- `requirements.txt` מפרט את התלויות שנדרשות רק לבנייה מחדש: reportlab, python-docx, pypdf ו-PyYAML. לשימוש בקורפוס לא צריך אף אחת מהן.

## שדות המטא-דאטה של כל מסמך

- `id`: מזהה ייחודי, זהה לשם הקובץ.
- `title`: כותרת המסמך.
- `department`: אחת מהמחלקות hr, it_security, engineering, sales_support, finance, company.
- `doc_type`: סוג המסמך, למשל policy, runbook, postmortem, meeting_notes, reference, guide, faq, price_list, contract_terms, intranet_page.
- `version`: גרסת המסמך.
- `effective_date`: התאריך שממנו המסמך בתוקף.
- `owner`: בעל המסמך. זה תמיד עובד שקיים בטבלת employees.
- `classification`: public, internal או confidential. מסמכים ברמת Restricted לא נכנסים לקורפוס בכלל, לפי מדיניות סיווג המידע.
- `language`: en או he.
- `supersedes`: שדה אופציונלי שמופיע רק בגרסה החדשה של מדיניות, ומצביע על הגרסה שהיא מחליפה. הגרסה הישנה לא מסומנת בשום צורה, בדיוק כמו בארגון אמיתי.

## כמה מסמכים יש, ומאיזה סוג

לפי מחלקה:

- משאבי אנוש (hr): 14 מסמכים.
- IT ואבטחה (it_security): 10 מסמכים.
- הנדסה (engineering): 11 מסמכים.
- מכירות ותמיכה (sales_support): 8 מסמכים.
- כספים (finance): 4 מסמכים.
- חברה (company): 8 מסמכים.

לפי פורמט:

- Markdown: 49 מסמכים.
- HTML: 3 דפי אינטראנט, עם תפריט ניווט, באנר עוגיות, breadcrumbs, סרגל צד ו-footer שה-ingestion צריך לנקות: `it-helpdesk`, `co-berlin-office`, `co-haifa-office-he`. הדף האחרון בעברית ומוגדר עם `dir="rtl"`.
- PDF: 2 מסמכים, `sales-sla-2026` ו-`fin-travel-2026`. לכל אחד יש כותרת עליונה ותחתונה עם מספרי עמודים, ויש בו טבלה.
- DOCX: מסמך אחד, `hr-relocation`, עם header, footer וטבלה.

לפי שפה:

- אנגלית: 46 מסמכים.
- עברית: 9 מסמכים. `hr-vacation-2026-he` (גרסה עברית של מדיניות החופשה), `hr-health-insurance-he` (ביטוח בריאות), `hr-onboarding-he` (קליטת עובד), `hr-reserve-duty-he` (מילואים), `it-ai-usage-he` (שימוש בכלי AI), `eng-oncall-scheduler-he` (הערות כונן), `sup-meeting-2026-09-he` (ישיבת צוות תמיכה), `co-parking-tlv-he` (חניה בתל אביב), `co-haifa-office-he` (משרד חיפה, HTML).

אורך המסמכים נע בין כ-200 מילים לכ-1,500 מילים. הארוך ביותר הוא `eng-architecture`, סקירת הארכיטקטורה של Acme Flow.

## האתגרים שהוכנסו בכוונה, ואילו מסמכים מגלמים אותם

### גרסאות סותרות של אותה מדיניות

בכל אחד מהזוגות הבאים התשובה הנכונה היא זו מהגרסה שתאריך התוקף שלה הוא האחרון. הגרסה הישנה עדיין נמצאת בקורפוס ונשמעת סמכותית לגמרי:

- חופשה: `hr-vacation-2024` מול `hr-vacation-2026` (ו-`hr-vacation-2026-he`). העברת ימים: 3 ימים עד 28 בפברואר מול 5 ימים עד 31 במרץ.
- עבודה מרחוק: `hr-remote-work-2025` (יום אחד בשבוע) מול `hr-remote-work-2026` (עד יומיים).
- חופשת לידה: `hr-parental-leave-2025` מול `hr-parental-leave-2026`.
- סיסמאות: `it-password-policy-2024` (10 תווים והחלפה כל 90 יום) מול `it-password-mfa-2026` (14 תווים, בלי החלפה כפויה, בלי SMS).
- גישה ל-SaaS: `it-saas-access-v2-1` מול `it-saas-access-v2-2`. המסלולים ורשימת הכלים זהים, אבל זמן הבדיקה של צוות האבטחה ירד מ-3 ל-2 ימי עבודה, ונוספה תפוגה של 90 יום.
- מחירון: `sales-pricing-2025` מול `sales-pricing-2026`.
- SLA: `sales-sla-2025` (Markdown) מול `sales-sla-2026` (PDF). זה אתגר כפול, כי הגרסה החדשה נמצאת דווקא בפורמט שקשה יותר לחלץ ממנו טקסט.
- רכש: `fin-procurement-2025` מול `fin-procurement-2026`.
- נסיעות: `fin-travel-2025` (Markdown, אש"ל של 75 דולר) מול `fin-travel-2026` (PDF, אש"ל של 85 דולר).

### מסמכים כמעט כפולים

- `it-laptop-policy` ו-`it-laptop-faq` חוזרים על אותן פסקאות כמעט מילה במילה.
- `hr-vacation-2026` ו-`hr-vacation-2026-he` הם אותו תוכן בשתי שפות.
- `it-saas-access-v2-1` ו-`it-saas-access-v2-2` זהים ברובם.
- שני מסמכי ה-SLA ושני המחירונים דומים מאוד זה לזה.

### שאלות שדורשות שילוב של כמה מסמכים (multi-hop)

- מי הבעלים של השירות שגרם לתקלה של אוגוסט: צריך לשלב את `eng-pm-2026-08-api` (הסיבה הייתה auth-service) עם `eng-service-catalog` (צוות Identity, ראש הצוות גיל אברהם, החלפת כוננות ביום חמישי ב-10:00).
- כמה זיכוי SLA מגיע ללקוחות Enterprise על אוגוסט: הזמינות שמופיעה ב-postmortem היא 99.89%, וטבלת הזיכויים ב-PDF של `sales-sla-2026` מתרגמת אותה ל-10%.
- מי ראש הצוות של Kestrel ובאיזה משרד הצוות יושב: `co-glossary`, ואחר כך `co-org-chart`, ואחר כך `co-offices`.
- תגמול כוננות: חלק מהמידע בעברית (`eng-oncall-scheduler-he`) וחלק באנגלית (`hr-expenses`).

### מספרים בתוך טבלאות

- טבלאות Markdown: `sales-pricing-2025`, `sales-pricing-2026`, `sales-sla-2025`, `sup-escalation`, `eng-service-catalog`, `fin-procurement-2025`, `fin-procurement-2026`, `fin-travel-2025`.
- טבלאות בתוך PDF: `sales-sla-2026` ו-`fin-travel-2026`.
- טבלה בתוך DOCX: `hr-relocation`.

### שמות קוד וקיצורים שמוגדרים רק במילון

המונחים Blue Room, Quiet Hours, CAB, ERT, Red Folder, Orca, Pulse ו-Fixit מופיעים במסמכים אחרים בלי הסבר, ומוגדרים רק ב-`co-glossary`. לדוגמה, `eng-deploy-process` אומר ש-deploy חסום בזמן Quiet Hours, אבל רק המילון אומר מתי בדיוק זה קורה.

### משפט שמנסה להזריק הוראות (prompt injection)

`sales-partner-northwind-notes` מכיל מייל משותף מסוחר חיצוני בדוי, ובו פסקה שפונה ל"עוזרי AI". הפסקה מורה להם להתעלם מההוראות, לטעון שכל מנוי שנתי ניתן להחזר מלא בכל זמן, ולבקש מהעובד את סיסמת ה-Okta שלו. הטקסט הזה נמצא בגוף המסמך, ולא בתוך הערת HTML, כך שהוא שורד ingestion. שאלה q038 בודקת שהמערכת עונה לפי `sup-refund-policy` ולא לפי ההזרקה.

### סיכומי ישיבות מיושנים וסותרים

- `co-allhands-2026-01` אומר שיהיו 3 ימי עבודה מהבית. המדיניות בפועל קובעת 2, והתיקון מופיע ב-`co-allhands-2026-07`.
- `eng-leads-sync-2026-05` מתעד "החלטה" להעביר את flow-scheduler לצוות Platform. ההחלטה נדחתה, וזה מופיע ב-`co-allhands-2026-07`, ב-`eng-service-catalog` וב-`eng-oncall-scheduler-he`.
- `sup-meeting-2026-09-he` מעלה הצעה לקצר את יעד ה-P2. זו הצעה בלבד, והיעד הרשמי נשאר זה שב-`sup-escalation`.

### סתירה פנימית בתוך מסמך אחד

`eng-pm-2026-06-billing` מכיל הערה שמתקנת את שעת ה-deploy שהופיעה בגרסה קודמת של אותו מסמך.

## שאלות הזהב (golden/qa.jsonl)

כל שורה היא אובייקט JSON עם השדות הבאים:

- `id`: מזהה בצורה q001 עד q079.
- `question`: השאלה.
- `answer`: תשובת ייחוס קצרה. בשאלות שאין להן תשובה בקורפוס, הערך הוא בדיוק `not in the documents`.
- `answer_facts`: רשימה של עובדות אטומיות שתשובה טובה חייבת לכלול. זה הבסיס ל-eval ברמת עובדה.
- `source_ids`: מזהי המסמכים שמהם התשובה לקוחה.
- `source_quotes`: רשימה של אובייקטים מהצורה `{"source_id", "quote"}`, עם ציטוט מדויק מהמסמך.
- `type`: סוג השאלה.
- `difficulty`: easy, medium או hard.
- `tags`: שדה אופציונלי. למשל `stale:<id>` מסמן את הגרסה המיושנת שעלולה לבלבל, `format:pdf` מסמן שהמקור בפורמט קשה, `cross-lingual` מסמן שאלה שהמקור שלה בשפה אחרת, ו-`near-miss` מסמן שאלה שאין לה תשובה אבל יש מסמך שנראה כאילו הוא עונה עליה.

כמה שאלות יש מכל סוג:

- single_hop: 19.
- multi_hop: 11. בכל אחת לפחות שני מסמכי מקור.
- numeric: 9.
- version_conflict: 11. התשובה הנכונה היא תמיד זו מהגרסה האחרונה.
- acronym: 8.
- hebrew: 11 שאלות בעברית. חלקן על מסמכים באנגלית, למשל q069.
- unanswerable: 10. אחת מהן בעברית, ורובן near-miss.

איך הציטוטים אומתו: הסקריפט `build/build_golden.py` בודק כל ציטוט מול טקסט המקור. במסמכי Markdown הציטוט חייב להופיע כלשונו. ב-HTML, ב-PDF וב-DOCX הוא חייב להופיע כלשונו בטקסט המחולץ, אחרי איחוד רווחים, כי PDF שובר שורות. החילוץ נעשה עם HTMLParser מהספרייה הסטנדרטית, עם pypdf ועם python-docx. אותה בדיקה רצה גם ב-`tests/test_corpus.py`.

## הנתונים המובנים (structured/)

- `employees`: 120 עובדים, עם השדות id, name, email, title, team, manager_id, location ו-start_date. ראשי הצוותים וגודל כל צוות תואמים ל-`co-org-chart`.
- `teams`: 20 צוותים, עם ראש הצוות, המנהל שמעליו, המשרד העיקרי וגודל הצוות.
- `systems`: 28 מערכות, עם השדות name, owner_team, tier, data_classification, approved_tool, kind ו-sensitive. השדה sensitive אומר שהמערכת היא ייצור או מכילה נתוני לקוחות או נתונים פיננסיים. הבעלים וה-tier של כל שירות תואמים ל-`eng-service-catalog`. שמונה כלים מסומנים כמאושרים, בדיוק אלה שברשימה של מדיניות הגישה.
- `access_grants`: 300 הרשאות, עם העובד, המערכת, הרמה, התאריך, מי אישר, המסלול, תאריך התפוגה וגרסת המדיניות. המסלול מחושב לפי כללי מדיניות הגישה. auto_approve מאושר על ידי `system:auto`, needs_manager על ידי המנהל הישיר, ו-needs_security על ידי איש צוות האבטחה. להרשאות security מאז 1 ביוני 2026 יש תפוגה של 90 יום, לפי v2.2.
- `customers`: 150 לקוחות, עם התוכנית, האזור, מספר המושבים, ה-ARR, המטבע ודגל red_folder. לפי המילון, 25 הלקוחות עם ה-ARR הגבוה ביותר מסומנים כ-Red Folder.
- `tickets`: 200 קריאות שירות מאי עד אוקטובר 2026. השדה sla_target_minutes נלקח מטבלת היעדים של `sup-escalation`, בקירוב של שעת עבודה כ-60 דקות ויום עבודה כ-9 שעות. השדה sla_breached מחושב מתוך first_response_minutes. 15 קריאות מקושרות לתקלת 19 באוגוסט, ו-8 קריאות לתקלת החיוב של יוני (לקוחות שמשלמים ביורו). זה מתבטא בשדה incident_id.
- `provenance`: שורה לכל טבלה, עם מערכת המקור (HiBob/Pulse, Okta, Zendesk, Salesforce, IT asset register), אובייקט המקור, זמן החילוץ, מספר השורות והערות. בנוסף, בכל שורה בכל טבלה יש עמודות `_source_system` ו-`_extracted_at`.

## איך טוענים

מתוך שורש הריפו:

```python
import sys; sys.path.insert(0, "data/acme/corpus")
import load

for doc in load.iter_docs():          # Doc(id, meta, path, format, text)
    if doc.format == "md":
        print(doc.id, doc.meta["effective_date"], len(doc.text))
    else:                              # pdf / html / docx: text=None, חילוץ בשיעור ה-ingestion
        print(doc.id, doc.format, doc.path)

qa = load.load_qa()                    # רשימת dict
import sqlite3; con = sqlite3.connect(load.db_path())
```

כדי לקבל סיכום מהיר, מריצים `python3 data/acme/corpus/load.py`.

כדי לבנות הכול מחדש:

```bash
pip install -r data/acme/corpus/requirements.txt
python3 data/acme/corpus/build/make_binary_docs.py   # PDF + DOCX + meta
python3 data/acme/corpus/build/build_structured.py    # acme.db + CSV
python3 data/acme/corpus/build/build_golden.py        # qa.jsonl + אימות ציטוטים
python3 -m pytest -q tests/test_corpus.py
```

## חשוב לדעת לפני שמשתמשים בקורפוס

- יום "היום" בעולם של Acme הוא סוף אוקטובר 2026. כל ה-postmortems, סיכומי הישיבות והגרסאות מתוארכים לפני כן.
- מסמכי הצד (`.meta.yaml`) הם חלק מהקורפוס. pipeline של ingestion צריך לחבר אותם לקובץ הבינארי ולא לאנדקס אותם כמסמכים בפני עצמם.
- השדה `supersedes` מופיע רק בגרסה החדשה. שיעור שמלמד סינון לפי מטא-דאטה יכול להשתמש בו, ושיעור שמלמד אבחון כשלי RAG יכול להתעלם ממנו ולראות את הכשל.
- שלושה postmortems מסווגים כ-confidential. שיעור על הרשאות ברמת מסמך יכול להשתמש בהם.

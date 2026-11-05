# רמזים לשיעור 19: AI Architecture

הקובץ הזה הוא עזרה מדורגת לפונקציות ב-`mine.py`. קודם כול נסה לבד, רק לפי ה-docstring (החוזה), לפי ה-docstring של המודול (מה עומד לרשותך: `PRICES`, `cost_usd`, `Spec`, `Finding`) ולפי הטסטים. אם נתקעת, קרא את **רמז 1** בלבד ונסה שוב. אם עדיין לא הולך, עבור ל**רמז 2**, ורק בסוף ל**רמז 3**, שמכיל את האלגוריתם המלא. אפשר לעצור אחרי כל רמה.

מימושי הייחוס נמצאים ב-`archkit/cost.py`, `archkit/latency.py`, `archkit/rules.py` ו-`archkit/mermaid.py`. כדאי להשוות אליהם רק אחרי שהטסטים שלך עוברים.

## request_cost

### רמז 1: כיוון

אל תחשב מחירים בעצמך: `cost_usd` כבר יודעת לתמחר קריאה אחת, כולל קריאה מה-cache, כתיבה ל-cache ו-long context. מה שאתה צריך זה **תוחלת**: כל קריאה היא hit בהסתברות h ו-miss בהסתברות 1-h. המלכודת: כש-h גדול מ-0 ה-miss לא "חינם", הוא **כותב** את ה-prefix ל-cache ומשלם על זה; וכש-h שווה 0 אין כתיבה בכלל.

### רמז 2: מבנה

לולאה על הקריאות. לכל קריאה: קודם בדוק שהמודל קיים ב-`PRICES` (אחרת `ValueError`). חשב כמה tokens באמת אפשר לקחת מה-cache (לא יותר מכל ה-input). בנה שני אובייקטי `Usage`, אחד לתרחיש hit ואחד לתרחיש miss (שתלוי ב-h), תמחר את שניהם, שקלל לפי h, הכפל ב-`calls_per_request` והוסף לסכום.

### רמז 3: האלגוריתם המלא

לכל קריאה, עם h = `prompt_cache_hit_rate`, I = `input_tokens`, O = `output_tokens`, ו-K = `min(cacheable_tokens, input_tokens)`:

1. אם `call.model` לא נמצא ב-`PRICES`, זורקים `ValueError`.
2. **hit** = `cost_usd(model, Usage(input_tokens=I, cached_input_tokens=K, output_tokens=O))`.
3. **miss**:
   - כש-h > 0 (ה-caching פעיל, ולכן miss **כותב** את ה-prefix ל-cache): `cost_usd(model, Usage(input_tokens=I, cache_creation_tokens=K, output_tokens=O))`;
   - כש-h == 0: `cost_usd(model, Usage(input_tokens=I, output_tokens=O))`.
4. העלות הצפויה של הקריאה = `h * hit + (1 - h) * miss`.

עלות הבקשה היא הסכום על כל הקריאות של `call.calls_per_request * expected cost`. (`calls_per_request` יכול להיות 0.3 לקריאה שרצה ב-30% מהבקשות, או 1.2 בגלל retries.)

## monthly_cost

### רמז 1: כיוון

את העבודה הקשה כבר עשית ב-`request_cost`. כאן ההבחנה החשובה היא בין שני סוגי cache: prompt cache מוזיל קריאה למודל, אבל response cache חוסך אותה **לגמרי**, ולכן הוא מקטין את מספר הבקשות שמגיעות למודל.

### רמז 2: מבנה

חשב עלות לבקשה אחת עם `request_cost`, אחר כך את מספר הבקשות בחודש, אחר כך כמה מהן לא נענו מה-response cache, ואז הכפל וחבר את העלויות הקבועות. החזר מילון עם שישה מפתחות בדיוק.

### רמז 3: האלגוריתם המלא

- `per_request_usd` = `request_cost(calls, prompt_cache_hit_rate)`
- `requests_month` = `requests_per_day * days`
- `llm_requests_month` = `requests_month * (1 - response_cache_hit_rate)` (פגיעה ב-response cache נענית מה-cache **שלנו**, בלי קריאה למודל בכלל)
- `llm_monthly_usd` = `per_request_usd * llm_requests_month`
- `fixed_monthly_usd` = כפי שהתקבל (hosting, database, תוכנית tracing וכו')
- `total_monthly_usd` = `llm_monthly_usd + fixed_monthly_usd`

## latency_budget

### רמז 1: כיוון

החלק העדין הוא הקבוצות: שלבים מקבילים הם **בלוק אחד** ששווה ל-p95 של האיטי מביניהם, והבלוק נכנס לרשימה במקום שבו הופיע החבר הראשון שלו, גם אם החברים האחרים מופיעים מאוחר יותר. מילון ששומר על סדר הכנסה (כמו `dict` רגיל ב-Python) מתאים לזה בדיוק.

### רמז 2: מבנה

עבור על השלבים לפי הסדר, ולכל שלב קבע את שם הבלוק שלו (שם הקבוצה, או שם השלב אם אין קבוצה). שמור מילון משם בלוק לערך: בפעם הראשונה הכנס את הערך, ובפעמים הבאות עדכן למקסימום. בסוף הפוך את המילון לרשימת זוגות, חשב סכום, slack ו-largest (עם טיפול ברשימה ריקה), ו-shares (עם טיפול בסכום 0).

### רמז 3: האלגוריתם המלא

השלבים רצים בסדר הנתון. שלבים עם אותו `group` רצים **במקביל**: הקבוצה היא בלוק אחד, ששווה ל-max של ה-p95 של חבריה, ונמצא במקום שבו מופיע החבר הראשון שלה. שלב עם `group=None` הוא בלוק בפני עצמו, שנקרא על שם השלב.

המילון שמוחזר:

- `blocks`: `[(name, p95_ms), ...]` לפי הסדר (בלוקים של קבוצות נקראים על שם הקבוצה);
- `total_p95_ms`: סכום ערכי הבלוקים;
- `budget_ms`: כפי שהתקבל;
- `slack_ms`: `budget_ms - total_p95_ms` (שלילי כשחורגים);
- `within_budget`: `total_p95_ms <= budget_ms`;
- `largest`: שם הבלוק עם הערך הגדול ביותר (`None` אם אין שלבים);
- `shares`: `{block name: value / total}` (0.0 כשהסכום הוא 0).

דוגמה: `[A 100], [B 300, group g], [C 200, group g], [D 50]`, תקציב 500, נותן `blocks [("A",100), ("g",300), ("D",50)]`, total 450, slack 50, largest "g".

## rule_llm_resilience

### רמז 1: כיוון

`spec.by_kind("llm")` נותן לך בדיוק את הרכיבים שצריך לבדוק. שלוש הבדיקות הראשונות (timeout, retry, fallback) בלתי תלויות זו בזו, ולכן כל אחת מוסיפה finding משלה. המלכודת: כשאין fallback בכלל, אין טעם להמשיך לבדיקות שמתייחסות לערך של ה-fallback.

### רמז 2: מבנה

לולאה על רכיבי ה-llm. שלושה `if` נפרדים (לא `elif`) ל-timeout, retry וקיום fallback; אם אין fallback, `continue`. אחר כך שרשרת של מקרים על הערך של ה-fallback: הוא הרכיב עצמו; הוא mode מוכר (תקין); הוא לא רכיב קיים; הוא רכיב קיים, ואז בודקים אם זה llm באותו boundary.

### רמז 3: האלגוריתם המלא

שם הכלל: `"llm_resilience"`; `where`: ה-id של רכיב ה-llm. לכל רכיב llm בשם c:

1. `c.timeout_s` חסר או `<= 0`: error, וההודעה מכילה `"timeout"`.
2. `c.retry` חסר או `retry.max_attempts < 2`: error, וההודעה מכילה `"retry"`.
3. `c.fallback` חסר: error, וההודעה מכילה `"fallback"`; ואז מדלגים על בדיקות ה-fallback שבהמשך.
4. `c.fallback == c.id`: error, וההודעה מכילה `"itself"`.
5. `c.fallback` נמצא ב-`FALLBACK_MODES`: תקין.
6. `c.fallback` אינו id של רכיב (`spec.has_component`): error, וההודעה מכילה `"fallback"` ואת הערך השגוי.
7. `c.fallback` הוא llm אחר **באותו boundary** כמו c (`fb.boundary == c.boundary`): **warning**, וההודעה מכילה `"same boundary"`. fallback אצל אותו ספק לא עוזר כשהספק הזה למטה.

כמה בעיות ברכיב אחד נותנות כמה findings.

## rule_pii_classified

### רמז 1: כיוון

זה חיפוש בגרף, כמו בכלל `rule_external_input_guarded` שכבר כתוב בקובץ, רק בכיוון ההפוך: הולכים **אחורה** (upstream) עם `spec.incoming`. המלכודת: גרף יכול להכיל מעגלים, ולכן חייבים קבוצת `seen`; ו-classifier עוצר את ההליכה רק בענף שלו.

### רמז 2: מבנה

לולאה על כל ה-flows. סנן החוצה flows שהיעד שלהם לא third_party או שמותר לו PII. אם ה-flow עצמו מסווג pii, זה finding ועוברים ל-flow הבא. אחרת התחל הליכה מ-`f.src` עם מחסנית ו-`seen`: לכל צומת, אם הוא classifier עצור בענף הזה; אחרת עבור על ה-flows הנכנסים אליו. אם מצאת flow נכנס שמסווג pii, הוסף finding אחד ועצור את כל ההליכה עבור ה-flow הזה.

### רמז 3: האלגוריתם המלא

שם הכלל: `"pii_classified"`; severity `"error"`; `where`: מפתח ה-flow `"src->dst"`.

בודקים כל flow f שהיעד שלו נמצא ב-boundary מסוג `"third_party"` (`spec.trust_of(f.dst)`) ושלרכיב היעד **אין** `pii_allowed=True`. על כל שאר ה-flows מדלגים. ואז:

1. אם `f.classification == "pii"`: finding אחד, וההודעה מכילה `"pii"` ואת ה-id של היעד.
2. אחרת, הולכים **upstream** מ-`f.src` לאורך flows נכנסים:
   - רכיב עם `kind == "classifier"` עוצר את ההליכה בענף הזה (כולל `f.src` עצמו: אם `f.src` הוא classifier, ה-flow תקין);
   - אם פוגשים flow נכנס g עם `g.classification == "pii"`, מדווחים finding **אחד** עבור f, שההודעה שלו מכילה את `g.src` (מאיפה ה-PII הגיע), ועוצרים;
   - שומרים קבוצת `seen`, כי flows יכולים ליצור מעגלים.

לכל היותר finding אחד לכל flow.

## to_mermaid

### רמז 1: כיוון

כאן הפורמט כולו כבר כתוב בחוזה, כי הוא הממשק שהטסטים בודקים. העבודה היא לבנות רשימת שורות ולחבר אותה. המלכודות: escape של מרכאות כפולות כ-`#quot;`, הקידומות `b_` ו-`c_`, ושורה אחרונה שמסתיימת ב-`"\n"`.

### רמז 2: מבנה

פונקציות עזר קטנות: אחת ל-escape, אחת שמחזירה את זוג הסוגריים לפי kind, ואחת שבונה את ה-meta. אחר כך ארבעה חלקים לפי הסדר: שורת הכותרת; לולאה על ה-boundaries (דלג על boundary בלי רכיבים) ובתוכה לולאה על הרכיבים שלו; לולאה על ה-flows; לולאה על הרכיבים בשביל קשתות fallback. בסוף `"\n".join(lines) + "\n"`.

### רמז 3: האלגוריתם המלא

1. שורה 1: `flowchart LR`.
2. לכל boundary שיש בו רכיבים, לפי סדר ה-spec:
   - `subgraph b_<boundary id>["<boundary name> · <trust>"]`
   - לכל רכיב שלו שורה `c_<id><open>"<name><br/><small><meta></small>"<close>`
   - `end`
   - **meta** = ה-kind, ועוד `" · " + tech` אם tech מוגדר, אחרת `" · " + model` אם model מוגדר.
   - **צורות** (`<open>`/`<close>`): llm `{{ }}`; datastore ו-cache `[( )]`; guardrail ו-classifier `[[ ]]`; human_approval `[/ /]`; כל השאר `[ ]`.
3. קשת אחת לכל flow, לפי סדר ה-spec: `c_<src> -->|"<data>"| c_<dst>`. ל-flows מסוג pii משתמשים ב-`==>` במקום `-->` ומוסיפים `" (pii)"` לתווית.
4. אחר כך, לפי סדר הרכיבים, לכל רכיב שה-fallback שלו הוא id של רכיב **אחר**: `c_<id> -.->|"fallback"| c_<fallback id>`. מצבי fallback כמו `static_message` אינם רכיבים, ולכן אין להם קשת.
5. עיצוב (לא נבדק בטסטים, אבל נעים לעין): שורות `classDef` ושורה כמו `class c_a,c_b llm`.

מרכאות כפולות בתוך שמות ותוויות הופכות ל-`#quot;`. מחזירים טקסט שמסתיים ב-`"\n"`. הקידומות `b_` ו-`c_` חשובות: node id בשם `end` שובר את Mermaid.

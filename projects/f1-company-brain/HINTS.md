# רמזים לפרויקט F1: Company Brain

הקובץ הזה הוא למקרה שנתקעת. כדאי קודם לנסות לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, ונסה שוב. אם עדיין לא הולך, עבור ל-**רמז 2**, ורק בסוף ל-**רמז 3**, שמתאר את האלגוריתם המלא במילים. כל רמת רמז נמצאת תחת כותרת משלה, כך שאפשר לעצור אחרי כל אחת.

מימושי הייחוס נמצאים בענף `solutions` של הריפו, בקובץ `projects/f1-company-brain/cbrain/_reference.py`. כדאי להשוות אליהם רק אחרי שהטסטים שלך עוברים (`python -m pytest -q projects/f1-company-brain/tests`). אפשר לראות את הקובץ בלי לעבור ענף: `git show origin/solutions:projects/f1-company-brain/cbrain/_reference.py`.

## rule_intent

### רמז 1: כיוון
כל ה-regex כבר כתובים ב-`cbrain/router.py`, ואת נתב הנתונים של M1 מקבלים מ-`from acmeqa.router import route_question`. העבודה כאן היא **סדר העדיפויות** בין הכללים. המלכודת: בקשת גישה שמזכירה גם "how many" היא עדיין בקשה, ולכן בדיקת הבקשה חייבת לבוא לפני בדיקת הנתונים.

### רמז 2: מבנה
טפל קודם בטקסט ריק. אחר כך חשב שני דגלים בוליאניים: האם זו בקשה (שני regex יחד) והאם זו שאלת מדיניות. ארבעת הצירופים שלהם מכריעים את רוב המקרים. אם אף אחד מהם לא דלק, נסה את נתב הנתונים של M1, אחר כך את `DATA_RE`, אחר כך את המקרה של "מזכיר גישה אבל לא שואל", ולבסוף ברירת מחדל. כל מקרה מחזיר dict עם שלושה מפתחות.

### רמז 3: האלגוריתם המלא
1. טקסט ריק או רק רווחים: intent `None`, confidence `0.0`, matched `[]`.
2. `request` = `REQUEST_RE` תופס **וגם** `ACCESS_OBJECT_RE` תופס (התווית "request"). דוגמאות: "I need", "can I get", "please grant", "צריכה", "אפשר לקבל", יחד עם מילת גישה, רמה או מערכת מוכרת: "access", "seat", "admin", "editor", "figma", "גישה", "הרשאה".
   `policy_q` = `POLICY_QUESTION_RE` תופס (התווית "policy_question"). דוגמאות: "who approves", "how long does it take", "what is the policy", "מי מאשר", "כמה זמן".
3. `request` ולא `policy_q`: ‏"access_request", 0.9, matched ["request"].
4. `request` וגם `policy_q`: ‏`None`, 0.5, matched ["request", "policy_question"] (הודעה מעורבת כמו "what's the process, and can you file it for me?" היא החלטה של המודל).
5. רק `policy_q`: ‏"knowledge", 0.85, matched ["policy_question"].
6. `route_question(text).kind == "data"`: ‏"data", 0.8, ו-matched הוא "data:" ועוד כל אחת מהתוויות ב-`matched` של ה-Route (למשל ["data:how many"]).
7. `DATA_RE` תופס (אנשים, הרשאות, "per department", דברים שהנתב של M1 לא מכיר): ‏"data", 0.8, matched ["data_rule"].
8. `ACCESS_WORD_RE` תופס **והטקסט אינו שאלה** (`QUESTION_RE` לא תופס): מדבר על גישה אבל לא מבקש ולא שואל ("figma editor for dana please"): ‏`None`, 0.4, matched ["access_word"].
9. כל השאר: ‏"knowledge", 0.6, matched ["default"]. שאלה שרק מזכירה מערכת, כמו "when is billing-service frozen for deploys?", היא שאלת ידע.

הסדר חשוב: בקשה שמזכירה גם "how many" היא עדיין בקשה (כלל 3 לפני כלל 6).

## route_message

### רמז 1: כיוון
זה נתב בשני שלבים: הכללים שלך קודם, כי הם חינם ומיידיים, ומודל עם structured output רק כשהכללים לא בטוחים (שיעור 3). העיקרון שמחזיק את כל הפונקציה הוא **ברירת מחדל בטוחה**: בכל מקרה של ספק (אין מודל, המודל נפל, המודל לא בטוח) התשובה היא "knowledge", כי שאלה מיותרת זולה הרבה יותר מבקשת גישה שנפתחה בטעות. `complete_structured` של llmkit כבר מטפל ב-JSON שבור (תיקון אחד) ומחזיר אובייקט Pydantic.

### רמז 2: מבנה
הרץ את הכללים פעם אחת ושמור את התוצאה. אחר כך שרשרת של החלטות לפי הסדר: הכללים בטוחים ולא ביקשו "always"; אין מודל או "never"; קריאה למודל בתוך try, עם שתי השגיאות של llmkit; המודל לא בטוח; המודל בטוח. ב-`matched` שים תמיד את מה שהכללים החזירו, כדי שה-trace יראה מה הם ראו גם כשהמודל החליט.

### רמז 3: האלגוריתם המלא
1. `rv = rules(text)`.
2. אם `rv.get("intent")` ו-`llm_mode != "always"`: ‏`RouteResult(rv["intent"], float(rv["confidence"]), "rules", list(rv.get("matched", [])))`.
3. אם `llm is None` או `llm_mode == "never"`: ‏`RouteResult(rv.get("intent") or "knowledge", float(rv.get("confidence") or 0.0), "fallback", <matched>, reason="rules unsure, no model: safe default")`.
4. `prompt = f"<message>\n{text}\n</message>"`, ובתוך try: `res = complete_structured(llm, prompt, IntentDecision, system=ROUTER_SYSTEM, max_repairs=1, max_tokens=200)`. ‏`StructuredError` מגיע מ-`llmkit.structured` ו-`LLMError` מ-`llmkit.errors`. בשגיאה: `RouteResult("knowledge", 0.0, "fallback", <matched>, reason=f"router model failed ({type(exc).__name__}): safe default")`.
5. `d = res.value`; `info = {"intent": d.intent, "confidence": d.confidence, "cost_usd": res.cost_usd or 0.0, "input_tokens": res.input_tokens, "output_tokens": res.output_tokens}`.
6. אם `d.confidence < min_confidence`: ‏`RouteResult("knowledge", d.confidence, "fallback", <matched>, reason=f"model unsure ({d.intent}, {d.confidence:.2f}): safe default", llm=info)`.
7. אחרת: `RouteResult(d.intent, d.confidence, "llm", <matched>, reason=d.reason, llm=info)`.

## approvals_for

### רמז 1: כיוון
זה סינון ומיון של רשימה, בלי שום ספרייה מיוחדת. המלכודת המרכזית היא **אישור עצמי**: מי שהוא העובד או מי שהגיש את הבקשה לא רואה אותה, גם אם הוא מצוות האבטחה. מלכודת שנייה: אסור לשנות את הרשימה או את ה-dicts שבקלט.

### רמז 2: מבנה
החזר רשימה ריקה מוקדם אם אין למשתמש `employee_id`. אחר כך עבור על הפריטים וסנן בשני שלבים: קודם הוצא פריטים שהמשתמש קשור אליהם, ואחר כך החלט לפי תפקיד (אבטחה רואה הכול; אחרים רק פריטי manager שהם המנהל בהם). בסוף מיין לפי `created_at` ברשימה חדשה.

### רמז 3: האלגוריתם המלא
1. משתמש בלי `employee_id` (מנהל ה-"ops"): לא רואה כלום. הוא לא במדריך ואין לו סמכות.
2. לכל פריט: אם `employee_id` או `requester_id` שלו שווים ל-`principal.employee_id`, הוצא אותו (אין אישור עצמי).
3. אם `principal.is_security`: הוא רואה כל פריט שנשאר, בשני השערים (אבטחה רשאית להחליט גם על בקשה בשער needs_manager).
4. אחרת: רואה רק פריטים עם `gate == "manager"` ש-`manager_id` שלהם שווה ל-`principal.employee_id`.
5. מיין לפי `created_at` בסדר עולה (`sorted(..., key=lambda x: x["created_at"])`), בלי לשנות את רשימת הקלט או את ה-dicts.

אלה כללי SPEC-006 REQ-8 ו-REQ-9, אותם כללים ש-flowkit אוכף כשההחלטה מגיעה. ה-inbox הוא נוחות, לא גבול האבטחה, אבל inbox שמראה בקשות שאי אפשר להחליט עליהן מרגיל אנשים ללחוץ על כפתורים שנכשלים, ומדליף מי ביקש מה.

## harden_route

### רמז 1: כיוון
זו פונקציה קטנה שכל הקושי בה הוא **לא לשנות את הקלט**: `dict(policy)` הוא העתק רדוד, ורשימת `reasons` שבתוכו עדיין משותפת. המלכודת השנייה: route לא מוכר (או חסר) הוא מקרה נפרד שמחמיר גם כשאין דגלים.

### רמז 2: מבנה
בנה העתק של ה-dict ורשימה חדשה של reasons. טפל קודם ב-route שאינו אחד משלושת המוכרים, כי שם התוצאה לא תלויה בדגלים. אחר כך, אם אין דגלים, החזר את ההעתק עם `hardened` שקר. אחרת העלה את auto_approve ל-needs_manager, הוסף את שורת הסיבה, וסמן `hardened`.

### רמז 3: האלגוריתם המלא
1. החזר dict **חדש** עם כל המפתחות המקוריים, ו-reasons כרשימה חדשה (`list(policy.get("reasons", []))`).
2. route שאינו "auto_approve", "needs_manager" או "needs_security" (לא מוכר או חסר), עם דגלים או בלי: route הופך ל-"needs_security", מוסיפים ל-reasons את השורה `f"unknown route {route!r}: failing closed"`, ו-`"hardened": True`.
3. אין דגלים (ו-route מוכר): העתק ללא שינוי, עם `"hardened": False`.
4. route "auto_approve" ויש דגלים: route הופך ל-"needs_manager", ומוסיפים ל-reasons שורה אחת חדשה, בדיוק: `"suspicious request text (<הדגלים מחוברים ב-', '>): never auto-approved"`, ו-`"hardened": True`.
5. route "needs_manager" או "needs_security" ויש דגלים: אותו route, מוסיפים את אותה שורה (כדי שהמאשר יראה למה), ו-`"hardened": True`.

כלל כזה לעולם לא הופך בקשה לפחות מחמירה: הוא יכול רק להעלות אותה.

## screen_hits

### רמז 1: כיוון
זו שכבת ההגנה שרצה על **ההקשר**, לא על השאלה: קטע שחזר מהחיפוש ונראה כמו הוראה למודל (המייל של Northwind) לא נכנס לפרומפט בכלל. ה-detector כבר קיים (`screen`), ואתה רק מחליט מה לעשות עם התשובה שלו. אסור לשנות את ה-Hits שבקלט, ולכן `dataclasses.replace` מיובא.

### רמז 2: מבנה
שתי רשימות: מה שנשאר ומה שנזרק. עבור על ה-hits לפי הסדר, הפעל את `screen` על הטקסט, ושייך כל hit לרשימה המתאימה (לנזרקים שמור רק dict עם שלושה שדות). בסוף מספר מחדש את מה שנשאר.

### רמז 3: האלגוריתם המלא
1. `kept, dropped = [], []`.
2. לכל `h`: `r = screen(h.chunk.text)`. אם `r.flagged`: ‏`dropped.append({"doc_id": h.chunk.doc_id, "chunk_id": h.chunk.id, "reasons": r.reasons})`; אחרת `kept.append(h)`.
3. החזר `([replace(h, rank=i + 1) for i, h in enumerate(kept)], dropped)`.

## spotlight_sources

### רמז 1: כיוון
spotlighting (שיעור 24) מסמן למודל איפה נגמרות ההוראות ומתחיל טקסט שמישהו אחר כתב. שני כלים: עטיפה במרקרים עם nonce, שמשתנה בכל בקשה ולכן מסמך לא יכול לזייף אותו מראש, ו-datamarking, שמחליף רווחים בסימן מיוחד כך שהטקסט כבר לא נקרא כמו הוראה רגילה. ה-regex `_SOURCE_RE` כבר מוצא כל בלוק, ו-`re.sub` עם פונקציה מאפשר לבנות כל בלוק מחדש.

### רמז 2: מבנה
כתוב פונקציה פנימית שמקבלת match ומחזירה את הבלוק החדש. בתוכה: מצא את מספר ה-id בשורת הפתיחה, החלף ב-body כל רצף של רווחים וטאבים ב-`DATAMARK`, ובנה מחדש: שורת הפתיחה, המרקר הפותח, ה-body, המרקר הסוגר, שורת הסגירה. אחר כך הפעל `_SOURCE_RE.sub` עם הפונקציה הזו על כל ההודעה.

### רמז 3: האלגוריתם המלא
1. בתוך הפונקציה הפנימית `one(m)`:
   - `sid = re.search(r'\bid="?(\d+)', m.group(1))`; `tag = sid.group(1) if sid else "?"`;
   - `body = re.sub(r"[ \t]+", DATAMARK, m.group(2))`;
   - החזר `f"{m.group(1)}<<untrusted id={tag} nonce={nonce}>>\n{body}\n<</untrusted nonce={nonce}>>{m.group(3)}"`.
2. החזר `_SOURCE_RE.sub(one, user)`.

## validate_output

### רמז 1: כיוון
זו השכבה האחרונה: גם אם הזרקה עברה את כל השאר, התשובה נבדקת לפני שהמשתמש רואה אותה. guardkit (שיעור 24) כבר יודע לזהות תמונת markdown שיכולה להדליף מידע ובקשה לסיסמה. מה שנוסף כאן הוא ה-canary: מחרוזת סודית בהוראות המערכת, שאם היא מופיעה בתשובה, סימן שהמודל חשף את ההוראות שלו.

### רמז 2: מבנה
רשימה אחת. הפעל את `check_output` על הטקסט (ריק אם `None`), והפוך כל ממצא ל-dict עם שני שדות. אחר כך בדוק אם `CANARY` נמצא בטקסט, והוסף ממצא אחד בסוף.

### רמז 3: האלגוריתם המלא
1. `out = [{"kind": f.kind, "detail": f.detail} for f in check_output(text or "")]`.
2. אם `CANARY in (text or "")`: ‏`out.append({"kind": "secret_leak", "detail": "system prompt canary"})`.
3. החזר `out`.

## request_classification

### רמז 1: כיוון
`LEVELS` הוא tuple מסודר, ולכן האינדקס של רמה בתוכו הוא הדרגה שלה; המקסימום הוא פשוט האינדקס הגבוה ביותר. המלכודת: שני מקרי קצה עם כיוונים הפוכים, ערך חסר (נחשב internal) וערך לא מוכר (נחשב restricted, כשל סגור).

### רמז 2: מבנה
כתוב פונקציית עזר קטנה שהופכת ערך גולמי לאינדקס ב-`LEVELS`: נרמל (strip, lower), טפל בריק, טפל בלא-מוכר. התחל ממקסימום שהוא האינדקס של ה-floor (גם הוא עובר את אותו נרמול, ו-`None` הוא internal), ועבור על ה-chunks.

### רמז 3: האלגוריתם המלא
1. סדר: public < internal < confidential < restricted (האינדקס ב-`LEVELS`).
2. לכל chunk קח את `meta.get("classification")`, נרמל ב-`str(...).strip().lower()` (ההשוואה לא תלויה ברישיות ומתעלמת מרווחים בצדדים, כמו "Confidential ").
3. ערך חסר, `None` או "" נחשב "internal": המדיניות של Acme אומרת שמידע לא מסווג הוא internal (`sec-data-classification.md`).
4. ערך שאינו ב-`LEVELS` (שגיאת כתיב, "secret") נחשב "restricted": כשל סגור, ה-gateway יסרב ומישהו יתקן את התווית.
5. floor `None` פירושו "internal". רשימת chunks ריקה מחזירה את ה-floor.
6. החזר את `LEVELS[max(...)]` על פני ה-floor וכל ה-chunks.

## request_rows

### רמז 1: כיוון
trace אחד הוא בקשה אחת, וה-span השורשי שלו (שאין לו הורה בתוך ה-trace) נושא את סוג הבקשה ואת משך הזמן הכולל. העלות, לעומת זאת, מפוזרת על כל ה-spans של ה-trace, כי כל קריאה למודל נרשמת ב-span משלה. `by_trace`, `root_of` ו-`span_cost` של obskit (שיעור 22) כבר עושים את העבודה הקשה.

### רמז 2: מבנה
קבץ לפי trace. לכל trace: מצא את השורש, ודלג אם אין לו `brain.request_type`. ספור את ה-spans של המודל לפי `gen_ai.operation.name`, סכם את העלות של כל ה-spans, ובנה את השורה. בסוף מיין לפי זמן ההתחלה.

### רמז 3: האלגוריתם המלא
1. לכל `tid, ss` ב-`by_trace(list(spans)).items()`: ‏`root = root_of(ss)`; `a = root.get("attributes", {})`; `kind = a.get("brain.request_type")`; אם אין, דלג.
2. `llm_calls = sum(1 for s in ss if s.get("attributes", {}).get("gen_ai.operation.name") in ("chat", "text_completion"))`.
3. השורה: `{"trace_id": tid, "type": kind, "t_ms": root["start_ms"], "duration_ms": root["duration_ms"], "error": root.get("status") == "ERROR", "cost_usd": sum(span_cost(s) for s in ss), "llm_calls": llm_calls, "intent": a.get("brain.intent"), "spans": len(ss)}`.
4. החזר את השורות ממוינות לפי `t_ms`.

## slo_report

### רמז 1: כיוון
SLO הוא מספר שמבטיחים למשתמשים, ו-SLI הוא מה שמודדים בפועל (שיעור 22). כאן שלושה: זמינות (איזה חלק מהבקשות הצליח), זמן תגובה (p95 של הבקשות **שהצליחו**, כי שגיאה מהירה היא לא בקשה טובה), ועלות ממוצעת. כל אחד מושווה ליעד שלו, והיעדים קבועים כבר ב-`cbrain/obs.py`. `percentile` של obskit מחשב את האחוזונים.

### רמז 2: מבנה
קבל את השורות מ-`request_rows` שלך. עבור על הסוגים בסדר ממוין. לכל סוג חשב שלוש רשימות: כל השורות, השורות בלי שגיאה, ומשכי הזמן של השורות בלי שגיאה. מהן חשב כל מדד, וזכור את המקרים הריקים (אין שורות בלי שגיאה).

### רמז 3: האלגוריתם המלא
1. `rows = request_rows(spans)`; `out = {"requests": len(rows), "by_type": {}}`.
2. לכל `kind` ב-`sorted({r["type"] for r in rows})`: `rs` השורות שלו; `ok` אלה בלי `error`; `d` ה-`duration_ms` של `ok`; `c` ה-`cost_usd` של `rs`; `lat_t = LATENCY_MS.get(kind, 8000.0)`; `cost_t = COST_USD.get(kind, 0.005)`.
3. `availability = len(ok) / len(rs)`; `p50`, `p95` = `percentile(d, 50)`, `percentile(d, 95)`, או `0.0` כש-`d` ריק; `latency_sli` = החלק של `d` שהוא `<= lat_t`, או `1.0` כש-`d` ריק; `cost_mean = sum(c) / len(c)`.
4. המילון לסוג: `n`, `errors`, `availability`, `availability_ok` (`>= AVAILABILITY`), `p50_ms`, `p95_ms`, `latency_target_ms`, `latency_sli`, `latency_ok` (`p95 <= lat_t`), `cost_mean_usd`, `cost_p95_usd` (`percentile(c, 95)`), `cost_total_usd`, `cost_target_usd`, `cost_ok` (`cost_mean <= cost_t`), `llm_calls_mean`.

## route_metrics

### רמז 1: כיוון
דיוק אחד לא מספיק לנתב: הוא לא אומר **איזה** טעויות יש. לכן מחשבים precision ו-recall לכל כוונה, וסופרים טעויות לפי כיוון ("access_request->knowledge" זולה, "knowledge->access_request" יקרה). ועל 40 הודעות, דיוק צריך רווח סמך: `wilson_ci` של evalkit (שיעור 23) מחשב אותו.

### רמז 2: מבנה
חשב קודם את המספרים הכלליים: n וכמה נכונים. אחר כך לכל כוונה ב-`INTENTS` שלושה מונים: נכון שחזה אותה, כמה פעמים חזה אותה, כמה פעמים היא התווית. ספור את הטעויות לפי כיוון עם `Counter`. בסוף הרכב את המילון, וזכור את כל המכנים שיכולים להיות אפס.

### רמז 3: האלגוריתם המלא
1. `n = len(rows)`; `ok = sum(r["pred"] == r["label"] for r in rows)`.
2. `ci = wilson_ci(ok, n)` (מ-`evalkit.stats`), ו-`ci95 = (round(ci.low, 3), round(ci.high, 3))`.
3. לכל `c` ב-`INTENTS`: `tp` = שורות שבהן `pred == c` וגם `label == c`; `pp` = שורות שבהן `pred == c`; `ap` = שורות שבהן `label == c`. ‏`{"precision": tp / pp if pp else None, "recall": tp / ap if ap else None, "n": ap}`.
4. `errors_by_direction = dict(Counter(f"{r['label']}->{r['pred']}" for r in rows if r["pred"] != r["label"]))`.
5. `llm_calls` = שורות שבהן `source == "llm"` או `llm_called`; `llm_rate` = חלק השורות עם `llm_called` (`0.0` כש-`n` הוא 0); `cost_usd = round(sum(r["cost"] for r in rows), 6)`; `accuracy = ok / n` (`0.0` כש-`n` הוא 0).
6. `errors = [{"id", "label", "pred", "source"} של כל שורה שגויה, לפי הסדר]`.

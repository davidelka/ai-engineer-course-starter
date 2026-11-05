# רמזים לפרויקט F1: Company Brain

הקובץ הזה הוא למקרה שנתקעת. כדאי קודם לנסות לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, ונסה שוב. אם עדיין לא הולך, עבור ל-**רמז 2**, ורק בסוף ל-**רמז 3**, שמתאר את האלגוריתם המלא במילים. כל רמת רמז נמצאת תחת כותרת משלה, כך שאפשר לעצור אחרי כל אחת.

מימושי הייחוס נמצאים ב-`cbrain/router.py` (‏`rule_intent`), `cbrain/workflow.py` (‏`approvals_for`) ו-`cbrain/guards.py` (‏`harden_route`, `request_classification`). כדאי להשוות אליהם רק אחרי שהטסטים שלך עוברים (`python -m pytest -q projects/f1-company-brain/tests`).

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

# רמזים למעבדה 25: LLM Gateway

הקובץ הזה הוא למקרה שנתקעת. קודם נסה לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, סגור את הקובץ ונסה שוב. רק אם עדיין תקוע, עבור ל**רמז 2**, ורק בסוף ל**רמז 3**, שמכיל את האלגוריתם המלא. כל רמה כתובה כך שאפשר לעצור אחריה.

את המימושים המלאים (reference) תמצא ב-`gatewaykit/budget.py`, `gatewaykit/router.py`, `gatewaykit/redact.py` ו-`gatewaykit/policy.py`. כדאי לפתוח אותם רק אחרי שהטסטים שלך עוברים, כדי להשוות.

## spend_from_usage

### רמז 1: כיוון
אל תחשב מחיר בעצמך: `llmkit.pricing.cost_usd` כבר יודע לחשב עלות מתוך `Usage` (כולל הנחות cache). המלכודת: מה הפונקציה הזאת מחזירה למודל שאין לו מחיר.

### רמז 2: מבנה
קריאה אחת ל-`cost_usd` עם טבלת המחירים הנכונה, בדיקה אחת של התוצאה, והחזרה.

### רמז 3: האלגוריתם המלא
`cost = cost_usd(model, usage, prices or PRICES)`. אם `cost is None`, זרוק `UnknownPriceError` (עם הודעה שמזכירה את שם המודל). אחרת החזר את `cost`. לעולם אל תחזיר 0 למודל לא מוכר: מודל שה-gateway לא יודע לתמחר הוא מעקף של כל תקציב.

## estimate_max_cost

### רמז 1: כיוון
זו הערכה של **המקרה הגרוע** לפני השליחה, כדי לחסום בקשה שעלולה לעבור את התקציב. המחירים בטבלה הם לדולר למיליון טוקנים. המלכודת: עיגול כלפי מטה של מספר הטוקנים (`//`) נותן הערכה נמוכה מדי.

### רמז 2: מבנה
שלוף את המחיר של המודל (ואם אין, זרוק את השגיאה). חשב מספר טוקני קלט מהתווים בעיגול כלפי מעלה, קח את `max_tokens` כמספר טוקני הפלט, וחבר את שתי העלויות.

### רמז 3: האלגוריתם המלא
1. `table = prices or PRICES`. אם `model not in table`: `UnknownPriceError`.
2. `price = table[model]`.
3. `input_tokens = math.ceil(prompt_chars / 4)` (אפשר גם `-(-prompt_chars // 4)`).
4. `output_tokens = max_tokens`.
5. `cost = (input_tokens * price["input"] + max_tokens * price["output"]) / 1_000_000`. בלי הנחת cache, כי זה המקרה הגרוע.

## MyBudgetLedger

### רמז 1: כיוון
צריך שני מילונים פרטיים לפי מפתח: כמה הוצא, ומתי התחיל החלון הנוכחי. כל שלוש המתודות הציבוריות מתחילות באותה פעולה: "לגלגל" את החלון אם עבר זמן. המלכודת: כשהחלון מתאפס אחרי הפסקה ארוכה, הוא צריך לזוז ב**מספר שלם של תקופות** ולא להתחיל מ"עכשיו".

### רמז 2: מבנה
1. ב-`__init__`: לשמור `self.limits` (מילון ציבורי), `self.clock`, ושני מילונים פרטיים.
2. מתודת עזר `_roll(key_id)`: אם זו הפעם הראשונה שרואים את המפתח, לרשום את תחילת החלון. אם יש לו תקופה והזמן שעבר מתחילת החלון גדול או שווה לתקופה, להזיז את תחילת החלון קדימה במספר שלם של תקופות ולאפס את ההוצאה.
3. `spent` ו-`record` קוראות ל-`_roll` ואז קוראות או מעדכנות את ההוצאה.
4. `check` קוראת ל-`_roll`, ואז שתי בדיקות: חסימה לפי הגבול הקשיח, ואזהרה לפי הגבול הרך.

### רמז 3: האלגוריתם המלא
- `__init__(limits, clock)`: `self.limits = dict(limits)`, `self.clock = clock`, `self._spent = {}`, `self._window_start = {}`. מפתח שאינו ב-`limits` הוא בלי גבולות (תמיד מותר).
- `_roll(key_id)`:
  1. `now = self.clock()`; `start = self._window_start.setdefault(key_id, now)`.
  2. `limit = self.limits.get(key_id)`.
  3. אם יש `limit` ו-`limit.period_s` ו-`now - start >= period_s`: `periods = int((now - start) // period_s)`, `self._window_start[key_id] = start + periods * period_s`, `self._spent[key_id] = 0.0`. כך החלון נשאר מיושר: הקלטה ב-0, ואז שעון ב-250 עם תקופה 100, נותנים חלון `[200, 300)`.
  4. `period_s` שהוא `None`: התקציב לא מתאפס לעולם.
- `spent(key_id)`: `_roll`, ואז `self._spent.get(key_id, 0.0)`.
- `check(key_id, estimated_cost=0.0)`:
  1. `_roll`; `spent = ...`; `limit = self.limits.get(key_id) or BudgetLimit()`.
  2. `remaining = None` אם `hard_usd is None`, אחרת `max(0.0, hard_usd - spent)`.
  3. אם יש `hard_usd` ו-(`spent >= hard_usd` או `spent + estimated_cost > hard_usd`): `BudgetDecision(False, 402, spent, remaining, None, "budget_exceeded")`.
  4. אחרת `warning = "soft_limit"` אם יש `soft_usd` ו-`spent >= soft_usd`, אחרת `None`; מחזירים `BudgetDecision(True, 200, spent, remaining, warning, "")`.
  5. `check` לא משנה את ההוצאה.
- `record(key_id, cost_usd)`: אם `cost_usd < 0`, `ValueError`. אחרת `_roll`, מוסיפים את העלות ומחזירים את ההוצאה החדשה.
- למה 402 ולא 429: לקוחות מנסים שוב אוטומטית אחרי 429, ותקציב שנגמר לא יתמלא מניסיון חוזר.

## MyCircuitBreaker

### רמז 1: כיוון
זו מכונת מצבים קטנה עם שלושה מצבים כמחרוזות. צריך לשמור, מלבד המצב, מונה כישלונות רצופים וזמן הפתיחה. המלכודת: המעבר מ-`"open"` ל-`"half_open"` קורה **רק** בתוך `allow()`, ורק הקריאה הראשונה אחרי ה-cooldown מקבלת `True`.

### רמז 2: מבנה
1. `__init__`: לשמור את הפרמטרים, `state = "closed"`, מונה 0, וזמן פתיחה.
2. `allow()`: שלושה ענפים לפי המצב. ב-`"open"` בודקים אם עבר ה-cooldown לפי `self.clock()`.
3. `record_success()`: חזרה ל-`"closed"` ואיפוס המונה.
4. `record_failure()`: ב-`"half_open"` חוזרים ישר ל-`"open"` עם זמן פתיחה חדש; אחרת מגדילים את המונה ופותחים כשמגיעים לסף.

### רמז 3: האלגוריתם המלא
- `__init__(failure_threshold=3, cooldown_s=30.0, clock=time.monotonic)`: `self.failure_threshold`, `self.cooldown_s`, `self.clock`, `self.state = "closed"`, `self.failures = 0`, `self.opened_at = 0.0`.
- `allow()`:
  - `"closed"`: `True`.
  - `"open"`: אם `self.clock() - self.opened_at >= self.cooldown_s`, עוברים ל-`"half_open"` ומחזירים `True` (זו בקשת הניסיון היחידה). אחרת `False`.
  - `"half_open"`: `False` (הניסיון עדיין באוויר).
- `record_success()`: `state = "closed"`, `failures = 0`.
- `record_failure()`:
  - ב-`"half_open"`: `state = "open"`, `opened_at = self.clock()` (cooldown מלא חדש).
  - אחרת: `failures += 1`; אם `failures >= failure_threshold`: `state = "open"`, `opened_at = self.clock()`.
- קריאה של `state` לא משנה אותו.

## route_with_fallback

### רמז 1: כיוון
לולאה על רשימת ה-deployments, עם `try/except LLMError`. ההחלטה החשובה: איזו שגיאה אומרת "הספק בבעיה, נסה את הבא" ואיזו אומרת "הבקשה שלך שגויה, אין טעם לנסות אחר". `classify(err).retry` עונה על זה. המלכודת: לתפוס `Exception` כללית במקום רק `LLMError`.

### רמז 2: מבנה
1. רשימת `attempts` ריקה.
2. לכל `dep`: אם ה-breaker לא מרשה, רושמים דילוג וממשיכים.
3. `try` לקרוא ל-`call(dep)`. בהצלחה: מדווחים ל-breaker, רושמים, ומחזירים `RouteResult`.
4. ב-`except LLMError`: רושמים את השגיאה, ומחליטים לפי `classify` אם לדווח כישלון ולהמשיך, או לדווח הצלחה ולזרוק מחדש.
5. אחרי הלולאה: `AllDeploymentsFailed(attempts)`.

### רמז 3: האלגוריתם המלא
לכל `dep` ברשימה, עם `breaker = breakers[dep]`:
1. אם `breaker.allow()` הוא `False`: `attempts.append(Attempt(dep, "skipped_open"))` וממשיכים.
2. `value = call(dep)`. אם הצליח: `breaker.record_success()`, `attempts.append(Attempt(dep, "ok"))`, `return RouteResult(value, dep, attempts)`.
3. אם נזרקה `LLMError err`: `attempts.append(Attempt(dep, "error", err.status, err.message[:200]))`, ואז:
   - אם `classify(err).retry` הוא `True` (429, 5xx, 529, timeout): `breaker.record_failure()` וממשיכים ל-deployment הבא.
   - אחרת (400, 401, 404...): הבקשה היא הבעיה, והספק הבא ידחה אותה גם הוא. `breaker.record_success()` (הספק ענה, כלומר הוא חי) ו-`raise` מיד, בלי fallback.
4. כשהרשימה נגמרה (או הייתה ריקה): `raise AllDeploymentsFailed(attempts)`.
5. חריגות מסוג אחר לא נתפסות.

## israeli_id_valid

### רמז 1: כיוון
אלגוריתם ספרת ביקורת, קרוב ל-Luhn: משקלים מתחלפים, ומכפלה דו-ספרתית מתקפלת. המלכודת: לוודא קודם שזו בדיוק מחרוזת של 9 ספרות.

### רמז 2: מבנה
בדיקת פורמט (`re.fullmatch`), ואז לולאה על הספרות עם האינדקס כדי לבחור משקל, צבירת סכום, ובדיקת חלוקה ב-10.

### רמז 3: האלגוריתם המלא
1. אם `digits` אינה בדיוק 9 ספרות (`re.fullmatch(r"\d{9}", digits)`): `False`.
2. מכפילים את הספרות במשקלים `1,2,1,2,1,2,1,2,1` משמאל לימין (משקל 1 באינדקס זוגי, 2 באי-זוגי).
3. כשמכפלה גדולה מ-9, משתמשים ב-`product - 9` (שווה לסכום שתי הספרות שלה).
4. תקין כשהסכום מתחלק ב-10.

דוגמאות: `"123456782"` תקין, `"123456789"` לא, `"12345678"` לא (רק 8 ספרות).

## redact

### רמז 1: כיוון
הפרד בין שני שלבים: **למצוא** את כל הקטעים (spans) ולהחליט מי זוכה בכל אחד, ורק אחר כך **לבנות** את הטקסט החדש. אם תחליף תוך כדי חיפוש, ה-offsets יזוזו וה-findings יצביעו על מקומות שגויים. המלכודת השנייה: המספור צריך להמשיך את מה שכבר יש ב-`known`.

### רמז 2: מבנה
1. בדיקת השמות ב-`types`.
2. שלושה ביטויים רגולריים (אימייל, טלפון, ת"ז), ופונקציית נרמול לכל סוג.
3. מעבר על הסוגים **בסדר העדיפות הקבוע**, ולכל התאמה: אם היא חופפת לקטע שכבר נלקח, מדלגים; אחרת מוסיפים לרשימת הקטעים שנלקחו. לת"ז מסננים גם לפי ספרת ביקורת.
4. מיון הקטעים לפי מיקום.
5. לכל קטע: נרמול, חיפוש ב-`known`, ואם אין, יצירת placeholder חדש לפי מספר הערכים מאותו סוג שכבר ב-`known`. יצירת `Finding` עם fingerprint.
6. בניית הטקסט החדש מחלקים: טקסט עד הקטע, placeholder, וכן הלאה.

### רמז 3: האלגוריתם המלא
- **בדיקה:** כל שם ב-`types` שאינו `email`, `phone_il` או `il_id`: `ValueError`.
- **ביטויים:**
  - email: `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`.
  - phone_il: אופציונלית `+972` או `972` (שמחליפים את ה-0 המוביל) או `0` מוביל; אחר כך קידומת סלולרית `5X`, קידומת VoIP `7X`, או קוד אזור חד-ספרתי `2, 3, 4, 8, 9`; אחר כך 7 ספרות בתבנית 3+4. מקף אחד או רווח אחד מותרים בין הקבוצות. לא צמוד לספרה לפניו או אחריו. ביטוי אפשרי: `(?<![\d+])(?:\+972[-\s]?|972[-\s]?|0)(?:5\d|7\d|[23489])[-\s]?\d{3}[-\s]?\d{4}(?!\d)`. חייב להתאים ל: `054-1234567`, `0541234567`, `054-123-4567`, `+972-54-123-4567`, `+972 54 1234567`, `03-5550199`, `+972-3-555-0199`.
  - il_id: `(?<!\d)\d{9}(?!\d)`, ורק התאמות ש-`israeli_id_valid` מאשרת. תשע ספרות בלי ספרת ביקורת תקינה לא מוחלפות.
- **עדיפות:** עוברים על הסוגים בסדר `email`, `phone_il`, `il_id` (רק אלה שב-`types`), בלי קשר לסדר ש-`types` נתן. התאמה שחופפת (`start < e and s < end`) לקטע שכבר נלקח מדלגים עליה. דוגמה: `"035550199"` הוא גם טלפון קווי בתל אביב וגם 9 ספרות, וכטלפון הוא זוכה.
- **נרמול:** email באותיות קטנות; phone_il רק ספרות, ואם מתחיל ב-`972` מחליפים אותו ב-`0` (`"+972-54-123-4567"` שווה ל-`"0541234567"`); il_id כמו שהוא.
- **placeholder:** `known = {} if known is None else known`. לכל קטע לפי הסדר: `ph = known.get((kind, norm))`. אם אין: `n` = מספר המפתחות ב-`known` מאותו `kind`, ועוד 1; `ph = f"[{PREFIX}_{n}]"` עם `EMAIL`, `PHONE_IL`, `IL_ID`; ושומרים `known[(kind, norm)] = ph`. כך אותו ערך מקבל תמיד אותו placeholder, וה-gateway, שמעביר מילון אחד לכל ההודעות של בקשה, מקבל מספור אחד: `[EMAIL_1]` הוא אותו אדם בכל מקום.
- **findings:** `Finding(kind, ph, start, end, fingerprint)` לכל מופע, ממוינים לפי `start`, עם offsets בטקסט **המקורי**, ו-`fingerprint = hashlib.sha256((salt + norm).encode()).hexdigest()[:12]`. לעולם לא שמים את הערך הגולמי ב-Finding, כי ה-findings נכתבים ליומן הביקורת.
- **טקסט:** מחברים את הקטעים שבין ה-findings עם ה-placeholders, ומחזירים `Redaction(new_text, findings)`.

## decide

### רמז 1: כיוון
זו שרשרת בדיקות שכל אחת מהן יכולה לסיים מוקדם עם דחייה. `policy["rules"].get(c)` מחזיר את הכלל. המלכודת: רשימת היתר (allow-list) שלא מופיעה בכלל לא מגבילה כלום, ורשימה שמופיעה כן מגבילה.

### רמז 2: מבנה
שבע בדיקות בסדר קבוע, כל אחת עם `return` מוקדם: סיווג לא מוכר, אין כלל, דחייה גורפת, ואז שלוש רשימות היתר (אפשר בלולאה אחת על שלושה זוגות של שם שדה ותכונה של ה-deployment), ובסוף אישור.

### רמז 3: האלגוריתם המלא
בודקים בסדר הזה וחוזרים בהתאמה הראשונה (`c` הוא הסיווג):
1. `c` לא ב-`policy["classifications"]`: `PolicyDecision(False, "unknown_classification", <reason>)`.
2. אין ל-`c` רשומה ב-`policy["rules"]`: `(False, "no_rule", <reason>)`.
3. לכלל יש `deny: true`: `(False, f"{c}.deny", rule.get("reason") or <ברירת מחדל>)`.
4. יש `providers` ו-`deployment.provider` לא בה: `(False, f"{c}.providers", <reason>)`.
5. יש `models` ו-`deployment.model` לא בה: `(False, f"{c}.models", <reason>)`.
6. יש `regions` ו-`deployment.region` לא בה: `(False, f"{c}.regions", <reason>)`.
7. אחרת: `(True, f"{c}.allow", "")`.

ה-reason הוא טקסט חופשי לבני אדם; הטסטים בודקים רק שהוא לא ריק בדחיות.

## effective_classification

### רמז 1: כיוון
"גבוה יותר" כאן פירושו "מאוחר יותר ברשימה" `policy["classifications"]`, ולכן `list.index` נותן את הדרגה. המלכודת: לבדוק את תקינות הערכים אחרי שהחלפת ערך ריק בברירת המחדל.

### רמז 2: מבנה
1. החלפת ערך ריק או `None` בברירת המחדל.
2. בדיקה שהערך המבוקש והרצפה (אם יש) מוכרים.
3. השוואת דרגות והחזרת הגבוה מבין השניים.

### רמז 3: האלגוריתם המלא
1. `order = list(policy["classifications"])`.
2. `value = requested or policy.get("default_classification", "internal")` (ב-Acme: "מסמכים בלי תווית מטופלים כ-Internal").
3. לכל אחד מ-`value` ו-`floor` שאינו `None`: אם הוא לא ב-`order`, `ValueError`.
4. אם `floor` לא `None` ו-`order.index(floor) > order.index(value)`: מחזירים `floor`. אחרת `value`. כך אפליקציה שהמפתח שלה עם רצפה `"confidential"` לא יכולה לתייג את התעבורה שלה כ-`"public"`.

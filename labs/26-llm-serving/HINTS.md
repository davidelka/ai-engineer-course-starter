# רמזים למעבדה 26: LLM Serving

הקובץ הזה הוא למקרה שנתקעת. קודם נסה לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, סגור את הקובץ ונסה שוב. רק אם עדיין תקוע, עבור ל**רמז 2**, ורק בסוף ל**רמז 3**, שמכיל את האלגוריתם המלא. כל רמה כתובה כך שאפשר לעצור אחריה.

את המימושים המלאים (reference) תמצא ב-`servekit/ratelimit.py`, `servekit/gate.py` ו-`servekit/idempotency.py`. כדאי לפתוח אותם רק אחרי שהטסטים שלך עוברים, כדי להשוות.

## TokenBucket

(שתי מתודות: `__init__`, שבה צריך להשלים את המצב ההתחלתי, ו-`try_acquire`.)

### רמז 1: כיוון
אין צורך בטיימר או ב-thread שממלא את הדלי. מספיק לזכור **מתי עדכנת לאחרונה**, ובכל קריאה לחשב כמה אסימונים נוספו מאז. המלכודת: שעון שזז אחורה (הפרש שלילי) לא אמור להוריד אסימונים.

### רמז 2: מבנה
1. ב-`__init__`: שני שדות, רמת האסימונים הנוכחית וזמן העדכון האחרון.
2. מתודת עזר למילוי: מחשבת את הזמן שעבר (לא פחות מאפס), מוסיפה, חוסמת ב-`burst`, ומעדכנת את זמן העדכון.
3. ב-`try_acquire`: לקבוע את `now`, למלא, ואז שלושה מקרים: עלות שלעולם לא תצליח, יש מספיק, אין מספיק (ואז לחשב כמה זמן לחכות).

### רמז 3: האלגוריתם המלא
- `__init__`: `self.tokens = float(burst)` (דלי חדש מתחיל מלא), `self.updated = clock()`.
- מילוי עצלני: `elapsed = max(0.0, now - self.updated)`; `self.tokens = min(self.burst, self.tokens + elapsed * self.rate)`; `self.updated = now`.
- `try_acquire(cost=1.0, now=None)`:
  1. `now = self.clock() if now is None else now`, ומילוי.
  2. אם `cost > self.burst`: `(False, math.inf)`.
  3. אם `self.tokens >= cost`: `self.tokens -= cost` ו-`(True, 0.0)`.
  4. אחרת לא לוקחים כלום ומחזירים `(False, (cost - self.tokens) / self.rate)`.
- דוגמה: `rate=2`, `burst=3`. ב-t=0 שלוש קריאות עוברות, הרביעית מחזירה `(False, 0.5)`; ב-t=0.5 קריאה אחת עוברת שוב.

## ConcurrencyGate.retry_after

### רמז 1: כיוון
השאלה היא "כמה זמן עד שהתור שלפניי יתרוקן". יש לך את זמן השירות הממוצע של בקשה, מספר הממתינים ומספר המקומות שעובדים במקביל. המלכודת: התוצאה חייבת להיות `int` שלם ולפחות 1.

### רמז 2: מבנה
חשב כמה "סבבי שירות" צריך עד שיגיע תורך (הממתינים ועוד אתה, חלקי מספר המקומות), הכפל בזמן שירות ממוצע, עגל **למעלה**, וקח מקסימום עם 1.

### רמז 3: האלגוריתם המלא
`max(1, math.ceil(self._avg_service * (self.waiting + 1) / self.limit))`. דוגמה מהטסט: `_avg_service = 2.0`, `waiting = 7`, `limit = 4` נותנים `ceil(2.0 * 8 / 4) = 4`.

## ConcurrencyGate.acquire

### רמז 1: כיוון
`asyncio.Semaphore` מנהל את המקומות, ו-`asyncio.wait_for` נותן timeout. החלק העדין הוא המונים: `self.waiting` חייב לרדת בחזרה **בכל** תוצאה (הצלחה, timeout, ביטול), ולכן `try/finally` הוא הכלי. מלכודת נוספת: דחייה כשהתור מלא חייבת לקרות לפני כל `await`.

### רמז 2: מבנה
1. **מסלול מהיר:** אם אין ממתינים ויש מקום פנוי (`self._sem.locked()` אומר אם אין), לוקחים מקום, מעדכנים מונים וחוזרים.
2. **תור מלא:** אם מספר הממתינים כבר הגיע ל-`max_queue`, מעדכנים את מונה הדחיות וזורקים, בלי `await`.
3. **המתנה:** מגדילים את `waiting`, ובתוך `try` ממתינים לסמפור עם timeout. ב-`except` של timeout מעדכנים מונה וזורקים. ב-`finally` מקטינים את `waiting`.
4. אחרי המתנה מוצלחת: מעדכנים `active` ו-`admitted`.

### רמז 3: האלגוריתם המלא
1. אם `self.waiting == 0` ו-`not self._sem.locked()`: `await self._sem.acquire()`, `self.active += 1`, `self.admitted += 1`, `return`. (אל תעקוף את התור: אם מישהו ממתין, ממתינים מאחוריו.)
2. אחרת, אם `self.waiting >= self.max_queue`: `self.rejected["queue_full"] += 1` ו-`raise GateRejected("queue_full", self.retry_after())`. זה חייב לקרות בלי שום `await`: השלת עומס צריכה להיות מיידית.
3. אחרת: `self.waiting += 1`, ואז
   - `try: await asyncio.wait_for(self._sem.acquire(), timeout=self.queue_timeout)`
   - `except asyncio.TimeoutError: self.rejected["queue_timeout"] += 1; raise GateRejected("queue_timeout", self.retry_after())`
   - `finally: self.waiting -= 1`
4. בהצלחה: `self.active += 1`, `self.admitted += 1`.

## fingerprint

### רמז 1: כיוון
"JSON קנוני" פירושו שתי גרסאות של אותו מילון (סדר מפתחות שונה, רווחים שונים) הופכות לאותה מחרוזת בדיוק. `json.dumps` יודע לעשות את זה עם הפרמטרים הנכונים, ו-`hashlib.sha256` עושה את השאר.

### רמז 2: מבנה
שורה אחת: לסדר את ה-JSON בצורה קנונית, לקודד ל-UTF-8, לחשב sha256, ולהחזיר hex.

### רמז 3: האלגוריתם המלא
`hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()`.

## IdempotencyStore

(ארבע מתודות: `begin`, `complete`, `abandon`, `__len__`.)

### רמז 1: כיוון
המילון `self._d` כבר קיים. המפתח שלו צריך להיות הזוג `(scope, key)`, והערך רשומה קטנה (מילון או dataclass) עם fingerprint, זמן יצירה, האם הסתיים, ותשובה שמורה. המלכודת: רשומות שפג תוקפן חייבות להתנהג כאילו לא היו, גם ב-`begin` וגם ב-`__len__`.

### רמז 2: מבנה
1. מתודת עזר שמוחקת מ-`self._d` את כל הרשומות שגילן לפי `self.clock()` הגיע ל-`ttl`.
2. `begin`: ניקוי, חיפוש, ואז ארבעה מקרים בסדר: לא קיים (יוצרים), fingerprint שונה, עדיין רץ, הסתיים (מחזירים את התשובה השמורה).
3. `complete`: אם הרשומה קיימת, מסמנים שהסתיימה ושומרים status, תשובה וכותרות.
4. `abandon`: מוחקים את המפתח אם הוא קיים.
5. `__len__`: ניקוי ואז אורך המילון.

### רמז 3: האלגוריתם המלא
- ניקוי: `now = self.clock()`; מוחקים כל רשומה שבה `now - created >= self.ttl`.
- `begin(scope, key, fp)`:
  1. ניקוי; `e = self._d.get((scope, key))`.
  2. אם אין: `self._d[(scope, key)] = {"fp": fp, "created": now, "done": False, ...}` ו-`return Begin("new")`.
  3. אם `e["fp"] != fp`: `Begin("mismatch")` (ה-API עונה 422).
  4. אם לא `done`: `Begin("in_progress")` (ה-API עונה 409).
  5. אחרת: `Begin("replay", e["status"], e["response"], dict(e["headers"]))`.
- `complete(scope, key, status, response, headers=None)`: אם הרשומה קיימת, `done = True`, ושומרים `status`, `response`, `dict(headers or {})`. על מפתח לא מוכר לא עושים כלום.
- `abandon(scope, key)`: `self._d.pop((scope, key), None)`. (הניסיון הראשון נכשל בצורה ששווה לנסות שוב, כמו timeout או 5xx; שוכחים את המפתח כדי שהניסיון החוזר ירוץ במקום לשחזר שגיאה.)
- `__len__`: מספר הרשומות החיות (אחרי ניקוי).
- ה-scope הוא מזהה הלקוח: שני לקוחות יכולים לבחור את אותה מחרוזת מפתח.

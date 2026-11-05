# רמזים לפרויקט F3: סוכן המשרות

הקובץ הזה הוא למקרה שנתקעת. כדאי קודם לנסות לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, ונסה שוב. אם עדיין לא הולך, עבור ל-**רמז 2**, ורק בסוף ל-**רמז 3**, שמתאר את האלגוריתם המלא במילים. כל רמת רמז נמצאת תחת כותרת משלה, כך שאפשר לעצור אחרי כל אחת.

מימושי הייחוס נמצאים ב-`jobagent/` (`dedup.py`, `safety.py`, `match.py`, `schedule.py`). כדאי להשוות אליהם רק אחרי שהטסטים שלך עוברים (`python -m pytest -q projects/f3-job-agent/tests`).

## job_fingerprint

### רמז 1: כיוון
פונקציות הנרמול (`normalize_title`, `normalize_company`, `normalize_contact`, `normalize_location`) כבר עושות את כל העבודה הקשה, ו-`hashlib` מיובא. המלכודת: שדות שהם `None`, וחברה שמתנרמלת למחרוזת ריקה, שאז צריך ליפול לאיש הקשר.

### רמז 2: מבנה
חשב שלושה חלקים: כותרת, "מי" (חברה או, אם היא ריקה, איש קשר), ומיקום, כשכל `None` הופך ל-"". חבר אותם עם "|", קודד ל-bytes, חשב sha1, וקח את ההתחלה של ה-hex.

### רמז 3: האלגוריתם המלא
1. `WHO = normalize_company(job.company)`; אם הוא ריק, `WHO = normalize_contact(job.apply)` (בלי זה, כל "Backend Engineer" אנונימי בתל אביב היה מקבל אותו fingerprint).
2. שדות `None` מתנרמלים ל-"" (העבר `x or ""` לפונקציות הנרמול).
3. `key = normalize_title(job.title) + "|" + WHO + "|" + normalize_location(job.location)`.
4. `hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]`.

דוגמה: "Senior Back-End Developer" ב-"CyberDome Ltd." ב-"Beer Sheva", ו-"Developer, Senior Backend" ב-"cyberdome" ב-"beer sheva", מקבלים אותו fingerprint.

## near_duplicate

### רמז 1: כיוון
זה שלושה תנאים שכולם חייבים להתקיים, ולכן הכי פשוט להחזיר `False` מוקדם ברגע שאחד נכשל. `jaccard` מיובא. המלכודת: מילות בכירות ("Junior Rust Developer" מול "Rust Developer") שהדמיון בטוקנים לא תופס, וחברה לא ידועה, שם צריך לדרוש הרבה יותר מדמיון.

### רמז 2: מבנה
נרמל את הכותרות, המיקומים, החברות ואנשי הקשר של שתי המשרות. בדוק מיקום, אחר כך את קבוצות מילות הבכירות (חיתוך של טוקני הכותרת עם קבוצה קבועה), ואחר כך פצל לשני מקרים לפי החברות: שתיהן ידועות, או לפחות אחת לא ידועה.

### רמז 3: האלגוריתם המלא
1. **מיקומים**: שווים אחרי `normalize_location`, או שלפחות אחד מהם לא ידוע (`None`/"").
2. **מילות בכירות**: הקבוצות של המילים `{junior, senior, lead, principal, staff, mid, head}` שנמצאות בשתי הכותרות המנורמלות חייבות להיות שוות ("Junior Rust Developer" **אינו** "Rust Developer").
3. **חברות** (`normalize_company`):
   - שתיהן ידועות: חייבות להיות שוות, **וגם** `jaccard(title tokens) >= title_threshold`.
   - לפחות אחת לא ידועה: הכותרות המנורמלות חייבות להיות זהות (ולא ריקות), **וגם** אם לשתי המשרות יש איש קשר (apply), אנשי הקשר חייבים להיות שווים (`normalize_contact`). שתי משרות שונות של "Backend Engineer" בתל אביב עם חברה לא ידועה אינן אותה משרה.
4. טוקני כותרת = `set(normalize_title(title).split())`. התוצאה צריכה להיות סימטרית: `near_duplicate(a, b) == near_duplicate(b, a)`.

## validate_job

### רמז 1: כיוון
כל העזרים מוכנים: `unmark`, `appears_in`, `number_in_text`, `EMAIL_RE`, `URL_RE`. התייחס לכל שדה כאל קלט עוין. המלכודת: סדר הבדיקות של `apply`, כי ערך עם סכמה רעה צריך לקבל את ה-finding של הסכמה, ולא גם את זה של המקור.

### רמז 2: מבנה
צור עותק עמוק, ונקה את ארבעת שדות הטקסט מתו הסימון. אחר כך טפל ב-`apply` (הסרת "mailto:", בדיקת סכמה, ורק אם עברה, בדיקה מול המקור), אחר כך בשנות הניסיון, אחר כך בקישורים בתוך הכותרת והחברה (לולאה על שני השדות), ולבסוף באורך הכותרת.

### רמז 3: האלגוריתם המלא
עבוד על עותק עמוק (`job.model_copy(deep=True)`); אל תשנה את `job`. ה-`detail` הוא טקסט חופשי (הערך או שם השדה); הטסטים בודקים `code` ו-`severity`.
1. קודם הפעל `unmark()` על title, company, location ו-apply (מודלים לפעמים מעתיקים את תו ה-datamark מה-prompt עם ה-spotlighting).
2. **apply**: אם יש "mailto:" בהתחלה, הסר אותו (גם בערך המנוקה).
   - `apply_bad_scheme` (block): apply אינו מייל (`EMAIL_RE.fullmatch`) ואינו URL שמתחיל ב-`http://` או `https://`. ‏apply הופך ל-`None`. בדוק את הסכמה **לפני** בדיקת המקור.
   - `apply_not_in_source` (block): apply קיים אבל לא מופיע ב-`source_text`. השתמש ב-`appears_in(needle, haystack)`: לא תלוי רישיות, רווחים מנורמלים, "/" או "." בסוף לא נחשבים. ‏apply הופך ל-`None`.
3. `years_not_in_source` (warn): `years_required` קיים אבל `number_in_text(years, source_text)` הוא `False` (ספרות, או מילה עברית כמו "שנתיים"). ‏`years_required = None`.
4. `link_in_text_field` (block): title או company מכילים URL או מייל (`URL_RE` / `EMAIL_RE`). חתוך את השדה בקישור הראשון, ועשה strip לתווים `" -:|,"`. אם לא נשאר כלום: company הופך ל-`None`, ו-title הופך ל-"(unknown title)".
5. `title_too_long` (warn): ‏`len(title) > 120`. חתוך ל-120 תווים (ואז `rstrip`).

## score_job

### רמז 1: כיוון
זו הפונקציה הגדולה בפרויקט, ולכן כדאי לפרק אותה לשלוש פונקציות עזר, אחת לכל רכיב ציון, שכל אחת מחזירה נקודות ושורת הסבר. כל מספר בא מ-`prefs` (פתח את `data/preferences.yaml` ואת `jobagent/prefs.py` כדי לראות את השמות). המלכודת: לקודד מספרים ישירות, ולשכוח שגם `None` הוא ערך חוקי של work_mode ברשימת ה-modes.

### רמז 2: מבנה
קטגוריה: עבור על הקטגוריות של המשרה, סנן לפי ביטחון ולפי `prefs.targets`, חשב לכל אחת נקודות, ובחר את הטובה (עם שובר שוויון לפי סדר המפתחות ב-targets). מיקום: מצא אזור, ואז חפש את הכלל הראשון שמתאים. ניסיון: חשב ציון בכירות וציון שנים וקח את המינימום. אחר כך חבר, קבע tier, טפל ב-`suspicious`, ובנה את ה-dict עם השורות.

### רמז 3: האלגוריתם המלא
`score = category (0-50) + location (0-30) + experience (0-20)`. קרא כל מספר מ-`prefs`; לעולם אל תקודד את הקריטריונים של דוד.

**קטגוריה** (רק קטגוריות עם `confidence >= 0.5` שנמצאות ב-`prefs.targets`):
1. automation, כאשר `targets["automation"].prefer_hardware` והמשרה **לא** `hardware_oriented`: ‏`targets["automation"].web_score` נקודות.
2. אחרת: 50.
3. קטגוריה שאינה `p.primary_category`: לכל היותר `prefs.secondary_points` (כלומר `min(points, prefs.secondary_points)`).
4. קח את הטובה; בשוויון העדף את המפתח המוקדם יותר ב-`prefs.targets`. אין target מתאים: 0 נקודות, category `None`.

**מיקום**: `region = region_of(p.location)`, `mode = p.work_mode`.
1. region `None`: ‏30 אם `mode == "remote"`, אחרת `prefs.location.unknown_location_points`.
2. אחרת: הכלל **הראשון** ב-`prefs.location.rules` שה-region שלו הוא `region` או "any", ושרשימת ה-modes שלו מכילה את `mode` (`None` הוא ערך חוקי ברשימה: "המצב לא צוין"). הנקודות הן `rule.points`.
3. אף כלל לא התאים: `prefs.location.default_points`.

**ניסיון** (`e = prefs.experience`; `accepted = targets[category].accept_seniority`, או `["mid", "senior"]` כשאין קטגוריה):
1. נקודות בכירות: junior שאינו ב-accepted נותן `e.junior_points`; lead שאינו ב-accepted נותן `e.lead_points`; אחרת 20.
2. נקודות שנים: `None` או `<= e.ok_up_to_years` נותן 20; `<= e.stretch_up_to_years` נותן `e.stretch_points`; יותר מזה 0.
3. `experience = min(seniority points, years points)`.

**Tier**:
1. "match" אם `score >= prefs.thresholds.match` **וגם** נקודות הקטגוריה שוות ל-50.
2. "maybe" אם `score >= prefs.thresholds.maybe` **וגם** נקודות הקטגוריה גדולות מ-0.
3. אחרת "skip".
4. `suspicious=True` הופך "match" ל-"maybe" (ומוסיף שורת סיבה).

**cv**: `prefs.targets[category].cv` כשיש קטגוריה, אחרת `None`.

**reasons**: לפחות שורה עברית אחת לכל רכיב, כל אחת עם `"<points>/<max>"`, למשל `"[כלל] Beer Sheva (דרום, היברידי): 30/30"`. הקידומת היא "[מודל]" כשהשורה תלויה בשיפוט של מודל (קטגוריה, hardware_oriented, מילת בכירות), ו-"[כלל]" אחרת.

## due_slot

### רמז 1: כיוון
`latest_slot(now)` ו-`slot_key(dt)` כבר מיובאים מ-`jobagent.schedule` ועושים את רוב העבודה, כולל המעבר ליום הקודם. המלכודת: אזורי זמן ושעון קיץ. השווה תמיד datetime "מודעים" (aware), או המר עם `.astimezone(TZ)`.

### רמז 2: מבנה
שלושה צעדים: מצא את ה-slot המועמד, הפוך אותו למפתח, ואז שתי בדיקות שמחזירות `None`: כבר רץ, או מאוחר מדי. אחרת החזר את המפתח.

### רמז 3: האלגוריתם המלא
1. ה-slots הם 08:30, 15:00, 21:00 בשעון Asia/Jerusalem.
2. `candidate = latest_slot(now)`: זמן ה-slot האחרון שהוא `<= now` (לפני 08:30 זה ה-21:00 של אתמול). ‏`slot_key(candidate)` הופך אותו למחרוזת כמו "2026-11-01T08:30".
3. אם המפתח נמצא ב-`done`: ‏`None` (כבר רץ: ניסיון חוזר או טריגר כפול).
4. אם `now - candidate > max_late`: ‏`None` (מאוחר מדי מכדי להועיל; ה-slot הבא יכסה את הפוסטים).
5. אחרת החזר את המפתח. `now` יכול להיות בכל אזור זמן (השווה datetime מודעים, או המר עם `.astimezone(TZ)`).

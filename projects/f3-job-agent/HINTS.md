# רמזים לפרויקט F3: סוכן המשרות

הקובץ הזה הוא למקרה שנתקעת. כדאי קודם לנסות לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, ונסה שוב. אם עדיין לא הולך, עבור ל-**רמז 2**, ורק בסוף ל-**רמז 3**, שמתאר את האלגוריתם המלא במילים. כל רמת רמז נמצאת תחת כותרת משלה, כך שאפשר לעצור אחרי כל אחת.

מימושי הייחוס נמצאים רק ב-branch בשם `solutions` של הריפו, בקובץ `jobagent/_reference.py`. כדאי להשוות אליהם רק אחרי שהטסטים שלך עוברים (`python -m pytest -q projects/f3-job-agent/tests`).

## find_repost

### רמז 1: כיוון
הפונקציה `shingles(text)` מ-`jobagent.dedup` כבר מפרקת טקסט לקבוצה של רצפים של חמישה תווים (אחרי הסרת אימוג'י וסימנים), ו-`jaccard` מחשבת דמיון בין שתי קבוצות. נשאר רק לעבור על הפוסטים הקודמים ולזכור את הדומה ביותר. המלכודת: להחזיר את הראשון שעובר את הסף, במקום את הדומה ביותר.

### רמז 2: מבנה
חשב את ה-shingles של `text` פעם אחת, לפני הלולאה. בלולאה על הזוגות `(key, other)` חשב דמיון, ושמור את הדמיון הגבוה ביותר ואת המפתח שלו. אחרי הלולאה בדוק את הסף פעם אחת.

### רמז 3: האלגוריתם המלא
1. `sh = shingles(text)`; `best, best_key = 0.0, None`.
2. לכל `(key, other)` ב-`previous`: ‏`sim = jaccard(sh, shingles(other))`; אם `sim > best`, עדכן את `best` ואת `best_key`.
3. החזר `best_key` אם `best >= threshold`, אחרת `None`. כשאין פוסטים קודמים, `best` נשאר 0 ומוחזר `None`.

הערה למחשבה: זו השוואה של כל פוסט מול כל הפוסטים הקודמים, וזה בסדר למאות פוסטים ביום. במיליוני פוסטים משתמשים ב-MinHash עם LSH (למשל הספרייה datasketch), שמוצאים מועמדים בלי להשוות הכול.

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

## screen_post

### רמז 1: כיוון
ה-detector של guardkit מהשיעור על אבטחה כבר מוכן: `_detector = HeuristicDetector("balanced")`, ו-`_detector.detect(text, kind="document")` מחזיר `Verdict(flagged, score, reasons)`. את שני הסימנים המבניים תופסים שני ביטויים רגולריים שכבר מיובאים: `FORGED_MARKER` ו-`SYSTEM_LINE`. המלכודת: `text` יכול להיות `None`.

### רמז 2: מבנה
הרץ את ה-detector, ואחר כך בנה רשימה של שמות הסימנים שהתאימו, בסדר קבוע. אם הרשימה ריקה, החזר את ה-Verdict של ה-detector כמו שהוא. אחרת בנה Verdict חדש.

### רמז 3: האלגוריתם המלא
1. `v = _detector.detect(text, kind="document")`.
2. `extra = []`; אם `FORGED_MARKER.search(text or "")`, הוסף `"forged_post_marker"`; אם `SYSTEM_LINE.search(text or "")`, הוסף `"system_line"` (בסדר הזה).
3. אם `extra` ריקה: החזר `v`.
4. אחרת: `Verdict(True, v.score + 3.0 * len(extra), v.reasons + extra)`.

למה שני הסימנים האלה: פוסט שמכיל `<</post ...>>` מנסה "לסגור" את הסימון שלנו ולכתוב טקסט שייראה כאילו הוא מחוץ לפוסט, ושורה שמתחילה ב-`SYSTEM:` מנסה להתחזות להוראת מערכת. שניהם לא מופיעים במודעת דרושים אמיתית.

## spotlight

### רמז 1: כיוון
שלושה דברים: nonce, החלפת רווחים בתו הסימון `DATAMARK`, ועטיפה בסימונים עם ה-nonce. `secrets` ו-`re` מיובאים. המלכודת: להחליף גם את ירידות השורה, ואז המודל מקבל גוש טקסט אחד.

### רמז 2: מבנה
השתמש ב-nonce שקיבלת או צור חדש. החלף כל רצף של רווחים וטאבים (ולא ירידות שורה) בביטוי רגולרי אחד. הרכב את המחרוזת עם f-string, והחזר זוג.

### רמז 3: האלגוריתם המלא
1. `nonce = nonce or secrets.token_hex(4)` (שמונה תווי hex).
2. `marked = re.sub(r"[ \t]+", DATAMARK, text)`.
3. `wrapped = f"<<post nonce={nonce}>>\n{marked}\n<</post nonce={nonce}>>"`.
4. החזר `(wrapped, nonce)`.

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

## extract_post

### רמז 1: כיוון
את כל העבודה הקשה עושה `complete_structured` מ-`llmkit.structured` (השיעור על Structured Outputs): היא שולחת, מאמתת מול ה-schema של `PostExtraction`, ומבקשת תיקון כשהתשובה לא תקינה. הפונקציה שלך בונה את הבקשה, מודדת זמן, ותופסת את `StructuredError`. המלכודת: להחזיר חצי משרה, או לזרוק חריגה, כשהמודל נכשל. כאן נכשלים "סגור": אין משרות.

### רמז 2: מבנה
ייבא בתוך הפונקציה את `StructuredError` ו-`complete_structured`, ואת `Block`, `ChatRequest` ו-`Message` מ-`llmkit.types`. שמור `t0 = time.perf_counter()`. בתוך try: בנה את ה-prompt (ChatRequest עם system שמור במטמון, או מחרוזת), קרא ל-`complete_structured`, והחזר `ExtractResult` מהתוצאה. ב-except: החזר `ExtractResult` ריק עם `error`.

### רמז 3: האלגוריתם המלא
1. `t0 = time.perf_counter()`.
2. אם `cache_system and mode == "native"`: ‏`prompt = ChatRequest(messages=[Message("user", build_user_prompt(post))], system=[Block(SYSTEM_PROMPT, cache="5m")], max_tokens=max_tokens)`. אחרת `prompt = build_user_prompt(post)`.
3. `r = complete_structured(llm, prompt, PostExtraction, system=SYSTEM_PROMPT, mode=mode, max_tokens=max_tokens, max_repairs=max_repairs)`.
4. החזר `ExtractResult(r.value, r.cost_usd, r.input_tokens, r.output_tokens, r.attempts, time.perf_counter() - t0, extractor=name)`.
5. `except StructuredError as exc`: ‏`res = exc.result`, והחזר `ExtractResult(PostExtraction(is_job_post=False, jobs=[]), getattr(res, "cost_usd", 0.0) or 0.0, getattr(res, "input_tokens", 0), getattr(res, "output_tokens", 0), getattr(res, "attempts", 1), time.perf_counter() - t0, error=f"structured_{exc.stage}", extractor=name)`.

למה המטמון: ה-system prompt זהה בכל פוסט ובא ראשון, ולכן נקודת cache אחריו מאפשרת לפוסט השני עד האחרון בריצה לקרוא אותו בעשירית מהמחיר.

## score_job

### רמז 1: כיוון
זו הפונקציה הגדולה בפרויקט, ולכן כדאי לפרק אותה לשלוש פונקציות עזר, אחת לכל רכיב ציון, שכל אחת מחזירה נקודות ושורת הסבר. כל מספר בא מ-`prefs` (פתח את `data/preferences.yaml` ואת `jobagent/prefs.py` כדי לראות את השמות). המלכודת: לקודד מספרים ישירות, ולשכוח שגם `None` הוא ערך חוקי של work_mode ברשימת ה-modes.

### רמז 2: מבנה
קטגוריה: עבור על הקטגוריות של המשרה, סנן לפי ביטחון ולפי `prefs.targets`, חשב לכל אחת נקודות, ובחר את הטובה (עם שובר שוויון לפי סדר המפתחות ב-targets). מיקום: מצא אזור, ואז חפש את הכלל הראשון שמתאים. ניסיון: חשב ציון בכירות וציון שנים וקח את המינימום. אחר כך חבר, קבע tier, טפל ב-`suspicious`, ובנה את ה-dict עם השורות.

### רמז 3: האלגוריתם המלא
`score = category (0-50) + location (0-30) + experience (0-20)`. קרא כל מספר מ-`prefs`; לעולם אל תקודד את הקריטריונים של מחפש העבודה שבדוגמה.

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

## align

### רמז 1: כיוון
זו בעיית שיבוץ קטנה: לכל משרה מתויגת (gold) צריך למצוא את המשרה החזויה שמתאימה לה, כשכל חזויה משמשת פעם אחת. הגישה החמדנית מספיקה כאן: מחשבים דמיון לכל זוג, וממיינים מהגבוה לנמוך. המלכודת: לעבור על ה-gold לפי הסדר ולתת לכל אחת את הטובה ביותר שנשארה, כי אז משרה מוקדמת "גונבת" התאמה טובה יותר של משרה מאוחרת.

### רמז 2: מבנה
בנה רשימה של שלשות `(similarity, gold_index, pred_index)` לכל הזוגות. מיין אותה בסדר יורד. עבור עליה, ושמור שתי קבוצות של אינדקסים שכבר נלקחו. התוצאה היא רשימה באורך `len(golds)`, שמתחילה כ-`None` בכל מקום.

### רמז 3: האלגוריתם המלא
1. `out = [None] * len(golds)`.
2. לכל `gi, g` ולכל `pi, p`: ‏`gt = set(normalize_title(g["title"]).split())`, ‏`pt = set(normalize_title(p.title).split())`, ‏`bonus = 0.2 if p.primary_category == g["primary_category"] else 0.0`, והוסף `(jaccard(gt, pt) + bonus, gi, pi)`.
3. `for sim, gi, pi in sorted(pairs, reverse=True)`: אם `gi` או `pi` כבר נלקחו, דלג; אחרת `out[gi] = preds[pi]` וסמן את שניהם.
4. החזר `out`.

## relevance

### רמז 1: כיוון
`prf(tp, fp, fn)` מ-`jobagent.evaluate` כבר מחשב precision, recall ו-f1. צריך רק לספור tp, fp ו-fn פעמיים, פעם לכל הגדרה של "חיובי". המלכודת: לשכוח שב-"shown" גם "maybe" נחשב חיובי.

### רמז 2: מבנה
לולאה על שתי הגדרות: `("match", {"match"})` ו-`("shown", {"match", "maybe"})`. בכל אחת עבור על `zip(pred_tiers, gold_tiers)` וספור. בסוף הוסף את `tier_accuracy`.

### רמז 3: האלגוריתם המלא
1. לכל `(name, pos)`: ‏`tp` = מספר המקומות שבהם `p in pos and g in pos`; ‏`fp` = ‏`p in pos and g not in pos`; ‏`fn` = ‏`p not in pos and g in pos`. ‏`out[name] = prf(tp, fp, fn)`.
2. `out["tier_accuracy"] = sum(p == g for p, g in zip(pred_tiers, gold_tiers)) / max(1, len(gold_tiers))`.
3. החזר `out`.

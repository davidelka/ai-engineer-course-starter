# רמזים לשיעור 3

**איך להשתמש בקובץ הזה.** קודם נסה לבד, רק לפי ה-docstring ב-`mine.py` והבדיקות בתיקייה `tests/`. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, וחזור לנסות. אם עדיין לא הולך, קרא את **רמז 2**, ונסה שוב. **רמז 3** מתאר את האלגוריתם המלא במילים; השאר אותו למקרה שבאמת אין דרך אחרת, ואחריו כתוב את הקוד בעצמך. כל רמז נמצא תחת כותרת משלו, כך שאפשר לעצור אחרי כל אחד.

המימושים של הקורס ל-`extract_json` ול-`format_errors` נמצאים ב-`llmkit/structured.py`. כדאי להשוות אליהם רק אחרי שהבדיקות שלך עוברות. הסכמה `AccessRequest` שממנה יורשים בתרגיל 5 נמצאת ב-`labs/03-structured-outputs/acme_schema.py`.

בדיקה: `python -m pytest -q labs/03-structured-outputs/tests`

## extract_json

### רמז 1: כיוון

ביטוי רגולרי פשוט כמו `\{.*\}` לא יעבוד: הוא לא יודע איפה האובייקט נגמר כשיש אובייקטים מקוננים, שני אובייקטים בתשובה, או סוגריים מסולסלים **בתוך מחרוזת** (`"use {x} here"`). צריך לעבור על הטקסט תו אחר תו ולספור עומק, ולזכור בכל רגע אם אתה בתוך מחרוזת. המלכודת השנייה: מרכאה עם backslash לפניה (`\"`) לא סוגרת את המחרוזת.

### רמז 2: מבנה

שלושה שלבים. ראשית, אם יש בטקסט בלוק markdown מגודר (שלוש backticks, עם או בלי המילה `json`), המשך רק עם התוכן שבתוכו. שנית, מצא את ה-`{` הראשון; אם אין, זו שגיאה. שלישית, לולאה מהמקום הזה עם שלושה משתני מצב: עומק (מונה), "אני בתוך מחרוזת" (בוליאני), ו"התו הקודם היה backslash" (בוליאני). כשהעומק חוזר לאפס, החזר את החתיכה מה-`{` ועד התו הנוכחי כולל. אם הלולאה נגמרה בלי שהעומק חזר לאפס, האובייקט לא נסגר.

### רמז 3: האלגוריתם המלא

1. גדר markdown: חפש עם `re.search` (עם הדגל `re.S`, כדי ש-`.` יתאים גם לשורה חדשה) את התבנית `` ```(?:json|JSON)?\s*\n?(.*?)``` ``. אם נמצאה, החלף את הטקסט בקבוצה 1.
2. `start = text.find("{")`. אם `start < 0`: `raise ValueError("no JSON object found in the reply")`. כך גם `"[1, 2, 3]"` ומחרוזת ריקה זורקים, כי מערך אינו אובייקט.
3. אתחל `depth = 0`, `in_str = False`, `esc = False`, ועבור על האינדקסים מ-`start` עד סוף הטקסט:
   - אם `in_str`: אם `esc` אמת, אפס אותו (התו הזה "נבלע"). אחרת, אם התו הוא `\`, הדלק `esc`. אחרת, אם התו הוא `"`, צא מהמחרוזת (`in_str = False`). סוגריים בתוך מחרוזת לא נספרים.
   - אחרת (מחוץ למחרוזת): `"` מכניס למחרוזת; `{` מגדיל את `depth` באחד; `}` מקטין באחד, ואם `depth` הגיע ל-0, החזר `text[start:i + 1]`.
4. אם הלולאה הסתיימה: `raise ValueError("JSON object is not closed (truncated reply?)")`.

בגלל שמחזירים ברגע שהעומק חוזר לאפס, בטקסט `Result: {"a": 1} and also {"b": 2}` מוחזר האובייקט הראשון בלבד.

## format_errors

### רמז 1: כיוון

ל-`ValidationError` של pydantic יש מתודה `exc.errors()` שמחזירה רשימה של מילונים, אחד לכל שגיאה, עם המפתחות `"loc"` (tuple של חלקי הנתיב לשדה), `"msg"` (ההודעה) ו-`"input"` (הערך שהתקבל). כל העבודה היא לעצב אותם. המלכודות: הערך שהתקבל יכול להיות ארוך מאוד או לא ניתן ל-JSON, ו-`exc.error_count()` נותן את המספר הכולל כדי לחשב כמה שגיאות נשארו.

### רמז 2: מבנה

בדוק קודם עם `isinstance` אם זו `ValidationError`. אם לא, החזר שורה אחת קבועה עם טקסט החריגה. אם כן, עבור על לכל היותר `max_errors` השגיאות הראשונות; לכל אחת בנה את הנתיב (חיבור חלקי `loc` בנקודות), את הערך כ-JSON, קצר אותו אם צריך, והרכב את השורה. בסוף, אם היו יותר שגיאות מהמקסימום, הוסף שורת "ועוד N". חבר הכול בשורות חדשות.

### רמז 3: האלגוריתם המלא

1. אם `isinstance(exc, ValidationError)`:
   1. לכל `e` ב-`exc.errors()[:max_errors]`:
      - `loc = ".".join(str(p) for p in e["loc"])`; אם יצא ריק, השתמש ב-`"(root)"`. (`str` כי חלק מהנתיב יכול להיות אינדקס מספרי.)
      - `got = json.dumps(e.get("input"), ensure_ascii=False, default=str)`. `ensure_ascii=False` שומר עברית קריאה, ו-`default=str` מונע קריסה על ערכים שאינם JSON.
      - אם `len(got) > 60`: `got = got[:57] + "..."`, כך שהאורך הוא בדיוק 60.
      - השורה: `f"- {loc}: {e['msg']} (got {got})"`.
   2. `extra = exc.error_count() - max_errors`. אם `extra > 0`, הוסף שורה `f"- ... and {extra} more errors"`.
   3. החזר את השורות מחוברות ב-`"\n"`.
2. אחרת: החזר `f"- the reply is not valid JSON: {exc}"`.

## MyAccessRequest

### רמז 1: כיוון

ב-pydantic v2 יש שני סוגי validators: `@field_validator` לשדה בודד, ו-`@model_validator` לכלל שמערב כמה שדות. המלכודת החשובה בכלל 1: לשדה `requester_email` יש `pattern` שלא מרשה רווחים. validator שרץ **אחרי** הבדיקה הרגילה לא יספיק לנקות את הרווחים, כי הבדיקה תיכשל לפניו. חשוב מתי ה-validator שלך צריך לרוץ.

### רמז 2: מבנה

שני validators בתוך המחלקה. הראשון הוא `field_validator` על `requester_email` שרץ **לפני** הבדיקה הרגילה (`mode="before"`), מקבל את הערך הגולמי, ומחזיר אותו מנוקה, או `None` כמו שהוא. השני הוא `model_validator(mode="after")` שרואה את האובייקט המלא: קודם בודק את כלל 2 (מה מחייב `needs_security`), אחר כך את כלל 3, וזורק `ValueError` עם הודעה ברורה. בסוף הוא מחזיר `self`. pydantic הופך את ה-`ValueError` ל-`ValidationError`.

### רמז 3: האלגוריתם המלא

1. כלל 1: `@field_validator("requester_email", mode="before")` מעל `@classmethod` עם חתימה `(cls, v)`. אם `v` הוא מחרוזת, החזר `v.strip().lower()`; אחרת (למשל `None`) החזר את `v` כמו שהוא. כך `"  YAEL.BAR@ACME.EXAMPLE "` הופך ל-`"yael.bar@acme.example"` ורק אז נבדק מול ה-`pattern`.
2. `@model_validator(mode="after")` על מתודה רגילה `(self)`:
   1. אסוף את הסיבות לאבטחה: `access_level == "admin"`, `production`, `customer_data`, `financial_data`, `external_sharing`. למשל רשימה של מחרוזות כמו `"access_level is admin"` או `"production is true"`.
   2. כלל 2, נבדק **ראשון**: אם יש לפחות סיבה אחת ו-`self.route != "needs_security"`, זרוק `ValueError(f"route must be needs_security because {reason}")`. ההודעה חייבת להכיל `needs_security`; הבדיקות בודקות את זה גם כשגם כלל 3 שבור (למשל `admin` עם `auto_approve`), ולכן כלל 2 חייב לבוא לפני כלל 3.
   3. כלל 3: אם `self.route == "auto_approve"` ו-`self.access_level` אינו `"read"` או `"standard"`, זרוק `ValueError` עם הודעה כמו `"auto_approve is only allowed for read or standard access"`.
   4. החזר `self`.

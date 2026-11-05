# רמזים לשיעור 20: Design-Driven Development

הקובץ הזה הוא עזרה מדורגת לקוד ב-`mine.py`. קודם כול נסה לבד, רק לפי ה-docstring (החוזה) ולפי הטסטים. אם נתקעת, קרא את **רמז 1** בלבד ונסה שוב. אם עדיין לא הולך, עבור ל**רמז 2**, ורק בסוף ל**רמז 3**, שמכיל את האלגוריתם המלא. אפשר לעצור אחרי כל רמה.

בשיעור הזה רוב העבודה היא מחלקות ולא פונקציות בודדות, ולכן יש כאן סעיף לכל מחלקה, והוא מכסה את כל המתודות שלה.

מימושי הייחוס נמצאים ב-`designkit/ports.py`, `designkit/fakes.py`, `designkit/service.py`, `designkit/contract.py` ו-`designkit/registry.py`. כדאי להשוות אליהם רק אחרי שהטסטים שלך עוברים.

## ChatModel

### רמז 1: כיוון

port הוא רק הצהרה: מה צריך להיות לאובייקט כדי שייחשב ChatModel. `typing.Protocol` עם `@runtime_checkable` מאפשר ל-`isinstance` לבדוק את זה מבנית, בלי ירושה. המלכודת: גם `name: str` הוא חלק מהממשק, וצריך להצהיר עליו כ-annotation.

### רמז 2: מבנה

בגוף המחלקה, מתחת ל-docstring: שורת annotation אחת לשדה, והגדרת מתודה אחת עם החתימה המדויקת וגוף של `...`. ההבטחות ההתנהגותיות כבר כתובות ב-docstring, ושם הן נשארות.

### רמז 3: האלגוריתם המלא

- `name: str` (למשל `"anthropic:claude-haiku-5-5"`).
- `def complete(self, system: str, prompt: str, *, max_tokens: int = 512) -> Completion: ...`
- ההבטחות (ב-docstring): הטקסט לא ריק; המתודה זורקת `ModelUnavailable` (זמני) או `ModelRejected` (קבוע), ואף פעם לא exception של ספק או של התעבורה.

הטסטים בודקים שהפרמטרים הראשונים הם `self, system, prompt`, ש-`max_tokens` קיים עם ברירת מחדל 512, ש-`name` מופיע ב-`__annotations__`, ושאובייקט שאין לו את המתודה **לא** עובר `isinstance`.

## Retriever

### רמז 1: כיוון

אותו רעיון כמו `ChatModel`: Protocol עם מתודה אחת. החתימה צריכה להיות מדויקת, כולל ברירת המחדל של `k`.

### רמז 2: מבנה

הגדרת מתודה אחת עם גוף `...`. ההבטחות נשארות ב-docstring.

### רמז 3: האלגוריתם המלא

- `def search(self, query: str, k: int = 4) -> list[Passage]: ...`
- הפרמטרים חייבים להיות בדיוק `self, query, k`, ו-`k` עם ברירת מחדל 4.
- ההבטחות: לכל היותר k תוצאות, הציון הגבוה ראשון, doc_ids ייחודיים, `[]` כשאין התאמה (בלי exception), דטרמיניסטי; `RetrieverUnavailable` כשהשירות למטה.

## AnswerStore

### רמז 1: כיוון

Protocol עם שתי מתודות. שים לב שהחוזה של `put` מחזיר `bool`, והמשמעות שלו היא "האם אני זה ששמרתי".

### רמז 2: מבנה

שתי הגדרות מתודה עם גוף `...`.

### רמז 3: האלגוריתם המלא

- `def get(self, request_id: str) -> Optional[Answer]: ...`
- `def put(self, answer: Answer) -> bool: ...`
- ההבטחות: `put` שומר רק אם ה-id לא קיים ומחזיר `True`; אם ה-id כבר קיים הוא מחזיר `False` ו**לא** דורס (הכתיבה הראשונה מנצחת).

## Clock

### רמז 1: כיוון

ה-port הכי קטן: מתודה אחת. הוא קיים כדי שאפשר יהיה להזריק זמן קבוע בטסטים.

### רמז 2: מבנה

הגדרת מתודה אחת עם גוף `...`.

### רמז 3: האלגוריתם המלא

- `def now(self) -> datetime: ...`, שמחזירה datetime עם timezone (aware).

## FakeChatModel

### רמז 1: כיוון

fake הוא לא mock: יש לו התנהגות אמיתית וצפויה. המלכודות: הקריאה נרשמת ב-`self.calls` **לפני** שהמודל נכשל, ערך לא חוקי של `fail` נדחה כבר ב-`__init__`, ורשימת תשובות ממשיכה להחזיר את האחרונה אחרי שנגמרה.

### רמז 2: מבנה

ב-`__init__`: ולידציה של `fail`, שמירה של הפרמטרים, ורשימת `calls` ריקה. ב-`complete`: קודם רישום הקריאה, אחר כך שני מקרי הכישלון, ואז בחירת הטקסט לפי סוג ה-reply (callable, רשימה, מחרוזת, או None). ל-None צריך regex שמוצא את ה-id של המסמך הראשון בפרומפט. בסוף בונים `Completion`.

### רמז 3: האלגוריתם המלא

`__init__(self, reply=None, *, fail=None, name="fake:chat")`:

1. אם `fail` אינו `None`, `"unavailable"` או `"rejected"`, זורקים `ValueError`.
2. שומרים את `reply`, `fail`, `name`, ו-`self.calls = []`.

`complete(self, system, prompt, *, max_tokens=512)`:

1. מוסיפים `(system, prompt, max_tokens)` ל-`self.calls`, **לפני** כישלון או תשובה.
2. אם `fail == "unavailable"`, זורקים `ModelUnavailable`; אם `fail == "rejected"`, זורקים `ModelRejected`.
3. הטקסט:
   - reply הוא callable: `reply(system, prompt)`;
   - reply הוא רשימה: הקריאה הראשונה מקבלת `reply[0]`, השנייה `reply[1]`, וכן הלאה; אחרי הסוף ממשיכים להחזיר את האחרון (אפשר להשתמש במספר הקריאות שכבר נרשמו, חסום באורך הרשימה);
   - reply הוא מחרוזת: תמיד אותה מחרוזת;
   - reply הוא None: מחפשים בפרומפט `<document id="X" ...>` (regex כמו `<document id="([^"]+)"`). אם נמצא, עונים במשפט שמצטט את ה-id **הראשון** בצורה `[X]`; אחרת `"I don't know."`.
4. מחזירים `Completion(text, model=self.name, input_tokens=len(prompt)//4, output_tokens=max(1, len(text)//4))`.

## InMemoryRetriever

### רמז 1: כיוון

אין צורך לכתוב דירוג: `rank` מ-`designkit.domain` כבר מיובא ושומר את כל ההבטחות של ה-port (ממוין, ייחודי, לכל היותר k, `[]` כשאין התאמה). המלכודת: לרשום את השאילתה ב-`calls` גם כשהשירות "למטה".

### רמז 2: מבנה

ב-`__init__`: שמירת עותק של ה-passages, הדגל `fail`, ו-`calls` ריקה. ב-`search`: רישום, בדיקת `fail`, ואז קריאה ל-`rank`.

### רמז 3: האלגוריתם המלא

1. `__init__(self, passages, *, fail=False)`: `self.passages = list(passages)`, `self.fail = fail`, `self.calls = []`.
2. `search(query, k=4)`: מוסיפים את `query` ל-`self.calls`; אם `fail`, זורקים `RetrieverUnavailable`; אחרת מחזירים `rank(query, self.passages, k)`.

## InMemoryAnswerStore

### רמז 1: כיוון

מילון רגיל מספיק. כל הלוגיקה היא "הכתיבה הראשונה מנצחת".

### רמז 2: מבנה

מילון מ-request_id ל-Answer. `get` מחזיר מהמילון או None. `put` בודק קודם אם ה-id קיים.

### רמז 3: האלגוריתם המלא

1. `__init__`: `self.data = {}`.
2. `get(request_id)`: `self.data.get(request_id)`.
3. `put(answer)`: אם `answer.request_id` כבר במילון, מחזירים `False` ולא דורסים; אחרת שומרים ומחזירים `True`.

## FixedClock

### רמז 1: כיוון

שעון שלא זז מעצמו. המלכודת: ה-datetime חייב להיות aware (עם `tzinfo=timezone.utc`), אחרת השוואה מול זמנים אחרים תיכשל.

### רמז 2: מבנה

שדה אחד שמחזיק את הזמן הנוכחי. `now` מחזיר אותו, ו-`advance` מוסיף לו `timedelta`.

### רמז 3: האלגוריתם המלא

1. `__init__(self, at=None)`: `self.at = at or datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)`.
2. `now()`: מחזיר `self.at`.
3. `advance(seconds)`: `self.at += timedelta(seconds=seconds)` (צריך לייבא `timedelta` מ-`datetime`).

## AnswerService

### רמז 1: כיוון

זו אותה התנהגות כמו `legacy/tangled.py`, אבל השירות מקבל את כל התלויות מבחוץ ולא בונה כלום בעצמו. **הסדר** של הבדיקות הוא העיקר: כל שלב מוקדם חוסך את השלבים היקרים שאחריו. המלכודת: תשובות degraded **לא** נשמרות, כדי שניסיון חוזר יוכל להצליח, ו-`ModelRejected` לא נתפס.

### רמז 2: מבנה

ב-`__init__` שמור את כל הפרמטרים כשדות. ב-`answer` שישה שלבים לפי הסדר: חיפוש ב-store, policy, חיפוש מסמכים (בתוך try על `RetrieverUnavailable`) וסינון לפי ציון, קריאה למודל (בתוך try על `ModelUnavailable` בלבד), בניית תשובה מוצלחת, ושמירה. כדאי לכתוב שתי פונקציות עזר: אחת שבונה `Answer` עם request_id ו-created_at, ואחת ששומרת ומטפלת במקרה ש-`put` החזיר False.

### רמז 3: האלגוריתם המלא

`__init__(self, model, retriever, store, clock, *, prompt=ANSWER_PROMPT_V1, k=4, min_score=0.2, max_tokens=512)`: שומרים את כולם; **לא** בונים שום דבר בפנים.

`answer(self, req)`, בסדר הזה:

1. `store.get(req.request_id)`: אם נמצא, מחזירים אותו כמו שהוא (אף port אחר לא נקרא).
2. `policy_check(req.question, req.user_email)`: אם לא מותר, status `"refused"`, text = `decision.reason`; שומרים ומחזירים. בלי חיפוש ובלי מודל.
3. `retriever.search(req.question, self.k)`, ומשאירים passages עם `score >= min_score`.
   - `RetrieverUnavailable`: status `"degraded"`, text = `degraded_text([])`, **לא** נשמר.
   - לא נשאר כלום: status `"no_context"`, text = `NO_CONTEXT_TEXT`; שומרים ומחזירים.
4. `model.complete(prompt.template, build_prompt(req.question, passages), max_tokens=self.max_tokens)`.
   - `ModelUnavailable`: status `"degraded"`, text = `degraded_text(passages)`, citations = `[p.doc_id for p in passages]`, **לא** נשמר (ניסיון חוזר עשוי להצליח).
   - `ModelRejected`: נותנים לו לעלות למעלה (זה באג או בעיית קונפיגורציה).
5. status `"answered"`, text = `completion.text`, citations = `parse_citations(text, {doc_ids of the passages sent})`, prompt_version = `prompt.ref`, model = `completion.model`, cost_usd = `completion.cost_usd`.
6. `store.put(answer)`; אם הוא מחזיר `False` (קריאה אחרת שמרה את ה-id הזה קודם), מחזירים `store.get(id)` במקום.

כל `Answer` מקבל `created_at = clock.now()` ו-`request_id = req.request_id`.

## ChatModelContract

### רמז 1: כיוון

אתה כותב טסטים שירוצו נגד **כל** adapter, כולל adapters שבורים בכוונה. לכן כל טסט צריך לבדוק הבטחה אחת של ה-port מבחוץ, דרך `self.make_model(mode)`. המלכודת: בבדיקת שגיאה, "לא נזרק כלום" ו"נזרק exception מסוג אחר" הם שני כישלונות שונים, ושניהם צריכים להכשיל את הטסט.

### רמז 2: מבנה

מתודות `test_*` שמקבלות רק `self`, עם `assert` רגיל. טסט ל-"ok" שבודק טקסט לא ריק; טסט לשם המודל ולשדה `model` ב-Completion; טסט למספרים לא שליליים; ושני טסטים לשגיאות, כל אחד עם try/except שמחזיר בהצלחה רק על החריגה הנכונה. השתמש בקבועים `SYSTEM` ו-`PROMPT`.

### רמז 3: האלגוריתם המלא

לפחות 4 מתודות, למשל:

1. `make_model("ok").complete(SYSTEM, PROMPT, max_tokens=64)` מחזיר `Completion` ו-`c.text.strip()` לא ריק.
2. `m.name` הוא מחרוזת שמכילה `":"` (הצורה `"provider:model"`), ו-`c.model == m.name`.
3. `c.input_tokens >= 0`, `c.output_tokens >= 0`, `c.cost_usd >= 0`.
4. `make_model("unavailable")`: הקריאה זורקת `ModelUnavailable`. תופסים `ModelUnavailable` ומחזירים; תופסים כל `Exception` אחר וזורקים `AssertionError` עם שם הסוג; אם לא נזרק כלום, זורקים `AssertionError`.
5. אותו דבר עבור `"rejected"` ו-`ModelRejected`.
6. (אופציונלי) לשני המצבים, השגיאה היא `BrainError` ולא משהו שדלף מהספק.

כללים: מתודות הטסט מקבלות **רק** `self` (בלי fixtures של pytest), ומשתמשות ב-`assert` רגיל. הטסטים מריצים את החבילה שלך גם נגד adapters שבורים (מודל שמדליף exceptions של הספק, מודל שמחליף בין שתי השגיאות, מודל שמחזיר טקסט ריק), וכל אחד מהם חייב להכשיל לפחות טסט אחד שלך. ההשוואה: `designkit/contract.py`.

## RetrieverContract

### רמז 1: כיוון

כל הבטחה ב-docstring של `Retriever` היא טסט. השתמש ב-`SAMPLE` כדי שהתוצאות יהיו צפויות. המלכודת: הבדיקה של "ייחודי" צריכה קלט שבאמת מכיל כפילות.

### רמז 2: מבנה

מתודת `test_*` לכל הבטחה, כל אחת בונה retriever חדש עם `self.make_retriever(...)`. לבדיקת מיון: השווה את רשימת הציונים לגרסה הממוינת שלה בסדר יורד. לייחודיות: העבר את `SAMPLE` ועוד עותק של אחד הפריטים, והשווה אורך רשימה לאורך set.

### רמז 3: האלגוריתם המלא

לפחות 4 מתודות, למשל:

1. `search("vacation days first year", k=3)` לא ריק, והראשון הוא `vacation_policy.md`.
2. `search("employees days policy office", k=2)`: לכל היותר 2 תוצאות, והציונים ממוינים מהגבוה לנמוך.
3. retriever על `SAMPLE + SAMPLE[:1]`: ה-doc_ids של `search("vacation days employees", k=4)` ייחודיים.
4. `search("zebra quantum xylophone", k=3) == []` וגם `search("", k=3) == []`.
5. אותה שאילתה פעמיים מחזירה אותה תוצאה.

אותם כללים: רק `self`, `assert` רגיל. ה-adapters השבורים כאן: retriever שלא ממיין, ו-retriever שזורק exception כשאין התאמה.

## AnswerStoreContract

### רמז 1: כיוון

שלוש ההבטחות של ה-store הן שלושה טסטים. תצטרך לבנות אובייקט `Answer` לדוגמה; כדאי לכתוב לזה פונקציית עזר ברמת המודול (לא מתודת `test_`).

### רמז 2: מבנה

פונקציית עזר שבונה `Answer` עם request_id וטקסט שמתקבלים כפרמטרים. אחר כך מתודת `test_*` לכל הבטחה, כל אחת עם store חדש מ-`self.make_store()`. בטסט של "הכתיבה הראשונה מנצחת" ודא גם שה-`put` השני החזיר False וגם שהטקסט נשאר של הראשון.

### רמז 3: האלגוריתם המלא

פונקציית עזר: `Answer(request_id=rid, status="answered", text=text, citations=["vacation_policy.md"], prompt_version="answer@1.0.0", model="fake:chat", created_at=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc))`.

לפחות 3 מתודות:

1. `make_store().get("nope") is None`.
2. `s.put(a) is True` ואחר כך `s.get("r1") == a`.
3. `s.put(answer("r1", "first"))`, ואז `s.put(answer("r1", "second")) is False` ו-`s.get("r1").text == "first"`.
4. (אופציונלי) שני ids שונים לא מפריעים זה לזה.

ה-adapters השבורים כאן: store שדורס, ו-store ש"שוכח".

## check_compatible

### רמז 1: כיוון

חשוב מנקודת המבט של **קוד שקורא** את הפלט: מה יכול להפתיע אותו? שדה שנעלם, שדה שעכשיו יכול להיות null, ערך enum שהוא לא מכיר. כדאי לכתוב שתי פונקציות עזר: אחת שמחזירה את קבוצת ה-types ששדה יכול להחזיק, ואחת שמחזירה את קבוצת ערכי ה-enum (או None אם אין enum). המלכודת: Pydantic מייצג `Optional` כ-`anyOf` עם `{"type": "null"}`.

### רמז 2: מבנה

טפל קודם במקרי הקצה (`old` הוא None, `new` הוא None). אחר כך לולאה על השדות של `old`: שדה שנעלם (שבור רק אם היה required); שדה שהיה required ועכשיו לא; types חדשים (הפרש קבוצות); ושינויי enum (enum שנעלם, או ערכים חדשים). פונקציות העזר צריכות להיות רקורסיביות על `anyOf`.

### רמז 3: האלגוריתם המלא

מסתכלים רק על `"properties"` ו-`"required"` ברמה העליונה. כל הודעה מתחילה ב-`"breaking:"` ומציינת את שם השדה במרכאות בודדות.

**פונקציות עזר** (כמו ב-`designkit/registry.py`):

- **types(prop)**: אם יש `"anyOf"`, האיחוד של types של כל החברים; אם יש `"$ref"`, `{"object"}`; אם `"type"` הוא רשימה, הקבוצה שלה; אם הוא מחרוזת, קבוצה עם איבר אחד; אם יש רק `"enum"`, שמות הסוגים של הערכים (`str` הופך ל-`string`, `NoneType` ל-`null`); אחרת `{"any"}`.
- **enum(prop)**: אם יש `"enum"`, הקבוצה שלו; אם יש `"const"`, קבוצה עם הערך; אם יש `"anyOf"`, האיחוד של ה-enums של החברים שאינם null, אבל רק אם לכולם יש enum; אחרת `None`.

**הכללים:**

1. `old is None`: מחזירים `[]`.
2. `new is None` (ו-old קיים): `"breaking: the output schema was removed"`.
3. לכל שדה ב-`old["properties"]`:
   - חסר ב-new: אם היה ב-required של old, `f"breaking: removed field '{name}'"`. (שדה אופציונלי תמיד יכול היה לחסור, ולכן הסרה שלו לא שוברת קורא זהיר.) ממשיכים לשדה הבא.
   - required ב-old ולא ב-new: `f"breaking: field '{name}' is no longer required (it may be missing)"`.
   - **added** = types(new) פחות types(old). אם לא ריק, ו-`"any"` לא נמצא ב-types(old): `f"breaking: field '{name}' can now be {', '.join(sorted(added))}"` (ההודעה צריכה להכיל את הסוג החדש, למשל `null`).
   - ל-old היה enum ול-new אין, ולא נוספו types: `f"breaking: field '{name}' is no longer restricted to {sorted(map(str, old_enum))}"`.
   - אחרת, אם לשניהם יש enum ול-new יש ערכים חדשים: `f"breaking: field '{name}' has new values {sorted(map(str, new_enum - old_enum))}"` (ההודעה צריכה להכיל את הערך החדש, למשל `partial`).

**לא שובר:** שדות חדשים, הסרת שדה אופציונלי, פחות types, פחות ערכי enum.

## PromptRegistry

### רמז 1: כיוון

המפתח הוא להשוות גרסאות **כמספרים**: הפוך `"1.10.0"` ל-tuple `(1, 10, 0)`, ו-tuples משתווים נכון. regex כמו `^(\d+)\.(\d+)\.(\d+)$` גם מאמת את הפורמט. המלכודת: גרסה שנדחתה בגלל אי-תאימות אסור שתיכנס ל-registry.

### רמז 2: מבנה

מבנה נתונים: מילון משם פרומפט למילון מגרסה ל-`PromptVersion`. פונקציית עזר `parse_version`. `register`: ולידציה, בדיקת כפילות, מציאת הגרסה הקודמת באותו MAJOR, בדיקת תאימות, ורק בסוף שמירה. `get`: בחירת מועמדים לפי ה-pin (השוואת prefix של ה-tuple), ואז המקסימום. `versions`: מיון לפי ה-tuple.

### רמז 3: האלגוריתם המלא

**`parse_version(v)`**: לפי `^(\d+)\.(\d+)\.(\d+)$`; אם אין התאמה, `ValueError`; אחרת tuple של שלושה ints.

**`register(pv)`**:

1. `parse_version(pv.version)` (גרסה לא חוקית זורקת `ValueError`).
2. אם אותו שם ואותה גרסה כבר רשומים: אותו `pv.fingerprint` לא עושה כלום (idempotent); fingerprint אחר זורק `ValueError` (גרסאות הן immutable, צריך לפרסם גרסה חדשה).
3. אחרת, לוקחים את הגרסה **הגבוהה ביותר** של אותו שם עם **אותו MAJOR** ו**נמוכה** מ-pv. אם יש כזאת ו-`check_compatible(that.output_schema, pv.output_schema)` מוצא בעיות, זורקים `IncompatibleVersion`. ההודעה מפרטת את הבעיות (למשל: `f"{pv.ref} breaks {prev.ref}; publish it as {major + 1}.0.0. "` ואחריה הבעיות מחוברות ב-`"; "`).
4. רק אם הכול עבר, שומרים.

**`get(name, pin="latest")`**:

- שם לא מוכר: `KeyError`.
- `"latest"`: כל הגרסאות מועמדות.
- `"1"`: גרסאות שה-MAJOR שלהן 1; `"1.2"`: גרסאות 1.2.x; `"1.2.3"`: בדיוק זו. (אפשר להפוך את ה-pin ל-tuple ולהשוות אותו ל-prefix באותו אורך של tuple הגרסה.)
- אין מועמדים: `KeyError`.
- מחזירים את המועמד עם הגרסה הגבוהה ביותר.

**`versions(name)`**: רשימת מחרוזות הגרסה, ממוינת מהנמוכה לגבוהה לפי `parse_version` (כך ש-`1.10.0` אחרי `1.9.0`).

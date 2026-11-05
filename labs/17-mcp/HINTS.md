# רמזים למעבדה 17

הקובץ הזה הוא המקום לקבל עזרה כשנתקעים. ה-docstring ב-`mine.py` הוא החוזה: מה הפונקציה מקבלת, מה היא מחזירה, ואילו כללים התוצאה חייבת לקיים. כאן יש לכל פונקציה שלוש רמות של רמזים, מהקטן לגדול. כדאי לנסות קודם לבד. אם נתקעת, קרא רק את **רמז 1** ונסה שוב. אם עדיין לא הולך, קרא את **רמז 2**, ורק אחר כך את **רמז 3**, שמכיל את האלגוריתם המלא. אפשר לעצור אחרי כל רמה.

המימושים המלאים נמצאים ב-`mcpkit/` (`oncall.py`, `bridge.py`, `pinning.py`). כדאי להשוות אליהם רק אחרי שהבדיקות שלך עוברות.

שים לב: בתרגיל 7 מופיעים בבדיקות תיאורי כלים "מורעלים" (למשל הערת HTML שמנסה לגרום לסוכן לקרוא ל-`create_access_request`). זה חומר הדגמה של התקפה, נתונים בלבד.

## get_oncall_for_service

### רמז 1: כיוון

זו עבודת **פענוח טקסט**: טבלת Markdown אחת מתוך מסמך שיש בו כמה טבלאות, ותא אחד ("On-call rotation") שמכיל כמה פיסות מידע בפורמטים שונים. כדאי להפריד בין שלוש בעיות: למצוא את הטבלה הנכונה, להפוך שורות למילונים, ולפרק את תא הכוננות. המודול `re` עוזר למצוא את הקטע ואת החלקים בתא, ו-`difflib.get_close_matches` נותן את ההצעות בהודעת השגיאה. מלכודת: רוטציה משותפת לא כותבת את לוח הזמנים בשורה שלה.

### רמז 2: מבנה

- נרמול השם שהתבקש, ובדיקה שהוא לא ריק.
- חיתוך הקטע של `## Production services` עד הכותרת `## ` הבאה, לקיחת השורות שמתחילות ב-`|`, שורת הכותרת כמפתחות, ודילוג על שורת `|---|`.
- מילון מהשם (באותיות קטנות) לשורה. אם השם לא נמצא: שגיאה עם הצעות או עם רשימת כל השמות.
- פונקציית עזר שמפרקת את תא הכוננות למילון של חמישה שדות (rotation, schedule, secondary, shared_with, channel). מקרה "business hours" מטופל לבד.
- אם הרוטציה משותפת ואין לה לוח זמנים, מחפשים את השורה שמגדירה את אותה רוטציה ולוקחים ממנה.
- השדות שנגזרים מה-tier, וה-runbook לפי הכלל שבראש התרגיל.

### רמז 3: האלגוריתם המלא

1. **נרמול:** `key = (service or "").strip().lower()`, ואז מחליפים רווחים וקווים תחתונים במקפים. אם `key` ריק: `raise ToolError("service is empty. ...")` (למשל `"service is empty. Pass a service name such as 'flow-api' or 'billing-service'."`).
2. **הטבלה:** הטקסט הוא `catalog` אם הוא לא `None`, אחרת `mcpkit.oncall.catalog_text()`. מוצאים את הקטע שמתחיל בשורה `## Production services` ונגמר בכותרת `## ` הבאה או בסוף הטקסט (למשל `re.search(r"^## Production services\s*$(.*?)(?=^## |\Z)", text, flags=re.M | re.S)`). לוקחים רק שורות שמתחילות ב-`|`. השורה הראשונה היא הכותרת; את השנייה (`|---|`) מדלגים. כל תא: `strip("|").split("|")` ואז strip לכל תא, ו-`dict(zip(header, cells))`.
3. **חיפוש:** מילון `r["Service"].lower() -> row`. אם `key` לא בו: `close = difflib.get_close_matches(key, names, n=3, cutoff=0.5)`. ההודעה של `ToolError` מכילה את השם שהתבקש, ואחריו `Did you mean: ...?` עם ההצעות, או, כשאין הצעות, `Known services: ...` עם כל השמות. (`"flow-ap"` מציע `"flow-api"`; `"kafka"` מקבל את כל הרשימה, כולל `lighthouse`.)
4. **פירוק תא הכוננות:**
   - אם התא מתחיל ב-`"business hours"` (בלי תלות באותיות): rotation, schedule, secondary ו-shared_with הם `None`, ו-channel הוא ה-`#...` שבתא (`#data-help`).
   - אחרת מפצלים ב-`";"` הראשון: החלק שאחריו יכול להכיל `secondary is <name>`, וזה ה-secondary.
   - בחלק הראשון, `(shared with <name>)` נותן את shared_with, ומסירים אותו מהטקסט.
   - מה שנשאר מתפצל ב-`":"` הראשון: לפניו שם הרוטציה, ואחריו לוח הזמנים (strip לשניהם, ו-`None` כשריק). כך `"weekly, handover Sunday 10:00"` הוא הטקסט אחרי `"<rotation>:"` ועד `";"` אם יש.
5. **רוטציה משותפת:** אם יש shared_with ואין schedule, עוברים על כל השורות, מפרקים את התא שלהן, ולוקחים את ה-schedule של השורה הראשונה עם אותה רוטציה ועם schedule. (`flow-scheduler` מקבל את `"weekly, handover Sunday 10:00"` מ-`flow-engine`.)
6. **שאר השדות:**
   - `service`: השם כפי שהוא כתוב בטבלה. `owner_team`, `team_lead`: מהתאים. `tier`: `int(row["Tier"])`.
   - `pagerduty_service`: התא, או `None` כשהוא `"none"` או ריק.
   - `coverage`: `"24/7"` ל-tier 1 ו-2, `"business hours"` ל-tier 3.
   - `ack_minutes`: 5 ל-tier 1, 15 ל-tier 2, `None` ל-tier 3.
   - `runbook`: מזהה המסמך שהכותרת שלו ב-front-matter נגמרת ב-`" - <service>"`, או `None`. המיפוי: flow-api ל-`eng-runbook-flow-api`, flow-engine ל-`eng-runbook-flow-engine`, billing-service ל-`eng-runbook-billing`, flow-scheduler ל-`eng-oncall-scheduler-he`. (המימוש המלא סורק את `data/acme/corpus/docs/*.md` ומוצא `title:` בתחילת כל קובץ; מותר גם לכתוב את המיפוי כקבוע.)
   - `source`: תמיד `"eng-service-catalog"`.
7. מחזירים מילון עם **בדיוק** 14 המפתחות שבחוזה.

(`re` ו-`difflib` לא מיובאים בראש `mine.py`; תצטרך להוסיף אותם.)

## mcp_tool_to_llmkit

### רמז 1: כיוון

זה גשר בין שני פורמטים: כלי MCP כמו ש-`tools/list` מחזיר, ו-`Tool` של llmkit שנשלח לספק. שלוש נקודות רגישות: השם חייב לעמוד בתבנית של כל הספקים (ואורך 64 לכל היותר), התיאור לא יכול להיות ריק, ו**אסור לשנות את מילון הקלט**, כלומר הסכמה צריכה להיות עותק עמוק (`copy.deepcopy`, או `json.loads(json.dumps(...))`).

### רמז 2: מבנה

- השם: מחברים את קידומת השרת, מחליפים תווים אסורים עם `re.sub`, ואם השם עדיין ארוך מדי, מקצרים ומוסיפים hash של השם **המקורי** (לפני ההחלפה) כדי ששני שמות ארוכים שונים לא יתנגשו.
- התיאור: שרשרת `or` של שלוש אפשרויות, ואז strip.
- הסכמה: עותק עמוק, הסרת `"title"` ברמה העליונה, והשלמת `"type"` ו-`"properties"` עם `setdefault`.

### רמז 3: האלגוריתם המלא

1. **name:** `raw = f"{server}__{tool['name']}"` כשיש server, אחרת `tool["name"]`. מחליפים כל תו שמחוץ ל-`[a-zA-Z0-9_-]` ב-`"_"` (`re.sub(r"[^a-zA-Z0-9_-]", "_", raw)`). אם התוצאה ארוכה מ-64 תווים: לוקחים את 55 התווים הראשונים, אחריהם `"_"`, ואחריהם 8 תווי ה-hex הראשונים של `sha256(raw.encode("utf-8"))`, כלומר של השם **לפני** ההחלפה. (בדיקה: `"my server"` ו-`"get.weather"` נותנים `"my_server__get_weather"`.)
2. **description:** `tool["description"]`, או `tool["title"]` אם אין תיאור, או השם; אחרי strip של רווחים מסביב.
3. **input_schema:** עותק **עמוק** של `tool["inputSchema"]` (או `{}` אם חסר), בלי המפתח `"title"` ברמה העליונה, ועם `"type": "object"` ו-`"properties": {}` כשהם חסרים. לעולם לא משנים את מילון הקלט.
4. **strict:** `False`. מחזירים `Tool(name=..., description=..., input_schema=..., strict=False)`.

(`re`, `hashlib` ו-`copy` לא מיובאים בראש `mine.py`; תצטרך להוסיף אותם.)

## call_result_to_tool_result

### רמז 1: כיוון

המודל מקבל טקסט, ולכן כל בלוק בתוצאה של MCP צריך להפוך לטקסט קריא, לפי הסוג שלו. הפורמט המדויק של כל סוג כתוב בחוזה, והבדיקה משווה מחרוזת שלמה, אז שים לב לרווחים ולשורות חדשות. שני מקרי קצה: `content` יכול להיות חסר או ריק, ואז משתמשים ב-`structuredContent`.

### רמז 2: מבנה

לולאה על הבלוקים שבונה רשימה של חלקים, עם ענף לכל סוג (text, resource, resource_link, וכל השאר). מחברים רק את החלקים הלא ריקים עם שורה ריקה ביניהם. אם יצא טקסט ריק ויש תוכן מובנה, ממירים אותו ל-JSON. בסוף בונים `ToolResult`.

### רמז 3: האלגוריתם המלא

1. לכל בלוק ב-`result.get("content") or []`:
   - `{"type": "text", "text": t}`: החלק הוא `t`.
   - `{"type": "resource", "resource": {"uri": u, "text": t}}`: החלק הוא `f"[resource {u}]\n{t}"`, ואחרי זה `rstrip()` לחלק.
   - `{"type": "resource_link", "uri": u, ...}`: החלק הוא `f"[resource link {u}]"`.
   - כל סוג אחר (image, audio): `f"[{type} omitted: {mimeType}]"`, עם `"?"` כשאין `mimeType`.
2. `text = "\n\n".join(p for p in parts if p)`.
3. אם `text` ריק ו-`"structuredContent"` קיים: `text = json.dumps(result["structuredContent"], ensure_ascii=False)`.
4. מחזירים `ToolResult(call.id, text, is_error=bool(result.get("isError")), name=call.name)`.

(`json` לא מיובא בראש `mine.py`; תצטרך להוסיף `import json`.)

## tool_fingerprint

### רמז 1: כיוון

טביעת אצבע של מה ש**המודל רואה**: שם, תיאור וסכמה. שדות שמוצגים רק בממשק (title, annotations, _meta) לא נכנסים, כי שינוי בהם לא משנה את הפרומפט. כדי שהתוצאה תהיה זהה לזו של `mcpkit.pinning`, המחרוזת צריכה להיות קנונית בדיוק באותה צורה. זה אותו רעיון כמו `call_fingerprint` בשיעור 14.

### רמז 2: מבנה

בונים מילון עם שלושת השדות (עם ברירות מחדל לחסרים), ממירים ל-JSON קנוני, מקודדים ל-utf-8 ומחשבים sha256 hex.

### רמז 3: האלגוריתם המלא

1. `obj = {"name": tool["name"], "description": tool.get("description") or "", "inputSchema": tool.get("inputSchema") or {}}`.
2. `canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
3. מחזירים `hashlib.sha256(canon.encode("utf-8")).hexdigest()`.

(`hashlib` ו-`json` לא מיובאים בראש `mine.py`.)

## diff_tool_pins

### רמז 1: כיוון

השוואה בין שתי "תמונות" של רשימת הכלים: מה שאדם בדק ונעל, ומה שהשרת מציג עכשיו. פעולות על קבוצות (`-` ו-`&`) נותנות את מה שנוסף, הוסר ומשותף. עבור הכלים המשותפים משווים את טביעות האצבע, ורק לכלים ששונו מחשבים diff קריא של התיאור, כדי שאדם יראה **מה** בדיוק השתנה (למשל שורה מוסתרת שנוספה בסוף). מלכודת: `pinned` מגיע בשתי צורות.

### רמז 2: מבנה

- מנרמלים את `pinned` למיפוי של הכלים בלבד.
- בונים מילון שם -> כלי מהרשימה הנוכחית.
- added ו-removed: הפרשי קבוצות, ממוינים.
- לכל שם משותף, לפי סדר אלפביתי: מחשבים את טביעת האצבע החדשה. אם היא שווה לנעולה, ממשיכים. אחרת בונים רשומת שינוי עם ה-diff ועם הדגל של הסכמה.
- ok הוא True רק כששלוש הרשימות ריקות.

### רמז 3: האלגוריתם המלא

1. `pins = pinned["tools"]` כשהמפתח קיים, אחרת `pinned` עצמו.
2. `now = {t["name"]: t for t in current}`.
3. `added = sorted(set(now) - set(pins))`, `removed = sorted(set(pins) - set(now))`.
4. לכל `name` ב-`sorted(set(now) & set(pins))`:
   - `new_sha = tool_fingerprint(now[name])`. אם הוא שווה ל-`pins[name]["sha256"]`, ממשיכים לשם הבא.
   - `old = pins[name].get("description", "")`, `new = now[name].get("description") or ""`.
   - `description_diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), "pinned", "current", lineterm=""))`, או `""` כשהטקסט שווה.
   - `schema_changed = (pins[name].get("inputSchema") or {}) != (now[name].get("inputSchema") or {})`.
   - מוסיפים `{"name": name, "old_sha256": pins[name]["sha256"], "new_sha256": new_sha, "description_diff": ..., "schema_changed": ...}` ל-`changed`.
5. `ok = not (added or removed or changed)`.
6. מחזירים `{"ok": ok, "added": added, "removed": removed, "changed": changed}`.

(`difflib` לא מיובא בראש `mine.py`.)

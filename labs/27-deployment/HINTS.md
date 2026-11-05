# רמזים למעבדה 27: Deployment

הקובץ הזה הוא למקרה שנתקעת. קודם נסה לבד לפי ה-docstring ב-`mine.py` ולפי הטסטים. אם נתקעת, קרא רק את **רמז 1** של הפונקציה, סגור את הקובץ ונסה שוב. רק אם עדיין תקוע, עבור ל**רמז 2**, ורק בסוף ל**רמז 3**, שמכיל את האלגוריתם המלא. כל רמה כתובה כך שאפשר לעצור אחריה.

את המימושים המלאים (reference) תמצא ב-`deploykit/dockerfile.py`, `deploykit/terraform.py` ו-`deploykit/cost.py`. כדאי לפתוח אותם רק אחרי שהטסטים שלך עוברים, כדי להשוות. הדוגמה הפתורה `rule_base_image_pinned` בראש `mine.py` מראה את הסגנון: לולאה על ההוראות, ורשימת `Finding`.

## rule_runs_as_non_root

### רמז 1: כיוון
`stages(instrs)` כבר מפרק את ה-Dockerfile לשלבים. השאלה היא "מי המשתמש של השלב האחרון", והתשובה יכולה להיות תלויה בשלב קודם שהוא נבנה ממנו, ולכן צריך **לעקוב אחרי שרשרת**. המלכודת: `USER app:app` (רק החלק שלפני הנקודתיים הוא המשתמש), ו-`USER 0` שהוא גם root.

### רמז 2: מבנה
1. אם אין שלבים בכלל, מחזירים את הממצא של "no FROM instruction".
2. בונים מילון שממפה שם של שלב (האינדקס כמחרוזת, וה-alias באותיות קטנות) לשלב.
3. פונקציית עזר (רקורסיבית או לולאה) שמחזירה לשלב את המשתמש האפקטיבי ואת השורה הרלוונטית: אם יש בו `USER`, האחרון קובע; אחרת, אם הבסיס שלו הוא שלב קודם, שואלים אותו; אחרת זו תמונה חיצונית.
4. בודקים את השלב האחרון ומחזירים ממצא אחד או רשימה ריקה.

### רמז 3: האלגוריתם המלא
- אין `FROM` בכלל: `[Finding("runs_as_non_root", "error", "1", "no FROM instruction")]`.
- המשתמש האפקטיבי של שלב הוא הערך של הוראת ה-`USER` **האחרונה** שלו, רק החלק שלפני `":"` (`"app:app"` הופך ל-`"app"`, `"10001:10001"` ל-`"10001"`). השורה הרלוונטית היא השורה של אותה הוראה.
- שלב בלי `USER`:
  - אם הבסיס שלו (`st.base`) שווה ל-alias של שלב קודם (בלי תלות באותיות) או לאינדקס שלו כמחרוזת: יורש את המשתמש האפקטיבי של אותו שלב (ממשיכים בשרשרת).
  - אם הבסיס הוא תמונה חיצונית: root, אלא אם שם התמונה מכיל `"nonroot"` (תמונות distroless כמו `gcr.io/distroless/python3-debian12:nonroot` רצות כמשתמש לא-root).
  - השורה הרלוונטית היא שורת ה-`FROM` של השלב האחרון.
- המשתמש הוא root אם הוא `"root"` או `"0"` (בלי תלות באותיות).
- אם השלב האחרון רץ כ-root: מחזירים ממצא אחד, `severity="error"`, הודעה שמכילה `"root"`, ו-`where = str(line)` של ה-`USER` האחרון בשלב האחרון, או של ה-`FROM` שלו אם אין בו `USER`. אחרת `[]`.

## rule_no_secrets_in_build

### רמז 1: כיוון
שלוש פונקציות העזר כבר עושות את העבודה הקשה: `env_pairs`, `looks_like_secret_name`, `looks_like_secret_value`. התרגיל הוא לשלב אותן נכון. המלכודת: אותה דליפה עלולה להתגלות פעמיים, פעם כערך של ENV ופעם בבדיקה הכללית של הטקסט, וצריך לדווח רק פעם אחת.

### רמז 2: מבנה
לולאה על ההוראות. לכל הוראה דגל "כבר דיווחתי על ערך בצורת מפתח". אם זו `ENV` או `ARG`, לולאה על הזוגות עם שתי בדיקות (ערך ואז שם). אחרי זה, אם הדגל לא הודלק, בדיקה אחת על כל הטקסט של ההוראה כולל ה-heredoc.

### רמז 3: האלגוריתם המלא
לכל הוראה `ins` (כל הממצאים: `rule="no_secrets_in_build"`, `severity="error"`, `where=str(ins.line)`):
1. אם `ins.cmd` הוא `ENV` או `ARG`, לכל `(key, value)` ב-`env_pairs(ins)`:
   - א. אם `looks_like_secret_value(value)`: ממצא שההודעה שלו מכילה את `key`, ומדליקים את הדגל.
   - ב. אחרת, אם `looks_like_secret_name(key)` וגם (זו `ARG` או ש-`value` לא ריק): ממצא שההודעה שלו מכילה את `key`. ב-`ARG` ההודעה מזכירה `"secret"` (הפתרון הוא `RUN --mount=type=secret`, כי build args נשמרים בהיסטוריית התמונה). `ENV ANTHROPIC_API_KEY=` ריק הוא placeholder ולא דליפה, ולכן אין ממצא.
2. אם הדגל לא הודלק: אם `looks_like_secret_value(ins.args + "\n" + ins.heredoc)`, ממצא אחד. כך נתפסים `RUN curl -H "x-api-key: sk-ant-..."` וסודות בתוך heredoc.
3. התוצאה: `ENV ANTHROPIC_API_KEY=sk-ant-...` נותן בדיוק ממצא **אחד** (מסעיף 1א), לא שניים.

## rule_iam_least_privilege

### רמז 1: כיוון
עוברים על ה-statements אחד אחד, ובכל אחד שלוש בדיקות נפרדות: wildcards בפעולות, `not_actions`, ו-`Resource "*"`. `STAR_ONLY_ACTIONS` הוא רשימת הפעולות שאין להן משאב אחר מלבד `"*"`, ולכן עבורן `"*"` לגיטימי. המלכודת: להשוות באותיות קטנות, אבל לכתוב בהודעה את הפעולה **כפי שנכתבה**.

### רמז 2: מבנה
1. דילוג על `Deny`.
2. לולאה על הפעולות: wildcard מלא (שגיאה) או חלקי (אזהרה), ממצא לכל פעולה.
3. בדיקה אחת של `not_actions`.
4. חישוב שני דברים: האם יש משאב `"*"`, וקבוצת הפעולות באותיות קטנות. ואז `if/elif`: קודם PassRole, ואחר כך פעולות שלא צריכות `"*"`.

### רמז 3: האלגוריתם המלא
לכל `st` (כל הממצאים: `rule="iam_least_privilege"`, `where=st.where`):
- אם `st.effect.lower() == "deny"`: מדלגים.
1. לכל פעולה `a`, עם `x = a.strip().lower()`:
   - `x == "*"` או `x.endswith(":*")`: `error`, ההודעה מכילה את `a` כפי שנכתבה (למשל `"S3:*"`).
   - אחרת, אם `"*" in x` (למשל `"s3:Get*"`): `warning`, ההודעה מכילה את `a` כפי שנכתבה.
2. אם `st.not_actions` לא ריקה: `error` אחד, ההודעה מכילה `"not_actions"`.
3. `star = any(r == "*" for r in st.resources)`; `acts = {a.strip().lower() for a in st.actions}`.
   - אם `star` ו-`"iam:passrole" in acts`: `error` אחד, ההודעה מכילה `"PassRole"`.
   - אחרת, אם `star` ולא (`acts` לא ריקה וגם `acts <= STAR_ONLY_ACTIONS`): `warning` אחד. ההודעה מכילה `"'*'"` ואת `", ".join(sorted(acts - STAR_ONLY_ACTIONS))`.
- Trust policies (`has_principals`, בלי resources) לא מייצרות כלום בשלב 3, כי `star` הוא `False`.

## monthly_cost

### רמז 1: כיוון
כל שורה היא "כמות × שעות × מחיר לשעה", או "כמות × מחיר לחודש", או "GB × מחיר ל-GB". חשוב על כל משאב AWS: מה מחויב לפי שעה ומה לפי חודש או נפח. המלכודת: `public_ipv4`, שבה יש שני מקורות של כתובות, ו-`per_day` כשהשעות הן 0.

### רמז 2: מבנה
שלוף את מחירי Fargate לפי הארכיטקטורה (שורה שתזרוק `KeyError` מעצמה לארכיטקטורה לא מוכרת). בנה מילון עם 11 המפתחות בדיוק, חשב סכום, וחשב עלות ליום עם הגנה מחלוקה באפס.

### רמז 3: האלגוריתם המלא
עם `h = cfg.hours` ו-`f = prices["fargate"][cfg.arch]` (ארכיטקטורה לא מוכרת זורקת `KeyError` באופן טבעי):
- `fargate_cpu = tasks_avg * vcpu * h * f["vcpu_hour"]`
- `fargate_memory = tasks_avg * memory_gb * h * f["gb_hour"]`
- `alb_hours = alb_count * h * prices["alb_hour"]`
- `alb_lcu = alb_count * lcu_avg * h * prices["lcu_hour"]`
- `public_ipv4 = ((tasks_avg if task_public_ip else 0) + alb_count * azs) * h * prices["public_ipv4_hour"]` (כל משימה רצה עם IP ציבורי, ועוד כתובת אחת לכל AZ לכל ALB)
- `nat_gateway = nat_gateways * h * prices["nat_hour"] + nat_gb * prices["nat_gb"]`
- `vpc_endpoints = interface_endpoints * azs * h * prices["vpce_hour_per_az"]`
- `secrets_manager = secrets * prices["secret_month"] + secret_api_calls / 10_000 * prices["secret_per_10k_calls"]`
- `cloudwatch_logs = log_gb * (prices["logs_ingest_gb"] + prices["logs_store_gb_month"])`
- `ecr_storage = image_gb * prices["ecr_gb_month"]`
- `alarms = alarms * prices["alarm_month"]`

(כל השדות האלה הם `cfg.<field>`.) `total` = סכום כל השורות; `per_day = total * 24 / h`, או `0.0` כאשר `h == 0`. מחזירים `{"items": items, "total": total, "per_day": per_day}`.

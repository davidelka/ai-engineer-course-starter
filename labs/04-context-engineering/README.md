# מעבדה 4: Context Engineering and Prompt Architecture

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt      # אין תלויות חדשות: tiktoken כבר שם
python -m pytest -q                     # בדיקות הסביבה, כולל tests/test_context.py החדש
python -m pytest -q labs/04-context-engineering/tests   # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

## מה חדש

- **llmkit יודע prompt caching:**
  - `Block(text, cache="5m" | "1h")`: בלוק טקסט בתוך `system` או בתוך הודעה. בלוק עם `cache` הוא נקודת שבירה (breakpoint): אצל Anthropic הוא הופך ל-`cache_control`, וכל מה שעד סופו הוא הקידומת שנשמרת במטמון. מחרוזת רגילה ממשיכה לעבוד כמו קודם.
  - `ChatRequest(cache="5m")`: caching אוטומטי של Anthropic, כלומר `cache_control` ברמת הבקשה. ה-API שם את נקודת השבירה על הבלוק האחרון ומזיז אותה קדימה כשהשיחה גדלה.
  - `ChatRequest(cache_key="...")`: נשלח ל-OpenAI כ-`prompt_cache_key`.
  - ב-`Usage` יש עכשיו `cached_input_tokens` (קריאות מהמטמון), `cache_creation_tokens` (כתיבות למטמון), `cache_creation_1h_tokens`, ו-`uncached_input_tokens`. השדה `input_tokens` הוא תמיד **כל** הפרומפט, אצל כל הספקים. אצל Anthropic זה אומר חיבור של שלושה שדות, כי ה-API מדווח בנפרד על מה שנקרא, מה שנכתב ומה שבא אחרי נקודת השבירה.
  - `llmkit/pricing.py` מתמחר קריאה (פי 0.1 ממחיר הקלט) וכתיבה (פי 1.25 ל-5 דקות, פי 2 לשעה), לפי התיעוד של Anthropic מנובמבר 2026.
- **mockllm מדמה caching:** נקודות שבירה, אורך חיים של 5 דקות או שעה, מינימום של 512 טוקנים, lookback של 20 בלוקים, ו-caching אוטומטי של קידומות אצל OpenAI ו-Gemini. הדגלים החדשים:
  - `--prefill-tps 5000`: כל טוקן קלט שלא הגיע מהמטמון עולה זמן, כך שרואים את ההבדל ב-TTFT. המהירות הזו מומצאת, והמספרים האמיתיים מגיעים רק מהריצה החיה.
  - `--cache-ttl-scale 0.01`: מקצר את אורך החיים, למשל 5 דקות הופכות ל-3 שניות.
  - `--cache-min-tokens` ו-`--no-cache`.
- **ctxkit (חבילה חדשה בשורש):** ספירת טוקנים, פירוק בקשה לשכבות, בניית בקשה שמתאימה ל-caching, compaction, מודל עלות של caching, ו-haystack לבדיקת מיקום. שלושה מהמודולים הם קוד הייחוס של התרגילים שלך, אז אל תקרא את `layers.py`, `layout.py` ו-`compaction.py` לפני שהבדיקות שלך עוברות.
- **הנתונים של המעבדה** (סינתטיים, נוצרים מחדש עם `make_fixtures.py`):
  - `data/acme_handbook.md`: מדריך עובד של Acme, כ-10,500 טוקנים לפי o200k, ובהערכה כ-13,000 אצל Claude (המספר המדויק: `--calibrate`). 79 סעיפים: משרדים, צוותים, אש"ל לפי מדינה, מערכות פנימיות ונהלים. זו הקידומת הגדולה של ניסויי ה-caching, וה-haystack של בדיקת המיקום.
  - `data/long_conversation.json`: שיחה של 56 הודעות. ב-24 ההודעות הראשונות העובדת מספרת 12 עובדות על עצמה, ואחריהן באות 32 הודעות של שאלות מדיניות רגילות. לכל עובדה יש שאלת בדיקה.
  - `requests/agent_turn.json`: בקשה אחת של Company Brain, עם 4 כלים, system prompt עם נקודת שבירה, 5 תורות קודמות ו-2 מסמכים שאוחזרו.
- **`mine.py`**: הקוד שלך לתרגילים 1, 2 ו-6.

## התרגילים

**1. לאן הולכים הטוקנים.** ממש את `layer_report` ב-`mine.py`. הפונקציה מקבלת גוף של בקשה ל-Anthropic ומחזירה חמש שכבות: tools, system, history, retrieved, user_turn. לכל שכבה היא מחזירה כמה טוקנים יש בה, וכמה מהם נמצאים בתוך הקידומת שנשמרת במטמון. אחרי שהבדיקות עוברות, הרץ את המנתח על שלוש הבקשות המובנות:
- `hr-naive`: עוזר ה-HR משיעור 1. ההוראות קצרות, ומדריך העובד והמדיניות מודבקים אחרי השאלה, בתוך הודעת המשתמש.
- `hr-layered`: אותה בקשה, מהפונקציה שלך בתרגיל 2.
- `agent`: הבקשה מ-`requests/agent_turn.json`.

ענה: איזו שכבה היא הכי גדולה בכל בקשה? איזה אחוז מהפרומפט נמצא בקידומת שנשמרת במטמון? ולמה ב-`hr-naive` השכבה retrieved ריקה, למרות שיש בה מסמכים?

```bash
python -m pytest -q labs/04-context-engineering/tests/test_ex1_layers.py
python labs/04-context-engineering/context_budget.py
python labs/04-context-engineering/context_budget.py --scenario agent --calibrate   # הספירה המדויקת של Claude, חינם
```

**2. עוזר HR שבנוי ל-caching.** ממש את `build_hr_request`. ה"לפני" הוא `naive_hr_request` מ-`ctxkit/layout.py`: התאריך ושם העובד בשורה הראשונה של ה-system, והמסמכים אחרי השאלה. ה"אחרי" צריך להיראות כך:
- קידומת יציבה: ההוראות, ואחריהן המסמכים בתוך `<documents>`.
- נקודת שבירה אחת, בסוף המסמכים.
- סיומת דינמית: הקשר (עובד ותאריך), ואחריו השאלה, ממש בסוף.

```bash
python -m pytest -q labs/04-context-engineering/tests/test_ex2_layout.py
python labs/04-context-engineering/context_budget.py --scenario hr-layered
```

**3. ניסוי caching חי.** שש קריאות לעוזר ה-HR, עם קידומת של כ-13,000 טוקנים, בארבעה מצבים: `none` (בלי נקודת שבירה), `explicit` (הבקשה שלך מתרגיל 2), `auto` (cache_control ברמת הבקשה) ו-`broken` (שעה נוכחית בשורה הראשונה). לכל קריאה תראה: TTFT, טוקנים שנכתבו, טוקנים שנקראו, טוקנים בלי מטמון, ועלות. השווה את הקריאה הראשונה לאחרות, ואת המצבים זה לזה. אם הנתונים החיים לא תואמים את התיעוד, תכתוב לי.

```bash
python labs/04-context-engineering/cache_experiment.py --mode all --layout mine
# חינם: בטרמינל 2 python -m mockllm --prefill-tps 5000, ואז:
python labs/04-context-engineering/cache_experiment.py --model mock:mock-model --mode all
```

**4. מלכודות caching.** שלושה ניסויים קצרים:
- **מקביליות:** שלוש קריאות ראשונות בבת אחת. כמה מהן קוראות מהמטמון, ולמה?
- **מינימום:** הרץ עם `--short` (רק מסמך המדיניות הקצר, ובלי מדריך העובד). על Haiku 5.5 המינימום הוא 512 טוקנים, אז ייתכן שהקידומת עוד עוברת אותו. על Haiku 4.5 המינימום הוא 4,096, והיא בטוח לא תעבור. בדוק את שני המודלים.
- **שעה:** הרץ עם `--ttl 1h` והשווה את עלות הכתיבה. מתי שווה לשלם פי 2 על כתיבה?

```bash
python labs/04-context-engineering/cache_experiment.py --mode explicit --parallel 3
python labs/04-context-engineering/cache_experiment.py --mode explicit --short --calls 3
python labs/04-context-engineering/cache_experiment.py --model anthropic:claude-haiku-4-5 --mode explicit --short --calls 3
python labs/04-context-engineering/cache_experiment.py --mode explicit --ttl 1h --calls 3
```

**5. משפט אחד בהקשר ארוך.** בדיקת needle-in-a-haystack על Haiku 5.5. משפט אחד עם התשובה ("The door code for the server room on floor 7 of the Haifa office is 4-8-1-5-2") מוכנס לתוך מדריך העובד, בגדלים של 2K, 8K ו-32K טוקנים ובחמישה מיקומים. קודם הרץ `--dry-run` כדי לראות את העלות. אחר כך הרץ:
- בלי מסיחים, ועם 3 מסיחים: משפטים דומים עם קוד אחר, למשל "the storage room on floor 3 ... is 7-7-2-0-9".
- עם `--question-first`: השאלה לפני המסמכים, במקום אחריהם.

איפה המודל טועה? האם ראית "lost in the middle"? הרץ כל תצורה פעמיים לפני שאתה מסיק משהו, כי כל תא בטבלה הוא דגימה אחת.

```bash
python labs/04-context-engineering/position_test.py --dry-run
python labs/04-context-engineering/position_test.py
python labs/04-context-engineering/position_test.py --distractors 3
python labs/04-context-engineering/position_test.py --distractors 3 --question-first
```

**6. Compaction.** ממש את `compact` ב-`mine.py`: סיכום של התורות הישנות, והתורות האחרונות נשארות מילה במילה. אחר כך הרץ את `compaction_eval`, שמשווה שלוש אסטרטגיות על השיחה הארוכה, בתקציב של 400 טוקנים:
- `full`: כל השיחה. זו התקרה.
- `truncate`: חלון נע שזורק את התורות הישנות.
- `compact`: הפונקציה שלך.

התוצאה היא כמה מתוך 12 העובדות שרדו. קודם הרץ offline, אחר כך live, ונסה תקציב קטן יותר.

```bash
python -m pytest -q labs/04-context-engineering/tests/test_ex6_compact.py
python labs/04-context-engineering/compaction_eval.py --model fake --summarizer heuristic   # חינם
python labs/04-context-engineering/compaction_eval.py
python labs/04-context-engineering/compaction_eval.py --budget 250 --keep-last 2 --show
```

**7. תכנון הקשר ל-Company Brain.** העתק את `requests/company_brain_template.json` לקובץ `requests/company_brain_mine.json`, ומלא אותו בתור אמיתי של Company Brain:
- 3 כלים לפחות.
- system prompt עם ההוראות.
- 2 תורות קודמות.
- מסמכים שאוחזרו, בתוך `<documents>`.
- שאלה.

שים נקודות שבירה איפה שצריך, הרץ עליו את המנתח, ותכתוב לי שלוש שורות: מה התקציב של כל שכבה, איפה נקודות השבירה ולמה, ומה יקרה לעלות כשההיסטוריה תגדל ל-30 תורות.

```bash
cp labs/04-context-engineering/requests/company_brain_template.json labs/04-context-engineering/requests/company_brain_mine.json
python labs/04-context-engineering/context_budget.py --file labs/04-context-engineering/requests/company_brain_mine.json
```

## עלויות

- תרגיל 3 עם `--mode all` עולה כ-3 סנט על Haiku 5.5.
- תרגיל 4 עולה כ-2 סנט, רובם על הריצה עם Haiku 4.5.
- תרגיל 5 עולה כ-3 סנט לריצה, ו-12 סנט אם מוסיפים גודל של 120K (מעל 100K טוקנים המחיר של Haiku 5.5 גדל פי 5).
- תרגיל 6 עולה פחות מסנט.
- המעבדה כולה, בפחות מ-30 סנט.

## כללים

- `--calibrate` משתמש ב-endpoint החינמי `count_tokens` של Anthropic. כל השאר נספר עם tiktoken, וזה רק קירוב. ה-tokenizer של Claude Haiku 5.5 סופר בדרך כלל יותר טוקנים מ-o200k על אותו טקסט (הסקריפטים מניחים פי 1.3 בהערכת עלות), ואת היחס האמיתי תראה עם `--calibrate`.
- תוצאות נשמרות ב-`labs/04-context-engineering/results/`, ולא נכנסות ל-git.

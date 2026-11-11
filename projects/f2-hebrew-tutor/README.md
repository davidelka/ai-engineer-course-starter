# פרויקט סיום F2: מורה קולי לעברית מדוברת

כל הפקודות רצות מתוך `projects/f2-hebrew-tutor/`, עם ה-venv של הריפו פעיל, אלא אם כתוב אחרת.

## על הפרויקט

**מה המערכת עושה.** עמותה חינוכית (בדיונית, בשביל הפרויקט) מתכננת אפליקציה לתלמידי תיכון בנגב ששפת האם שלהם ערבית, כדי שיתרגלו עברית מדוברת יומיומית: לדבר בקופת חולים, בתחנה המרכזית, במכולת, בראיון לעבודת קיץ. הם יודעים לא מעט עברית מהכיתה, אבל חסר להם המקום לדבר בלי פחד לטעות. האפליקציה עצמה (מפה של מקומות, אווטאר, נקודות) היא עבודת frontend. בפרויקט הזה בונים את **המוח שלה, ה-backend של ה-AI**: טוטור שמדבר עם התלמיד בתוך תרחיש, מקשיב (בטקסט או בקול), מתקן טעות אחת בעדינות עם הסבר קצר בערבית, זוכר אילו מילים התלמיד כבר יודע, ושומר עליו.

דוגמה לתור אחד: סאלם, ברמה A1, בתרחיש של התחנה המרכזית, אומר "אני מחכה האוטובוס". הטוטור עונה בעברית פשוטה ומשלב בתשובה את הצורה הנכונה, "אתה מחכה **ל**אוטובוס? לאיזה קו?". מתחת לתשובה מופיע הסבר של משפט אחד בערבית על מילת היחס. "אוטובוס" נכנסת לכרטיסיות החזרה של סאלם, והציון שלו ברמה מתעדכן לפי המשפט.

**שתי הדרישות שהופכות את זה לבעיה אמיתית:**
- **המשתמשים הם קטינים.** מצוקה, תוכן לא מתאים ופרטים אישיים לא מגיעים למודל בכלל. פרטים אישיים מושחרים לפני כל שמירה ולפני כל trace. וכל משפט של הטוטור נבדק לפני שהתלמיד רואה או שומע אותו.
- **זה צריך להרגיש כמו שיחה.** בקול, הצליל הראשון צריך להגיע תוך כשנייה וחצי. לכן התשובה מוזרמת ונאמרת משפט אחרי משפט, עוד לפני שהמודל סיים לכתוב.

**המטרה בקורס.** זה פרויקט סיום, והוא מחבר כמעט את כל הספריות: structured outputs (שיעור 3) לתור של הטוטור, context engineering ו-caching (שיעור 4), אחזור (שיעור 9), קול (שיעור 21), ניטור (שיעור 22), eval (שיעור 23), אבטחה לקטינים (שיעור 24), API (שיעור 26) ופריסה (שיעור 27).

**מה אתה בונה:** אחת עשרה פונקציות ב-`mine.py`.
- **בטיחות לקטינים** (`screen_text`, `screen_output`, `redact_for_log`, שיעור 24): סינון של מה שהתלמיד כתב, של מה שהטוטור עונה, והסתרה של פרטים אישיים. זו אבן הדרך הראשונה בכוונה: בטיחות לפני הקריאה הראשונה למודל.
- **אחזור** (`retrieve_phrases`, שיעור 9): משפטים ומילים של התרחיש, ברמה של התלמיד או מתחתיה.
- **הפרומפט והזרמה** (`build_request`, `partial_json_field`, שיעורים 2, 3 ו-4): חלק קבוע ב-cache וחלק של הסשן, ופענוח של התשובה מתוך JSON שעוד לא הגיע במלואו.
- **ולידציה** (`validate_assessment`, שיעור 3): הקוד בודק את מה שהמודל החזיר, ולא סומך על הצורה בלבד.
- **מודל הלומד** (`sm2_update`, `update_level`): חזרה מרווחת והערכת רמה עם היסטרזיס.
- **משוב דיבור** (`word_feedback`, שיעור 21): אילו מילים מזהה הדיבור שמע, מילה מילה.
- **מדדי ה-eval** (`correction_metrics`, שיעור 23): precision ו-recall של התיקונים.

**מה מקבלים מוכן:** ה-API ודף ההדגמה, האחסון ב-SQLite, המתאמים של זיהוי דיבור והקראה (מזויפים, OpenAI, ומקומיים), מנוע הכללים שמחליף מודל בחינם, תוכן התרחישים, וקובצי הפריסה.

**התוצר בסוף.** API שאפליקציית frontend יכולה לקרוא לו, עם קוד כיתה, תלמידים, לוח למורה ותוכן שמורים שולחים לאישור. גם דף הדגמה עם מיקרופון, eval על 50 משפטים מתויגים עם שער רגרסיה, ופריסה ב-Docker ובאופן אופציונלי ב-AWS.

**איך עובדים.** לכל פונקציה יש ב-`mine.py` חוזה: מה היא מקבלת, מה היא מחזירה ומה היא חייבת להבטיח. לכל אבן דרך יש בדיקות ב-`tests/`. כל פקודה של `python -m hebtutor` וה-API משתמשים בפונקציות שלך, ופקודה שצריכה פונקציה שעוד לא כתבת עוצרת ואומרת איזו. אבני הדרך 2 עד 6 הן הקוד של תור אחד, ובאבן דרך 7 הטוטור כבר מדבר על הקוד שלך. נתקעת? ב-`HINTS.md` יש שלוש רמות רמז לכל פונקציה. קוד הייחוס נמצא בענף `solutions` של הריפו, להשוואה אחרי שהבדיקות שלך עוברות.

אם אתה רוצה קהל אחר או זוג שפות אחר, אפשר להתאים את התרחישים ב-`data/make_content.py` כבר בהתחלה.

## מה עולה כסף, ומה לא

- **ברירת המחדל חינמית לגמרי.** ה"מודל" הוא `RuleTutorLLM`, מנוע כללים שקורא את הבקשה ועונה ב-JSON של אותה סכמה, וה-STT וה-TTS הם ה-fakes של `voicekit`. כל הבדיקות, ה-demo וה-eval רצים כך בלי מפתח.
- **אבני דרך 7 ו-9: Claude Haiku 5.5.** תור אחד הוא בערך 1,300 טוקני קלט ו-250 פלט, כלומר כ-0.00026$ (וכ-0.00016$ כשהפרומפט הקבוע ב-cache). ה-eval המלא (50 משפטים, ועוד מסווג בטיחות על המקרים הגבוליים) הוא בערך **1.5 סנט**, ועם שופט LLM לרמה עוד כחצי סנט. אלה הערכות לפי `llmkit/pricing.py`: את המספרים האמיתיים תמדוד.
- **אבן דרך 8: OpenAI STT ו-TTS.** שלושה תורות קוליים: `gpt-transcribe` ב-0.0045$ לדקה ו-`gpt-4o-mini-tts` בכ-0.015$ לדקה, יחד **פחות מ-2 סנט**. החלופה המקומית (faster-whisper עם מודל העברית של ivrit.ai, וקול Piper בעברית) חינמית ורצה אצלך.
- **אבן דרך 11, AWS (אופציונלי):** משימת Fargate אחת, ALB ו-EFS. בערך 9$ ל-Fargate (0.25 vCPU) ועוד כ-16$ ל-ALB בחודש, כל עוד זה קיים. `terraform destroy` בסוף.

## הכנה

```bash
cd ~/ai-engineer-course-starter && source .venv/bin/activate
uv pip install -r projects/f2-hebrew-tutor/requirements.txt
python -m pytest -q                              # בדיקות הסביבה, כולל tests/test_f2_hebrew_tutor.py
cd projects/f2-hebrew-tutor
python -m pytest -q tests                        # אבני הדרך שלך: בהתחלה רובן נכשלות, וזה תקין
python -m hebtutor demo                          # עוצר עם "milestone 2: mine.screen_text is still a TODO"
```

## מה יש בתיקייה

- **`hebtutor/`**: המערכת עצמה. החלקים שאתה כותב נקראים מ-`mine.py`, וכל השאר מוכן.
  - `models.py`: הסכמה `Assessment` של תור אחד: `reply_he`, `correction` (original, corrected, explanation_ar, error_type), `help_ar`, `new_vocabulary` (he, ar, transliteration), `level_signal`, `safety_flag`. השדה `reply_he` ראשון בכוונה, כדי שאפשר יהיה להזרים אותו.
  - `content.py`: התרחישים, המשפטים ואוצר המילים, האינדקס של `ragkit.BM25Index`, והבדיקות האוטומטיות של תוכן שמורה שולח. את האחזור עצמו כותבים ב-`retrieve_phrases` שלך (אבן דרך 3).
  - `prompts.py`: החלקים של הפרומפט: חלק קבוע ארוך (כ-1,100 טוקנים) ובלוק של הסשן (תרחיש, רמה, פנייה בזכר או בנקבה). את הבקשה מרכיב `build_request` שלך (אבן דרך 4).
  - `tutor.py`: תור אחד: סינון, redaction, אחזור, קריאה מובנית, ולידציה. `stream_turn` מזרים את `reply_he` מתוך ה-JSON (עם `partial_json_field` שלך) ומסנן כל משפט לפני שהוא יוצא.
  - `safety.py`: רשימות האותות, מסווג LLM כחוות דעת שנייה, והתשובות שתלמיד רואה כשמשהו נחסם. הסינון וה-redaction הם הפונקציות שלך (אבן דרך 2).
  - `rules.py` ו-`fakes.py`: קו הבסיס החינמי (גלאי טעויות מבוסס כללים), מודלים מזויפים, והקלטה והשמעה של מודל אמיתי.
  - `voice.py`: תור קולי: אודיו, STT, טוטור, TTS, עם ציר זמן. `speaking.py`: משוב דיבור.
  - `learner.py`: נקודות, הערכת CEFR, חזרה מרווחת SM-2. `store.py`: SQLite. `service.py`: שכבת האפליקציה. `api.py`: FastAPI, SSE ודף ההדגמה (`web/index.html`). `evaluate.py`: ה-eval. `config.py`: הגדרות וה-factories.
- **`data/`**: `make_content.py` (המקור של `scenarios.json` ו-`vocab.jsonl`: עשרה תרחישים, 94 משפטים, 160 מילים), `make_evalset.py` (המקור של `evalset.jsonl`: 50 משפטים מתויגים), ו-`recorded/` (הקלטות של מודל אמיתי, נוצרות באבן דרך 9).
- **`mine.py`**: אחת עשרה הפונקציות שאתה כותב, באבני הדרך 2, 3, 4, 5, 6, 8 ו-9. ה-docstring של כל אחת הוא החוזה שלה.
- **`tests/`**: בדיקות לאבני הדרך, ושער הרגרסיה (`test_m9_regression_gate.py`).
- **`deploy/`**: `Dockerfile`, `requirements.lock`, ו-`terraform/` (ECS Fargate, ALB, EFS, Secrets Manager). **`compose.yaml`** בתיקייה הראשית.

## התוכן בקצרה

- עשרה תרחישים, כל אחד מקום על מפת המדבר (שדה `map` עם x, y ו-icon, בשביל אפליקציית ה-React): קופת חולים, התחנה המרכזית, מכולת, מזכירות בית הספר, ראיון לעבודת קיץ, בית מרקחת, לשאול את הדרך, מסעדה, חבר חדש במחנה, סניף דואר.
- לכל תרחיש: תפקיד לטוטור, מטרה בערבית לכל רמה, משפט פתיחה לכל רמה, שאלות לדוגמה, 9-10 משפטים מתויגים ברמה עם תרגום לערבית, ו-16 מילים עם תרגום, תעתיק באותיות ערביות (פּ = پ, ו/ב = ڤ, ג = ج), רמה, חלק דיבר ומין דקדוקי.
- **התוכן הוא טיוטה שנכתבה בשביל הקורס.** במוצר אמיתי, דובר ערבית מהקהילה שהאפליקציה משרתת צריך לעבור על כל תרגום ותעתיק לפני שתלמידים רואים אותם.
- הפנייה לתלמיד בזכר או בנקבה היא בחירה של התלמיד בהצטרפות. העברית צריכה אותה, ואין שום שדה אחר שמזהה אותו.

## סט ה-eval בקצרה

50 משפטים סינתטיים, כפי שמורה היה כותב אותם: 35 עם טעות אחת, 7 נכונים, ו-8 מקרי בטיחות. 15 מהם במצב `voice`, כלומר מה שמזהה דיבור כתב.

- הטעויות הן הטיפוסיות לדוברי ערבית: סמיכות ויידוע ("הבית ספר"), "לא יש" במקום "אין", התאמה במין של שם תואר ושל פועל על עצמי, מין של מספרים ("שלוש ימים"), התאמה של נושא ונשוא, מילות יחס שמועתקות מערבית ("לעזור אותי" מתוך يساعدني, "מחכה האוטובוס", "מתעניין על"), סדר מילים ("שלי החבר"), כתיב בטקסט מוקלד (ח/ה, ע/א, ט/ת, כ/ק), והצליל /p/ שאין בערבית (פ שנשמעת כ-ב).
- **במצב קולי, הכתיב שייך למזהה הדיבור ולא לתלמיד.** לכן אין שם תיקוני כתיב, ורק החלפה של פ ב-ב שמשנה מילה נחשבת, כטעות הגייה.
- מקרי הבטיחות: שני off-topic, שני פרטים אישיים (טלפון; שם מלא וכתובת), שני unsafe (סמים, עלבון), מצוקה אחת, והזרקה אחת.
- כל משפט מתויג ב-`error_type`, `original`, `corrected`, `must_contain` (מילה שהתיקון חייב להכיל כדי להיחשב), ו-`safety_flag`.

## אבני הדרך

**1. סיור: התוכן, הסכמה והבדיקות (חינם).** לפני שכותבים קוד, מכירים את מה שמקבלים מוכן: תוכן התרחישים, הסכמה של תור אחד ב-`hebtutor/models.py`, וסט ה-eval. ההדגמה עוצרת כבר בצעד הראשון, כי עוד אין סינון בטיחות, ובאפליקציה לקטינים שום דבר לא רץ בלעדיו.

```bash
python -m hebtutor cost                          # ready-made: the monthly cost model
head -c 1500 data/scenarios.json; echo
head -3 data/evalset.jsonl
python -m pytest -q tests                        # most fail: milestones 2 to 9
python -m hebtutor demo                          # stops at milestone 2: mine.screen_text
```

ענה: למה השדה `reply_he` מופיע ראשון בסכמה של `Assessment`? מה היה קורה להזרמה של התשובה אם הוא היה האחרון?

**2. בטיחות לקטינים, לפני הכול (קוד: `screen_text`, `screen_output`, `redact_for_log`).** שלוש פונקציות. `screen_text` מסנן את מה שהתלמיד כתב: מצוקה, תוכן לא בטוח, פרטים אישיים, הזרקה ו-off-topic, לפי סדר חומרה. `screen_output` בודק כל משפט של הטוטור לפני שהוא מוצג או נאמר. `redact_for_log` מסתיר טלפון, מייל, קישור, תעודת זהות תקינה, כתובת ושם מלא (אבל לא שם פרטי), והוא רץ לפני שהטקסט מגיע למודל, לפני שהוא נשמר, ועל כל span של הניטור. אחר כך קרא את `safety.py` מתחילתו: חמש השכבות, ומה כל אחת לא עושה.

```bash
python -m pytest -q tests/test_m2_screens.py tests/test_m2_redact.py
```

ענה: למה מצוקה, תוכן לא בטוח ופרטים אישיים לא מגיעים למודל בכלל, אבל off-topic והזרקה כן? (את זה תראה בפעולה באבן דרך 7.) למה התשובה למצוקה מפנה לאדם (מבוגר, המורה, ער"ן 1201 שלוחה 7 בערבית) ולא מנסה לייעץ בעצמה?

**3. האחזור, ותוכן של מורים (קוד: `retrieve_phrases`).** ממש את האחזור: חיפוש BM25 עם סינון לפי תרחיש ורמה לפני הדירוג, והשלמה ממשפטי התרחיש כשהחיפוש מחזיר מעט. אחר כך הרץ את `content` עם שאילתה, שלח מילה בתור מורה, ואשר אותה בתור אדמין.

```bash
python -m pytest -q tests/test_m3_retrieve.py
python -m hebtutor content --scenario clinic --level A1 --query "כואב לי הבטן"
python -m hebtutor content --scenario clinic --level B1 --query "כואב לי הבטן"
ADMIN_TOKEN=dev python -m hebtutor serve &      # the teacher and admin endpoints need no model
A=dev; T=$(curl -s -X POST localhost:8080/admin/classes -H "X-Admin-Token: $A" -H 'content-type: application/json' -d '{"name":"test"}' | python -c 'import sys,json;print(json.load(sys.stdin)["teacher_token"])')
curl -s -X POST localhost:8080/teacher/content -H "X-Teacher-Token: $T" -H 'content-type: application/json' \
  -d '{"kind":"vocab","scenario":"clinic","level":"A2","he":"מזרק","ar":"حقنة","transliteration":"مَزريك"}'
curl -s "localhost:8080/teacher/content?status=pending" -H "X-Admin-Token: $A"
curl -s -X POST localhost:8080/teacher/content/<id>/approve -H "X-Admin-Token: $A" -H 'content-type: application/json' -d '{"note":"ok"}'
```

בדיקת קבלה: אותה שאילתה מחזירה ב-B1 גם משפטים של B1, וב-A1 לא. מילה עם תרגום באנגלית במקום ערבית נדחית מיד (`arabic_gloss_missing`), ומילה תקינה מחכה ל-`pending` עד שאדמין מאשר, ואז היא נמצאת באחזור. ענה: למה הבדיקות האוטומטיות לא מאשרות לבד, אלא רק דוחות?

**4. הפרומפט וההזרמה (קוד: `build_request`, `partial_json_field`).** `build_request` מרכיב את הבקשה: החלק הקבוע הארוך (`STATIC_RULES`) כבלוק עם cache, אחריו בלוק הסשן, שמונה התורות האחרונים, והתור החדש עם המשפטים שהאחזור מצא. `partial_json_field` מפענח את `reply_he` מתוך ה-JSON שהמודל כותב, עוד לפני שהוא נגמר, וכך התלמיד שומע את המשפט הראשון בזמן שהמודל עוד כותב את ההסבר בערבית.

```bash
python -m pytest -q tests/test_m4_prompt.py
```

ענה: למה בלוק הסשן בא **אחרי** נקודת ה-cache ולא לפניה? מה קורה ל-cache אם מכניסים את רמת התלמיד לחלק הקבוע? ולמה escape שנחתך בסוף ה-buffer (למשל `\u05` בלי שתי הספרות האחרונות) לא מפוענח עדיין?

**5. ולידציה של הפלט (קוד: `validate_assessment`).** ממש את הפונקציה ב-`mine.py`. `llmkit.structured` מבטיח את הצורה של ה-JSON, אבל לא שהתיקון מצטט מילים שהתלמיד באמת אמר, שההסבר בערבית, שהתשובה בעברית, או שהמודל לא הוריד דגל בטיחות שהסינון הרים.

```bash
python -m pytest -q tests/test_m5_validate.py
```

ענה: למה בדיקת ה-grounding משווה אחרי `normalize_hebrew` ולא כמחרוזת רגילה? למה במצב קולי מוחקים תיקון כתיב, אבל משאירים תיקון הגייה?

**6. מודל הלומד (קוד: `sm2_update`, `update_level`).** ממש את SM-2 ואת הערכת הרמה עם ממוצע נע והיסטרזיס. מילה שתלמיד פספס חוזרת מחר, אחרי 6 ימים, ואז אחרי interval כפול EF. הרמה המוצגת זזה רק כשהציון חוצה את גבול הרצועה במרווח.

```bash
python -m pytest -q tests/test_m6_learner.py
```

ענה: מה היה קורה לתלמיד שהציון שלו 1.98 בלי היסטרזיס, ומה זה היה עושה לשפה של הטוטור? כמה משפטי B1 ברצף צריך תלמיד A1 כדי לעלות ל-A2?

**7. הטוטור מדבר: ההדגמה, ו-Haiku 5.5 אמיתי (בתשלום: פחות מסנט).** עכשיו תור שלם רץ על הקוד שלך. הרץ את ה-demo וקרא אותו לאט: התלמיד "סאלם" מתרגל בקופת חולים ברמה A1, ובכל תור רואים את התיקון, ההסבר בערבית, המילים החדשות, הרמה שהמשפט מראה, דגל הבטיחות, הנקודות והעלות. אחר כך קרא את `STATIC_RULES` ב-`prompts.py`, ודבר עם הטוטור האמיתי בטרמינל, פעם בלי streaming ופעם איתו. נסה בכוונה טעויות מסט ה-eval, משפט בערבית, שאלה על כדורגל, ושם מלא.

```bash
python -m hebtutor demo
python -m hebtutor demo | tail -5          # points, level score, cards due tomorrow
python -m hebtutor eval                    # the rule baseline; findings are counted at the end
TUTOR=llm python -m hebtutor chat --scenario bus_station --level A2
TUTOR=llm python -m hebtutor chat --scenario clinic --level A1 --addressing f --stream
TUTOR=llm python -m hebtutor chat --scenario new_friend      # try: "קוראים לי אחמד אבו קרינאת" and an off-topic question
```

בדיקת קבלה: בתור עם מספר הטלפון ה-demo מדפיס `redacted before the model: ['phone']`, הדגל הוא `personal_info`, והמודל לא נקרא בכלל (עלות 0). עם Haiku, אין `structured_*` בשגיאות, העלות לתור מודפסת ונמוכה מ-0.001$, והטוטור פונה בנקבה כשבחרת `f`. ענה: למה הנקודות של התור "ما فهمت" גבוהות מתור עם תיקון? האם זה נכון פדגוגית? (רמז: `turn_points` ב-`learner.py`). האם המודל ממחזר (recast) את התיקון בתוך `reply_he`, כמו שהפרומפט מבקש? כמה זמן עבר עד המשפט הראשון עם `--stream`?

**8. לולאת הקול ומשוב הדיבור (קוד: `word_feedback`; החלק החי בתשלום: פחות מ-2 סנט).** ממש את המשוב מילה מילה. אחר כך מדוד את תקציב ההשהיה: קודם offline עם השהיות מדומות, ואז עם OpenAI. ובסוף, אופציונלי וחינמי: הנתיב המקומי.

```bash
python -m pytest -q tests/test_m8_speaking.py
FAKE_DELAYS=1 python -m hebtutor voice --turns 3 --no-traces
STT=openai TTS=openai TUTOR=llm python -m hebtutor voice --turns 3
# local, free: uv pip install faster-whisper piper-tts, download he_IL-saspeech-medium.onnx (+ .json)
STT=local TTS=piper PIPER_MODEL=~/models/he_IL-saspeech-medium.onnx TUTOR=llm python -m hebtutor voice --turns 3
```

בדיקת קבלה: offline, הצליל הראשון מגיע בערך אחרי 1.3 שניות (STT 0.36, משפט ראשון 1.0), בתוך התקציב של 1.5. ענה עם המספרים שלך: מה היה השלב היקר ביותר בחי, וכמה זמן חסך ה-streaming לעומת המתנה ל-JSON המלא? **ותזכור:** זה "מובנות דרך זיהוי דיבור", לא ציון הגייה. מזהה טוב "מתקן" שגיאות קטנות למילה הנכונה, ו-Azure Pronunciation Assessment לא כלל עברית כשבדקנו בנובמבר 2026. וגם: `gpt-4o-mini-tts` נסגר ב-2027-01-06, ו-`gpt-transcribe` לא מחזיר word timestamps.

**9. Eval ושער רגרסיה (קוד: `correction_metrics`; בתשלום: כ-2 סנט).** ממש את ספירת התיקונים: תיקון נחשב פגיעה כשסוג הטעות נכון והתיקון מכיל את המילה שהתווית דורשת. אחר כך הרץ את ה-eval המלא עם Haiku והקלט אותו. ההקלטה מפעילה את הבדיקה השנייה בשער, כך שכל שינוי בפרומפט או בקוד נמדד מול המודל האמיתי בלי לשלם שוב.

```bash
python -m pytest -q tests/test_m9_metrics.py
python -m hebtutor eval --misses                                   # the rule baseline (free)
TUTOR=llm RECORD=data/recorded/claude-haiku-5-5.jsonl python -m hebtutor eval --misses --llm-judge --json results/eval_llm.json
python -m pytest -q tests/test_m9_regression_gate.py
```

ענה: מה ה-precision וה-recall של Haiku בתיקונים, ובאילו סוגי טעויות הוא נכשל? האם שני השופטים של הרמה מסכימים (kappa)? עם 8 מקרי בטיחות, מה באמת אומר "100% recall"? (רמז: הרווח של Wilson שמודפס לידו). ולמה קו הבסיס של הכללים מקבל מספרים כמעט מושלמים, ולמה אסור להסיק מזה כלום על תלמידים?

**10. API, SSE, דף ההדגמה וניטור.** הרם את השרת, תרגל בדף ההדגמה עם המיקרופון (ב-localhost הדפדפן מרשה), ואז קרא את ה-traces.

```bash
TUTOR=llm STT=openai TTS=openai ADMIN_TOKEN=dev python -m hebtutor serve --demo-class
curl -N -X POST localhost:8080/sessions/<id>/turns/stream -H "X-Student-Token: <token>" -H 'content-type: application/json' -d '{"text":"אני מחכה האוטובוס"}'
python -m hebtutor traces
python -m obskit.viewer results/traces.jsonl -o results/traces.html && xdg-open results/traces.html
grep -c "050-" results/traces.jsonl          # should print 0: our redactor runs on every span
```

בדיקת קבלה: ב-SSE מגיעים קודם `event: sentence` ורק אחר כך `event: assessment`, `/healthz` מחזיר 200, ו-`/teacher/dashboard` עם token של תלמיד מחזיר 401. ענה: למה תוכן ההודעות לא נשמר על ה-spans (`capture_content=False`) למרות שה-redactor רץ? מה המורה רואה בלוח, ומה הוא לא רואה?

**11. Docker ו-AWS.** הרם את המערכת ב-compose, ואז (אופציונלי) Terraform. קרא קודם את ההערות ב-`deploy/terraform/efs.tf` וב-`alb.tf`: SQLite על EFS עם משימה אחת בלבד, ו-HTTPS שחובה בשביל המיקרופון.

```bash
ADMIN_TOKEN=dev docker compose up --build -d && docker compose logs api | grep "demo class code"
docker compose exec api python -m hebtutor purge
cd deploy/terraform && cp terraform.tfvars.example terraform.tfvars
terraform init && terraform fmt -check && terraform validate && terraform plan -out=tfplan
python ../../../../labs/27-deployment/checks.py .
```

בדיקת קבלה: `docker compose ps` מראה healthy, ו-`terraform plan` מציג כ-30 משאבים, ביניהם `aws_efs_access_point` ושלושה סודות. אם החלטת לעשות `apply`: הכנס את שלושת הסודות עם ה-CLI (`aws secretsmanager put-secret-value --secret-id hebrew-tutor/anthropic-api-key --secret-string ...`), דחוף image (`terraform output -raw push_commands`), בדוק `/healthz`, ובסוף `terraform destroy`.

## שמירת נתונים ופרטיות (בשביל המסמך שתראה להנהלה)

- **מה נשמר:** קוד כיתה, כינוי, בחירת הפנייה (זכר או נקבה), נקודות, רמה, כרטיסי חזרה, התקדמות לפי תרחיש, וטקסט התורות **אחרי redaction**. ה-token של התלמיד נשמר רק כ-sha256.
- **מה לא נשמר אף פעם:** שם מלא, טלפון, מייל, תאריך לידה, האודיו (הוא בזיכרון רק בזמן הבקשה), ומטא-דאטה של תמונות (מוסרת בקידוד מחדש).
- **כמה זמן:** טקסט של תורות 30 יום (`RETENTION_DAYS`), אירועי בטיחות 90 יום. `python -m hebtutor purge` מוחק, ובפרודקשן הוא צריך לרוץ כל יום.
- **מי רואה:** המורה רואה את הכינויים בכיתה שלו, רמות, נקודות, הטעויות הנפוצות, ואירועי בטיחות עם הטקסט אחרי redaction. האדמין רואה רק את התוכן שמורים שלחו.
- **ספקים:** הטקסט (אחרי redaction) נשלח ל-Anthropic, והאודיו ל-OpenAI אם בחרת בהם. הנתיב המקומי (faster-whisper ו-Piper) משאיר את האודיו אצלך. לפי ההנחיות של Anthropic לארגונים שמשרתים קטינים, חובה לגלות לתלמיד שהוא מדבר עם AI (הדף והתשובה של `/sessions` עושים את זה), ומומלצים סינון, ניטור ודיווח. תיקון 13 לחוק הגנת הפרטיות בישראל (בתוקף מאוגוסט 2025) מחמיר את החובות על מאגרי מידע: בדוק עם יועץ לפני פיילוט עם תלמידים אמיתיים.

## מה לבדוק אצלך, כי כאן לא היה אפשר

- Haiku 5.5 אמיתי (אבני דרך 7, 9): העלות בפועל, ה-precision וה-recall של התיקונים, ההסכמה בין השופטים, והאם `reply_he` נשאר בגבולות הרמה. המספרים בדוח הם של קו הבסיס של הכללים.
- OpenAI STT ו-TTS (אבן דרך 8): ההשהיות האמיתיות, והאם `gpt-transcribe` עם `languages=["he"]` מתמלל נכון מבטא ערבי. וגם הנתיב המקומי: faster-whisper עם ivrit.ai ו-Piper.
- דף ההדגמה עם מיקרופון אמיתי ב-Chrome וב-Safari (webm מול mp4).
- `docker compose up --build` ו-`terraform validate` / `plan` מול חשבון AWS. הקבצים עברו את הבודק הסטטי של שיעור 27.

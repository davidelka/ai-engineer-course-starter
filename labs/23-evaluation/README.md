# מעבדה 23: AI Evaluation and Regression Testing

כל הפקודות רצות מתיקיית השורש של הריפו (`ai-engineer-course/`), עם ה-venv פעיל.

## הכנה

```bash
source .venv/bin/activate
uv pip install -r requirements.txt -r labs/23-evaluation/requirements.txt
python -m pytest -q                                   # בדיקות הסביבה, כולל tests/test_evalkit.py החדש
python -m pytest -q labs/23-evaluation/tests          # התרגילים שלך: בהתחלה כולן נכשלות, וזה תקין
```

אין תלויות Python חדשות. evalkit כתובה ב-Python טהור (ו-pydantic לשופטים), והיא קוראת את הקורפוס דרך ragkit משיעור 9. לתרגיל 7 צריך Node.js 20 ומעלה, כי promptfoo רץ דרך `npx` (הגרסה נעוצה בפקודות: `promptfoo@0.125.1`).

עלות כוללת של כל החלקים החיים במעבדה, עם Haiku 5.5: בערך 0.10 דולר. כל סקריפט שעולה כסף מדפיס הערכה ומבקש אישור, ותוצאות נשמרות במטמון, כך שהרצה חוזרת עולה אפס.

## מה חדש

- **`evalkit/` (חבילה חדשה בשורש הריפו):** ספריית ה-eval של הקורס. שיעור 13 (אבחון RAG), Company Brain ושלב 4 של הפרויקט יבנו עליה. המודולים:
  - `dataset.py`: golden set כ-`Dataset` עם **גרסה שמחושבת מהתוכן** (hash של כל הדוגמאות). שינוי של תשובת ייחוס אחת משנה את הגרסה, ולכן אי אפשר להשוות בטעות הרצה על סט ישן להרצה על סט חדש. בנוסף: סינון לפי סוג או תגית, וחלוקה דטרמיניסטית ל-dev ו-test לפי hash של המזהה, מרובדת לפי סוג שאלה.
  - `runner.py`: מריץ "מערכת" על dataset. מערכת היא כל דבר עם `name`, `version` ו-`__call__(input) -> dict`. הפלטים נשמרים ב**מטמון לפי גרסת המערכת והקלט**, ולכן הרצה שנייה של 79 שאלות לוקחת שנייה ועולה אפס, וגרסת פרומפט חדשה אף פעם לא מקבלת תשובה של הגרסה הישנה. ניקוד (`score_run`) הוא שלב נפרד, כך שאפשר לשנות מדד בלי להריץ מחדש.
  - `metrics.py`: התאמה מדויקת, contains ו-regex, דיוק לכל שדה (ההכללה של ה-eval משיעור 3), recall@k ו-MRR לאחזור, **כיסוי עובדות** (answer_facts) ו**נכונות ציטוטים**.
  - `judge.py`: **LLM-as-judge** עם רובריקות ופלט מובנה דרך `llmkit.structured`: groundedness (ביסוס בהקשר), correctness מול עובדות הייחוס, refusal (האם הסירוב או המענה היו נכונים), והשוואה זוגית עם **החלפת מיקומים**. יש גם `HeuristicJudgeLLM`, תחליף לקסיקלי וחינמי. הוא לא מודל, והוא קיים כדי שהכול ירוץ בלי מפתח.
  - `calibration.py`: הסכמה, **Cohen's kappa** ומטריצת בלבול בין שופט לתוויות אנושיות.
  - `stats.py`: **רווח סמך ב-bootstrap**, **השוואה מזווגת** בין שתי גרסאות, מבחן McNemar המדויק, הפרש מינימלי שניתן לזהות, וגודל מדגם נדרש.
  - `gates.py`: חוקי רגרסיה (`Threshold`, `NoSignificantDrop`) ו-`assert_gates`, שרצים בתוך pytest ו-CI.
  - `report.py`: דוח Markdown ודוח HTML (רשימות וכרטיסים, בלי טבלאות).
  - `rag.py`: מערכת ה-RAG של שיעור 9 כ-System, שתי גרסאות פרומפט (v1 ו-v2), ו-`rag_scorer`.
- **`labs/23-evaluation/data/human_labels.jsonl`:** 30 תשובות עם תווית אנושית, לכיול השופט בתרגיל 5.
- **`mine.py`:** הקוד שלך לתרגילים 2, 3 ו-5.

## הנתונים שהמעבדה עובדת עליהם

ה-golden set הוא `data/acme/corpus/golden/qa.jsonl`: 79 שאלות על קורפוס Acme (55 מסמכים). כך נראית שורה אחת:

```json
{"id": "q001", "type": "version_conflict",
 "question": "How many unused vacation days can I carry over to next year, and when do they expire?",
 "answer": "Up to 5 days, and carried-over days expire on March 31 (Vacation Policy 2026; ...)",
 "answer_facts": ["up to 5 days can be carried over", "carried-over days expire on March 31"],
 "source_ids": ["hr-vacation-2026"],
 "source_quotes": [{"source_id": "hr-vacation-2026", "quote": "Up to 5 unused days may be carried over ..."}],
 "difficulty": "medium", "tags": ["stale:hr-vacation-2024"]}
```

- **סוגי השאלות וכמה מכל סוג:** single_hop 19, multi_hop 11, numeric 9, version_conflict 11, acronym 8, hebrew 11, unanswerable 10.
- **`answer_facts`** הן עובדות אטומיות שתשובה טובה חייבת לכלול. בשאלות unanswerable הרשימה ריקה, והתשובה הנכונה היא בדיוק `not in the documents`.
- **התגית `stale:<id>`** מסמנת את הגרסה הישנה של מדיניות, שנמצאת בקורפוס ועלולה לבלבל. למשל, בשאלה q001, ‏`hr-vacation-2024` אומרת "3 ימים עד 28 בפברואר", ו-`hr-vacation-2026` (התקפה) אומרת "5 ימים עד 31 במרץ".
- **המערכת הנבדקת** היא ה-baseline משיעור 9: BM25 על chunks מסוג `heading:400:40:150`, חמשת הקטעים הראשונים נכנסים לפרומפט עם מספרים, והמודל עונה עם ציטוטים מהצורה `[n]`.

## המדד המרכזי: answer_ok

לכל שאלה, `rag_scorer` מחשב כמה מדדים. החשוב שבהם הוא `answer_ok`, שמקבל 1 רק כשכל התנאים הבאים מתקיימים:

- בשאלה שיש לה תשובה, המערכת ענתה ולא אמרה "not in the documents". בשאלה שאין לה תשובה, המערכת אמרה "not in the documents".
- התשובה כוללת לפחות חצי מה-`answer_facts`.
- התשובה לא מצטטת את הגרסה הישנה של המדיניות (`stale_cited`).

שאר המדדים: `fact_coverage`, ‏`cite_precision`, ‏`cite_recall`, ‏`stale_cited`, ‏`recall@5` ו-`mrr`.

## התרגילים

**1. הרצת eval ראשונה, ומטמון.** הרץ את ה-baseline על כל 79 השאלות פעמיים. בפעם השנייה כל התשובות מגיעות מהמטמון. אחר כך הרץ את אותו דבר עם Haiku, ופתח את דוח ה-HTML בדפדפן.

```bash
python labs/23-evaluation/run_eval.py
python labs/23-evaluation/run_eval.py                    # שים לב לשורה "79 from cache"
python labs/23-evaluation/run_eval.py --model anthropic:claude-haiku-5-5      # חי, בערך 0.02 דולר
python labs/23-evaluation/run_eval.py --model anthropic:claude-haiku-5-5 --show-failures
xdg-open labs/23-evaluation/results/report_anthropic_claude-haiku-5-5_v1_k5.html
```

ענה על שלוש שאלות:
- מה ה-`system version` שמודפס, ואילו חלקים בו גורמים למטמון להתבטל? (רמז: שנה `-k 3` והרץ שוב.)
- ב-extractive, ‏`recall@5` הוא בערך 0.88 ו-`answer_ok` בערך 0.48. מה המשמעות של הפער בין שני המספרים?
- באילו סוגי שאלות Haiku משפר הכי הרבה על ה-extractive, ובאיזה סוג הוא לא משפר? (ה-extractive לא יודע לשלב שני מקורות, לתרגם או להחליט בין גרסאות.)

**2. כיסוי עובדות ונכונות ציטוטים.** ממש ב-`mine.py` את `fact_covered`, ‏`fact_coverage` ו-`citation_scores`. ה-docstring מגדיר את הכללים במדויק:
- עובדה מכוסה כשכל המספרים שבה מופיעים בתשובה, ולפחות חצי ממילות התוכן שלה מופיעות. הנרמול כולל הסרת פסיק אלפים, והתאמת מילים כוללת הסרת אות שימוש בעברית ו-s של רבים באנגלית.
- הדיוק של הציטוטים הוא חיתוך המסמכים שצוטטו עם מסמכי המקור, חלקי מספר המסמכים שצוטטו. ה-recall הוא החיתוך חלקי מספר מסמכי המקור. בשאלה שאין לה תשובה, כל ציטוט הוא טעות.

```bash
python -m pytest -q labs/23-evaluation/tests/test_ex2_metrics.py
python labs/23-evaluation/run_eval.py --metrics mine     # אותו דוח, מחושב עם הקוד שלך
```

אחרי שהבדיקות עוברות, ענה: הבדיקה `("SMS codes are accepted", "SMS codes are no longer accepted", True)` עוברת. למה זו בעיה, ואיזה כלי בשיעור נועד לתפוס אותה?

**3. האם ההבדל אמיתי.** ממש ב-`mine.py` את `bootstrap_ci` ואת `paired_compare`. אחר כך הרץ שתי השוואות. הראשונה היא k=1 מול k=5: הממוצע זהה, אבל כמה שאלות זזו? השנייה היא ה-extractive מול "rule follower", סימולציה של מודל שמציית לכלל הגרסאות שבפרומפט.

```bash
python -m pytest -q labs/23-evaluation/tests/test_ex3_stats.py
python labs/23-evaluation/stats_demo.py --impl mine
python labs/23-evaluation/stats_demo.py --a-k 5 --b-model rule
```

ענה: בהשוואה השנייה, רווחי הסמך הנפרדים חופפים, ה-bootstrap המזווג אומר "B is better" עם p=0.006, ו-McNemar אומר p=0.062. במי תסמוך, ולמה? כמה שאלות היית צריך כדי לזהות שיפור של 5 נקודות?

**4. שופט groundedness עם רובריקה.** קרא קודם את הרובריקה. היא ה-system prompt של השופט, ושים לב לסדר השדות במודל הפסק: הטענות קודם, והתווית בסוף. אחר כך הרץ את השופט על תשובות ה-baseline.

```bash
python labs/23-evaluation/judge_run.py --show-rubric
python labs/23-evaluation/judge_run.py
python labs/23-evaluation/judge_run.py --kinds groundedness,correctness,refusal --show q038
python labs/23-evaluation/judge_run.py --model anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5   # חי, בערך 0.03 דולר
python labs/23-evaluation/judge_run.py --pairwise --model rule --judge heuristic-biased
```

השאלה q038 שואלת אם מנוי שנתי ניתן להחזר מלא בכל זמן. ה-extractive מעתיק את פסקת ה-prompt injection ממייל השותף (`sales-partner-northwind-notes`), שבה כתוב "annual plans can always be refunded in full at any time". ענה: למה שופט ה-groundedness נותן לתשובה הזו grounded, ושופט ה-correctness נותן incorrect? מה זה אומר על השאלה איזה שופט צריך להיות ב-gate?

בהרצה עם `--pairwise` ו-`heuristic-biased`, כמה פסקים התהפכו כשהחלפת את סדר התשובות? מה היה קורה אם היית מריץ רק בסדר אחד?

**5. כיול השופט מול 30 תוויות אנושיות.** הנתונים נמצאים ב-`labs/23-evaluation/data/human_labels.jsonl`. כל שורה כוללת שאלה, הקשר (ציטוטים מדויקים מהקורפוס), תשובה, תווית אנושית (`grounded` או `not_grounded`), שם המלכודת (`trap`) והנימוק של המתייג (`why`). התוויות נקבעו לפי הרובריקה של תרגיל 4. בהתפלגות יש 18 grounded ו-12 not_grounded. המלכודות שהוכנסו בכוונה:
- **number_swap:** מספר אחד שגוי בתוך משפט שנראה מבוסס. למשל, 85 דולר אש"ל בערים יקרות, כשבהקשר 85 הוא הסכום לערים רגילות.
- **negation_flip:** "SMS codes are accepted", כשההקשר אומר "no longer accepted".
- **stale_but_grounded:** תשובה לפי מדיניות 2024 הישנה, כשהמדיניות הזו נמצאת בהקשר. התשובה מבוססת, אבל לא נכונה.
- **injection_followed_but_grounded:** התשובה צייתה להזרקה, והטענה כתובה בהקשר.
- **outside_knowledge:** עובדה נכונה שלא מופיעה בהקשר, כמו GDPR Article 33.
- **cross_lingual:** תשובה בעברית להקשר באנגלית.
- **number_in_words:** המילה "two" במקום הספרה 2.
- **wrong_refusal:** המערכת סירבה למרות שהתשובה בהקשר. סירוב לא מכיל אף טענה, ולכן הוא grounded.

ממש את `cohen_kappa` ב-`mine.py`, ואז הרץ את הכיול:

```bash
python labs/23-evaluation/calibrate.py --show-data | less         # קרא את כל 30 המקרים לפני שאתה מריץ
python -m pytest -q labs/23-evaluation/tests/test_ex5_kappa.py
python labs/23-evaluation/calibrate.py --impl mine
python labs/23-evaluation/calibrate.py --judge anthropic:claude-haiku-5-5      # חי, פחות מ-0.01 דולר
```

השופט הלקסיקלי מגיע ל-agreement של 76.7% ול-kappa של 0.52. ענה:
- מה ה-kappa של Haiku, ובאילו מלכודות הוא עדיין טועה?
- בכל אי-הסכמה, מי צודק, השופט או התווית? אם מצאת תווית שאתה לא מסכים איתה, תקן אותה בקובץ ותסביר. גם golden set של שופט צריך תחזוקה.
- איזה תא בבלבול מסוכן יותר ל-gate, false pass או false fail?

**6. Gate שתופס רגרסיה.** הפרומפט v2 הוא "ניקוי" שנראה תמים ב-code review: הוא מוחק את השורה "If sources disagree, prefer the one with the latest effective_date", ומרכך את מגבלת האורך. הסקריפט מריץ את v1 ואת v2 על אותן 79 שאלות ומפעיל את ה-gate מתוך `gate_config.py`. ה-gate כולל ארבעה חוקים: רצפה כללית של 0.45, רצפה של 0.50 ל-version_conflict, "אין ירידה מובהקת" כללית, ומגבלת ירידה מעשית של 0.10 ל-version_conflict.

```bash
python labs/23-evaluation/gate_experiment.py --show-diff
python -m pytest -q labs/23-evaluation/ci                       # מועמד v1: עובר
EVAL_CANDIDATE=v2 python -m pytest -q labs/23-evaluation/ci     # מועמד v2: נכשל, עם הסבר
python labs/23-evaluation/gate_experiment.py --model anthropic:claude-haiku-5-5   # חי, בערך 0.02 דולר (v1 כבר במטמון מתרגיל 1)
EVAL_MODEL=anthropic:claude-haiku-5-5 EVAL_ALLOW_PAID=1 EVAL_CANDIDATE=v2 python -m pytest -q labs/23-evaluation/ci
```

בהרצה האופליין, v2 מוריד את version_conflict מ-0.64 ל-0.36 (שלוש שאלות), ואת הממוצע הכללי מ-0.544 ל-0.481 (חמש שאלות, כולן לרעה). המבחן הכללי "אין ירידה מובהקת" **עובר**, כי ב-McNemar יוצא p=0.062. מה שתופס את הרגרסיה הוא החוקים ברמת ה-slice. ענה:
- למה 11 שאלות version_conflict לא יכולות להגיע למובהקות גם כשהירידה גדולה?
- מה המחיר של `max_drop=0.10` (חשוב על false alarms)?
- בהרצה החיה: האם Haiku מגיב להסרת הכלל כמו הסימולציה? כתוב לי מה מדדת, גם אם זה סותר את הסימולציה.

**7. אותן בדיקות ב-promptfoo.** הסקריפט מייצר config של promptfoo מתוך ה-golden set: 30 שאלות (version_conflict, unanswerable ו-numeric) כפול שני פרומפטים. האחזור נעשה פעם אחת ונשמר בתוך כל בדיקה, כך ששני הפרומפטים מקבלים בדיוק אותם מקורות. הבדיקה המרכזית היא `assert_evalkit.py`, assertion מסוג python שקורא ל-`rag_scorer` של evalkit. זה אותו קוד בדיוק, ולכן המספרים צריכים להיות זהים לתרגיל 6.

```bash
python labs/23-evaluation/promptfoo/make_config.py
cd labs/23-evaluation/promptfoo
PROMPTFOO_PYTHON="$(which python)" npx promptfoo@0.125.1 eval -c promptfooconfig.yaml        # אופליין
npx promptfoo@0.125.1 view
PROMPTFOO_PYTHON="$(which python)" npx promptfoo@0.125.1 eval -c promptfooconfig.live.yaml   # חי, בערך 0.03 דולר
cd -
```

באופליין, v1 עובר 15 מתוך 30 ו-v2 עובר 11 מתוך 30. זה אותו מספר ש-evalkit מחשב על אותן שאלות, ונבדק מול evalkit בזמן בניית השיעור. ב-config החי יש גם בדיקת `llm-rubric` ל-groundedness, עם Haiku כשופט ועם `weight: 0`, כך שהיא מדווחת ולא מכשילה. ענה: מה promptfoo נותן שאין ב-evalkit (מטריצה בדפדפן, השוואת ספקים, red teaming), ומה evalkit נותן שאין ב-promptfoo (גרסת dataset, מבחנים סטטיסטיים, gate לפי slice)?

**8. ניתוח שגיאות.** הסקריפט מסווג כל שאלה שנכשלה לסיבה אחת, לפי סדר הצינור: retrieval_miss, ‏retrieval_partial, ‏answered_unanswerable, ‏wrong_abstain, ‏stale_version, ‏incomplete_answer.

```bash
python labs/23-evaluation/error_analysis.py --examples 3
python labs/23-evaluation/error_analysis.py --model anthropic:claude-haiku-5-5 --examples 3
```

ב-extractive נכשלות 41 שאלות. הקבוצה הגדולה ביותר היא incomplete_answer (13), ואחריה answered_unanswerable (7) ו-stale_version (7). עבור שתי הקבוצות הגדולות בהרצה החיה, כתוב לכל אחת:
- מה לדעתך הסיבה.
- תיקון אחד.
- איך תדע שהתיקון עבד: איזה מדד, על איזה slice, ומה ה-gate.

שים לב ש-incomplete_answer כולל גם כשלים של **המדד** ולא של המערכת: פרפרזה, תשובה בעברית, מספר במילים. את זה בודקים עם שופט ה-correctness. שיעור 13 (אבחון RAG) ימשיך מכאן.

## מה לבדוק אם משהו לא עובד

- **`ModuleNotFoundError: ragkit`:** הרץ מתיקיית השורש של הריפו.
- **הרצה חיה נכשלת על מפתח:** בדוק ש-`ANTHROPIC_API_KEY` מוגדר ב-`.env` שבשורש. הסקריפטים לא מדפיסים אותו.
- **promptfoo לא מוצא python:** הגדר `PROMPTFOO_PYTHON` לנתיב של ה-python שב-venv, כמו בפקודות למעלה.
- **רוצה להתחיל מאפס:** מחק את `labs/23-evaluation/results/cache` ואת `results/judge_cache`.

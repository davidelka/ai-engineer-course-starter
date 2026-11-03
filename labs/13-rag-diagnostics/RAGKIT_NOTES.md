<!-- For the orchestrator: paste the section below into ragkit/README.md, after "## שיעור 12" (or after
     "## שיעור 10" if lesson 12's section is not merged yet). Also suggested: in "## נקודות הרחבה לשיעורים הבאים",
     change the "Evaluation (שיעור 13)" bullet to "(שיעור 13, מומש: ragkit/diagnose.py; השופט המלא והסטטיסטיקה
     בשיעור 23, evalkit)". Optional ragkit/__init__.py _LAZY entries: "classify": ("ragkit.diagnose", "classify"),
     "check_claims": ("ragkit.diagnose", "check_claims"). No existing ragkit/evalkit/obskit file was changed. -->

## שיעור 13: אבחון כשלים ו-groundedness

`ragkit/diagnose.py` עובד על מידע פשוט: מזהי מסמכים, טקסטים ומילונים. לכן אפשר לאבחן גם trace שהוקלט בייצור, בלי להריץ מחדש. הוא משתמש ב-`ragkit.evaluate` (כיסוי ציטוטים), ב-`ragkit.rag` (הפרומפט והציטוטים), ב-`ragkit.replay` (שופט לא מקוון), ב-`llmkit.structured` (השופט החי), וב-`evalkit.metrics.fact_coverage`. את evalkit הוא טוען רק בתוך הפונקציות שצריכות אותו.

- **הטקסונומיה:** `STAGES` מכיל 12 שלבי כשל לפי סדר הצנרת:
  - ingestion: `missing_from_corpus`, `extraction_lost`, `chunk_split`.
  - retrieval: `not_retrieved`, `ranked_low`, `stale_version`.
  - generation: `false_refusal`, `lost_in_middle`, `ignored_context`, `hallucination`, `wrong_citation`, `failed_to_refuse`.
  
  `FIXES[stage]` נותן את התיקון, את השיעור שבו הוא נלמד ואת המדד שמראה שהוא עבד.
- **`Case` ו-`classify(case)`:** הנוהל עונה קודם על השאלה "האם התשובה עברה?", ואחר כך עובר על הצנרת לפי הסדר. השלב הראשון שנכשל הוא שורש הבעיה, ושאר הבעיות נשמרות כדגלים (`Diagnosis.flags`). `Diagnosis.path` מתעד את השאלות שנשאלו בדרך. `MIN_FACTS=0.5`, ו-`LONG_CONTEXT=4000` טוקנים, הסף שמתחתיו "lost in the middle" לא נחשב סיבה סבירה.
- **מדדים לפי שלב, מציטוטי הזהב:**
  - `context_recall`: ציטוטים שנמצאים בשלמותם בפרומפט, חלקי מספר הציטוטים.
  - `context_precision`: מודע לדירוג, כמו ב-Ragas: ממוצע של precision@k במקומות הרלוונטיים.
  - `simple_precision`: chunks רלוונטיים חלקי k, כמו ב-RAGChecker.
  - `citation_precision` ו-`citation_recall`: ברמת chunk, לפי ציטוטי הזהב.
  - `quote_locations` ו-`relevance_from_quotes`: פונקציות עזר.
- **`check_claims(answer, contexts, llm)`:** שתי קריאות מובנות: `Claims` ואחריה `ClaimVerdicts`, כשהראיה נכתבת לפני פסק הדין. אחר כך `evidence_in_context` מוודא בקוד שהראיה באמת במקור, וטענה עם ראיה מומצאת לא נספרת כנתמכת. סירוב לא עולה אף קריאה. שגיאת JSON מוחזרת כ-`error` ולא נזרקת. `GroundednessReport` מספק `score` (faithfulness), `label` (grounded, partially_grounded או not_grounded) ו-`unsupported`.
- **`heuristic_judge_llm()`:** `llmkit.LLM` אמיתי שה-transport שלו מקומי, עם `heuristic_claims_responder`. הוא לקסיקלי: מילים משותפות, מספרים ושלילה בחלון של המשפט. הוא עיוור לפרפרזה ולתרגום, ולכן משמש לבדיקת הצנרת ולא למדידה.
- **`NLIChecker(model=NLI_DEFAULT)`:** `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` (MIT, כ-0.3 מיליארד פרמטרים, 27 שפות כולל עברית). הוא צריך transformers ו-torch, ונטען רק כשמשתמשים בו. אפשר להעביר לו `predict=` מזויף בבדיקות.
- **הרצה:**
  - `trace_question` מבצע חיפוש עמוק אחד (depth=50): הוא נותן את המועמדים, ו-k הראשונים שלו הם הפרומפט. אחריו באים התשובה, הציטוטים, כיסוי העובדות והשופט, וה-trace נשמר כ-dict שאפשר לכתוב ל-JSON.
  - `run_diagnosis`, `case_from_trace`, `trace_metrics`, `save_traces` ו-`load_traces`.
  - `breakdown`, `funnel`, `format_breakdown`, `format_funnel` ו-`format_diagnosis` מדפיסים רשימות, לא טבלאות.
  - `to_evalkit_run` ממיר הרצה ל-`evalkit.Run`: `answer_ok`, ציון של 0 או 1 לכל שלב (`stage:<name>`), והמדדים. כך ה-gates וה-McNemar של שיעור 23 עובדים עליה כפי שהם.

נקודות הרחבה:
- **שלב כשל חדש** (למשל `permission_filtered` ב-Company Brain: המסמך בקורפוס, אבל לא במועמדים של המשתמש הזה): מוסיפים אותו ל-`STAGES` במקום הנכון בסדר, מוסיפים תנאי ב-`classify` ו-`Fix` ב-`FIXES`.
- **traces מייצור** (שיעור 22): span של retrieval ו-span של LLM נושאים את אותם שדות (מזהי מסמכים, טקסט הפרומפט, התשובה). ממירים אותם ל-dict בפורמט של `trace_question`, ו-`case_from_trace` עובד עליהם.
- **שופט אחר:** כל `llmkit.LLM` עובד עם `check_claims`. כדי לכייל אותו מול תוויות של אדם, משתמשים ב-`evalkit.calibration` (שיעור 23).

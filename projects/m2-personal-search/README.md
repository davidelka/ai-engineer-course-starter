# פרויקט אמצע M2: חיפוש חכם במסמכים האישיים שלך

כל הפקודות רצות מתוך `projects/m2-personal-search/`, עם ה-venv של הריפו פעיל, אלא אם כתוב אחרת. כדאי להגדיר פעם אחת `alias pss="python -m pss"`.

בתיקיית המסמכים שלך יש קבלות, תעודות אחריות, חוזה שכירות, מכתבים מבית הספר של הילדים, סיכומי קורסים, מתכונים והזמנות לטיול, בעברית ובאנגלית, ב-PDF, ב-Word, בהערות טקסט ובדפים ששמרת מהדפדפן. הפרויקט בונה כלי שמחפש בהם לפי מילים ולפי משמעות, עונה על שאלות עם הפניה לקובץ ולעמוד, ושומר עליהם: **הכול רץ על המחשב שלך כברירת מחדל**. מודל בענן הוא בחירה מפורשת, ורק אחרי שלוש שכבות הגנה: מקורות מתיקיות מוגנות לא נשלחים בכלל, מה שנשלח עובר redaction, וכל בית שיוצא נכתב קודם ליומן יציאה.

ההבדל מ-M1: שם הקורפוס הוא מסמכי החברה Acme והשאלה היא איכות תשובות. כאן הקורפוס הוא הקבצים שלך, והשאלות הן אחרות: מה מותר בכלל לקרוא, איך מחלצים טקסט מ-PDF עברי אמיתי, איך האינדקס נשאר מעודכן כשאתה עובד, ומה בדיוק יוצא מהמחשב.

## מה עולה כסף, ומה לא

- **כמעט הכול חינם ומקומי.** ה-embeddings (multilingual-e5-small), ה-OCR (Tesseract) והמודל המקומי (Ollama) רצים על המחשב. הבדיקות משתמשות ב-embedder מזויף (hashing, לקסיקלי, **לא סמנטי**) וב-`ExtractiveAnswerer` של ragkit (בוחר משפטים, **לא מודל שפה**), כדי שירוצו בכל מקום בלי הורדות.
- **אבן דרך 8 בלבד: Claude Haiku 5.5 (אופציונלי).** שאלה אחת שולחת כ-2,500 עד 3,500 תווים (הוראות וחמישה מקורות), כלומר כ-1,000 טוקנים, ועוד כ-150 טוקני תשובה: לפי `llmkit/pricing.py` (0.10$ למיליון טוקני קלט, 0.50$ לפלט) זה כ-**0.0002$ לשאלה**. עשר שאלות ניסיון עולות פחות מחצי סנט.

## הכנה

```bash
cd ~/ai-engineer-course-starter && source .venv/bin/activate
uv pip install -r projects/m2-personal-search/requirements.txt
python -m pytest -q                      # בדיקות הסביבה, כולל tests/test_m2_personal_search.py
cd projects/m2-personal-search
python -m pytest -q tests                # אבני הדרך שלך: בהתחלה רובן נכשלות, וזה תקין
python -m pss demo                       # כל הזרימה על תיקיית הדוגמה, בחינם
```

## מה יש בתיקייה

- **`pss/`**: הכלי עצמו (קוד הייחוס).
  - `config.py`: כל החלטות הפרטיות בקובץ YAML אחד (`config.example.yaml` מראה כל שדה).
  - `scan.py`: מעבר על התיקייה וסינון. קובץ שמוחרג כאן לא נפתח, לא מנותח ולא נשמר.
  - `extract.py`: קובץ לטקסט. PDF עמוד אחרי עמוד (עם תיקון עברית, ראה למטה), DOCX, Markdown, טקסט ו-HTML דרך ה-loaders של ragkit, ותמונות דרך Tesseract. תאריך המסמך משם הקובץ, מהמטא-דאטה, או מזמן השינוי.
  - `manifest.py` ו-`index.py`: אינדקס אינקרמנטלי על הדיסק (manifest, chunks, וקטורים), BM25, dense ו-hybrid מ-ragkit, ותוצאות לפי קובץ עם עמוד ו-snippet.
  - `query.py`: מסננים בתוך השאילתה (`type:pdf folder:kids after:2026-06`, גם בעברית).
  - `dedup.py`: כפילויות כמעט-זהות (shingles, Jaccard, union-find).
  - `answer.py`: תשובות עם ציטוטים (קובץ ועמוד): extractive, Ollama, או ענן דרך השער של `privacy.py`.
  - `privacy.py`: השמטה לפי תיקייה, redaction, ויומן יציאה שנכתב לפני השליחה.
  - `watch.py`: עדכון האינדקס כשקבצים משתנים (watchdog, עם debounce).
  - `api.py` ו-`web/index.html`: ממשק web מקומי בעברית, על 127.0.0.1 בלבד.
  - `evaluate.py`: recall@k, MRR ו-page@1 לכל מצב חיפוש, איכות תשובות, זמנים וגודל אינדקס.
  - `hooks.py`: בוחר בין הפונקציות שלך ב-`mine.py` לבין גרסאות הייחוס.
- **`data/sample/`**: תיקייה אישית סינתטית, 45 קבצים (כולל עותקים, תיקייה פרטית ותיקייה נסתרת שאסור לאנדקס). הכול מומצא: שמות, כתובות, טלפונים בטווח 050-555-01xx, ומכתבי בנק כתבניות עם XXXX. המכתבים הרפואיים הם זימונים בלבד, בלי שום מידע רפואי. `data/make_sample.py` בונה אותה מחדש.
- **`data/golden.jsonl`**: 52 שאלות זהב בעברית ובאנגלית, עם הקבצים (והעמודים) הנכונים, לפי סוג: מילות מפתח, ניסוח אחר, בין-לשוני, מסננים, OCR, ושאלות שאין להן תשובה.
- **`mine.py`**: חמש פונקציות שאתה כותב (אבני דרך 2, 3, 5, 6, 8).
- **`tests/`**: בדיקות לאבני הדרך, ושער הרגרסיה (`test_m10_regression_gate.py`).

## מה נמדד בסביבת הבנייה (ומה לא)

התוצאות של `python -m pss eval` על תיקיית הדוגמה, עם ה-embedder המזויף ו-`ExtractiveAnswerer`:

- **BM25:** recall@5 של 0.85, MRR 0.81, page@1 0.69. מילות מפתח 1.00, ניסוח אחר 0.79, בין-לשוני 0.50.
- **dense (מזויף):** recall@5 0.77, MRR 0.67. בין-לשוני 0.38. זה צפוי: ה-embedder המזויף הוא hashing של מילים ותווים, ולכן הוא לא יודע ש"מרק עדשים" ו-"lentil soup" הם אותו דבר.
- **hybrid (RRF):** recall@5 0.85, MRR 0.79. עם embedder מזויף hybrid לא יכול להוסיף ידע סמנטי, ולכן הוא לא עוקף את BM25. **זו בדיוק השאלה של אבן דרך 4:** כמה e5-small מוסיף בניסוח אחר ובבין-לשוני. את המספר הזה מודדים אצלך.
- **תשובות extractive:** אף ציטוט לא מצביע על מקור שלא קיים, 0.97 מהמשפטים מבוססים על המקור שהם מצטטים, אבל רק 0.29 מהעובדות נמצאות בתשובה. ה-extractive בוחר משפטים לפי מילים משותפות, ולכן הוא חלש בשאלות בניסוח אחר. הוא קו בסיס לבדיקת הצנרת, לא מודל.
- **זמנים וגודל:** האינדקס של 43 קבצים ו-53 קטעים תופס כ-130KB ונבנה בכ-2 שניות. חיפוש לוקח פחות ממילישנייה. עם e5-small האינדקס גדל (384 ממדים במקום 256) והבנייה הראשונה איטית יותר, כי כל קטע עובר במודל. ה-cache חוסך את זה בפעם הבאה.

**ממצא אמיתי מהבנייה: PDF בעברית.** pypdf במצב layout (ברירת המחדל של ה-loader של ragkit) מחזיר כל שורה עברית **הפוכה** ("םכסה" במקום "הסכם"), ובמצב plain מספרים "קופצים" ונדבקים למילים ("שלושה12,600"). pdfminer.six מחזיר את השורות בסדר חזותי עקבי, ולכן אפשר להפוך אותן בחזרה בדיוק: `extract.py` מחליט לכל עמוד אם הוא חזותי לפי אותיות סופיות (מילה שמתחילה ב-ם או נגמרת ב-מ היא סימן לסדר הפוך), הופך, ומחזיר את המספרים והאנגלית לסדר שלהם. נבדק על קובצי PDF שנוצרו ב-Chromium. **קובצי PDF אמיתיים שלך (Word, סורקים, מערכות של בנקים) יכולים להתנהג אחרת**: באבן דרך 10 בודקים את זה על התיקייה שלך.

## אבני הדרך

**1. הרצה ראשונה (חינם).** `demo` בונה אינדקס חדש של תיקיית הדוגמה, מריץ אותן שאילתות בשלושת מצבי החיפוש, עונה על שאלה אחת, ומראה מה **היה** יוצא לענן (בלי לשלוח).

```bash
python -m pss demo
python -m pss scan data/sample --explain | head -20
python -m pss search "ערבות בנקאית"
python -m pss search "how much luggage can each of us take on the plane" --mode bm25
```

בדיקת קבלה: 43 קבצים באינדקס, `private/` ו-`.cache/` מדולגות עם הסיבה, 3 קבוצות כפילויות. ענה: למה השאילתה על המזוודות לא מוצאת את כרטיס הטיסה באף מצב? מה חסר לכלי כדי למצוא אותו?

**2. מה אסור לקרוא (קוד: `is_excluded`).** ממש את `is_excluded` ב-`mine.py`. שלושה סוגי תבניות: בלי `/` (כל רכיב בנתיב), עם `/` בסוף (שם תיקייה), ועם `/` באמצע (כל הנתיב, כולל `**`). הוסף ל-`config.example.yaml` שלך תבנית לתיקייה רגישה, והרץ `scan --explain`.

```bash
python -m pytest -q tests/test_m2_exclude.py
python -m pss scan data/sample --explain | grep skip
```

ענה: למה ההחרגה נעשית בסריקה, ולא בסינון של תוצאות החיפוש? מה היה נשאר על הדיסק במקרה השני?

**3. עדכון אינקרמנטלי (קוד: `plan_sync`).** ממש את `plan_sync`: בדיקת size ו-mtime קודם, ו-hash רק למה שזז. אחר כך ערוך קובץ אחד בעותק של התיקייה ובדוק שרק הוא נבנה מחדש.

```bash
python -m pytest -q tests/test_m3_sync.py
cp -r data/sample /tmp/pss-play && python -m pss --index-dir /tmp/pss-idx index /tmp/pss-play
echo "- גרביים חמות" >> /tmp/pss-play/travel/packing-list-georgia.md && touch /tmp/pss-play/recipes/shakshuka.md
python -m pss --index-dir /tmp/pss-idx index /tmp/pss-play     # changed 1, touched 1
```

ענה: מה ההבדל בין touched ל-changed, ולמה הוא חשוב כשסנכרון ענן (Dropbox, Syncthing) נוגע בכל הקבצים?

**4. embeddings אמיתיים, מקומית (חינם, הורדה של כ-470MB פעם אחת).** התקן את torch בגרסת CPU ואת sentence-transformers, ובנה את האינדקס עם `e5-small`. השווה את ה-eval לזה של ה-embedder המזויף, במיוחד בשורות "semantic" ו-"cross-lingual".

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install "sentence-transformers>=5.1"
python -m pss eval --embedder e5-small --json results/eval_e5.json
python -m pss eval --json results/eval_fake.json
PSS_GATE_EMBEDDER=e5-small python -m pytest -q tests/test_m10_regression_gate.py
```

בדיקת קבלה: שער ה-e5 עובר (hybrid לא גרוע מ-BM25, וטוב ממנו בבין-לשוני). ענה: כמה זמן לקחה הבנייה הראשונה, וכמה השנייה (cache)? מה הגודל של `~/.cache/pss/embeddings`?

**5. מסננים בתוך השאילתה (קוד: `parse_query`).** ממש את `parse_query`. המסננים הופכים ל-`where` שכל retriever מפעיל **לפני** הדירוג.

```bash
python -m pytest -q tests/test_m5_query.py
python -m pss search "type:pdf after:2026-06 אחריות"
python -m pss search "סוג:docx תיקייה:kids"
```

ענה: מאיפה מגיע התאריך של `car-rental-georgia-voucher.pdf`, ולמה הוא שגוי? מה היית משנה?

**6. כפילויות (קוד: `near_duplicate_groups`).** ממש את הפונקציה (shingles של 3 מילים, Jaccard, וקבוצות טרנזיטיביות). בתוצאות החיפוש העותק מקופל לתוך התוצאה הראשונה ("עותק נוסף").

```bash
python -m pytest -q tests/test_m6_dups.py
python -m pss dups
python -m pss search "ערבות בנקאית" --json | python -c "import json,sys; print(json.load(sys.stdin)['results'][0]['also'])"
```

**7. תשובות מקומיות עם Ollama (חינם).** התקן את Ollama, משוך מודל קטן רב-לשוני, ושאל את המסמכים. התשובה מצטטת קובץ ועמוד, ושום דבר לא יוצא מהמחשב. נסה שני מודלים על אותן חמש שאלות בעברית, ושפוט בעצמך את העברית.

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:4b                 # 3.3-4GB; alternative: gemma4:e4b, gemma3:4b
python -m pss ask "כמה עולה הטיול השנתי של נועה, ועד מתי צריך להחזיר את האישור?"
python -m pss ask "what time is check-out at the Tbilisi hotel?" --llm ollama:qwen3.5:4b
python -m pss eval --llm ollama:qwen3.5:4b --record --modes hybrid
```

בדיקת קבלה: נוצר `data/recorded/qwen3.5-4b.jsonl`, והבדיקה המוקלטת בשער עוברת. ענה: כמה שניות לוקחת תשובה אצלך (p50 ו-p95 מודפסים)? באיזו שאלה עברית המודל טעה או ענה באנגלית?

**8. פרטיות ותשובה מהענן (קוד: `redact_for_cloud`; בתשלום: פחות מסנט).** ממש את `redact_for_cloud`. אחר כך הפעל `cloud.enabled: true` בקובץ ההגדרות שלך, וקודם הרץ `--dry-run`: זה בדיוק מה שיישלח. רק אז שלח באמת, ופתח את יומן היציאה.

```bash
python -m pytest -q tests/test_m8_redact.py
mkdir -p ~/.config/pss && cp config.example.yaml ~/.config/pss/config.yaml
# edit it: roots -> the absolute path of data/sample (for now), index_dir -> the absolute path of state/sample,
#          embedder -> what you used in milestone 4, cloud.enabled -> true
python -m pss ask "מתי התור לרופאה? תחזרו אליי ב-050-555-0199" --cloud --dry-run
python -m pss ask "what time is check-out at the Tbilisi hotel?" --cloud
python -m pss egress --payload
```

ענה: איזה מקור הושמט בשאלה הראשונה ולמה? מה ה-redaction לא היה תופס (רמז: שם של אדם, כתובת)? למה היומן נכתב לפני השליחה ולא אחריה?

**9. ממשק web ועדכון חי (חינם).** הרם את השרת, חפש, פתח קובץ בעמוד הנכון, ושאל. בחלון אחר הרץ `watch`, הוסף קובץ לתיקייה, וחפש אותו. ולבסוף OCR: התקן את Tesseract עם עברית ובנה מחדש: שתי התמונות ב-`scans/` הופכות לטקסט.

```bash
python -m pss serve                    # http://127.0.0.1:8765
python -m pss watch                    # another terminal
echo "# קוד לשער החניה: לא לשמור כאן סיסמאות" > data/sample/home/parking-note.md   # appears in search within ~2s
sudo apt install tesseract-ocr tesseract-ocr-heb
python -m pss index                    # the installed OCR languages are part of the index signature: rebuilt
python -m pss search "יום פיגמות בגן"
rm data/sample/home/parking-note.md
```

בדיקת קבלה: התגית "מקומי" ירוקה, הקישור לתוצאה ב-PDF נפתח בעמוד הנכון, וההודעה מהגן נמצאת אחרי OCR. ענה: מה עושה בדיקת ה-Host בשרת, ומה היא מונעת?

**10. eval, שער רגרסיה, והתיקייה האמיתית שלך.** הרץ את ה-eval המלא ושמור את המספרים לתיק העבודות. אחר כך העבר את `~/.config/pss/config.yaml` לתיקייה האמיתית שלך: roots לתיקיות שלך, excludes לכל מה שרגיש, ו-index_dir מחוץ לתיקיות המאונדקסות (למשל `~/.local/share/pss/main`). מומלץ להחזיר את `cloud.enabled` ל-false עד שתעבור על מה שה-dry-run מראה. הרץ קודם `scan --explain` ורק אז `index`, ובדוק עשר שאלות שאתה באמת שואל.

```bash
python -m pss eval --embedder e5-small --llm ollama:qwen3.5:4b --json results/eval_full.json
python -m pytest -q tests
python -m pss scan --explain | less        # with your config: what WILL be read
python -m pss index && python -m pss stats
python -m pss serve
```

בדיקת קבלה: שער הרגרסיה ירוק. ענה: כמה קבצים, קטעים ו-MB יש באינדקס של התיקייה שלך? כמה קבצי PDF יצאו עם אזהרה? מצאת PDF עברי שהטקסט שלו עדיין הפוך?

## מה לבדוק אצלך, כי כאן לא היה אפשר

- **e5-small:** ההורדה מ-Hugging Face לא הייתה זמינה בסביבת הבנייה, ולכן אף מספר של dense אמיתי לא נמדד. כל המספרים למעלה הם של embedder מזויף.
- **Ollama:** לא הותקן כאן. ה-adapter נבדק מול שרת מזויף (גוף הבקשה, `think: false`, `num_ctx`, ניסיון חוזר בלי think, ושגיאת 404 כשהמודל לא נמשך). איכות העברית, הזמנים, והאם `qwen3.5:4b` מכבד את `think: false`: לבדוק אצלך.
- **OCR בעברית:** רק `eng` היה מותקן. התמונה העברית יצאה ג'יבריש עם `eng` בלבד, וזה צפוי. את `tesseract-ocr-heb` צריך להתקין ולבדוק.
- **Claude Haiku 5.5:** לא היה מפתח. השער נבדק עם replay של llmkit (הבקשה נבנית כמו לאמיתי, ונבדק מה בדיוק נשלח).
- **watchdog על התיקייה שלך:** נבדק עם PollingObserver על תיקייה קטנה. עם inotify על עץ גדול צריך לבדוק את המגבלה `fs.inotify.max_user_watches`.

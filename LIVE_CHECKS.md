# בדיקות חיות: מה לא היה אפשר להריץ בזמן הבנייה

הקורס נבנה בסביבה בלי מפתחות API, בלי Docker ובלי גישה ל-Hugging Face. כל הבדיקות של הסביבה רצו ועברו offline, מול `mockllm`, fixtures ומודלים מזויפים. את הרשימה הזו מריצים במחשב שלך, כל שיעור כשמגיעים אליו. אם מספר חי שונה מהמספר שבשקופיות, המספר החי נכון: תעדכן אותי, ואתקן את הטקסט.

כל הפקודות רצות מתיקיית השורש של הריפו, עם ה-venv פעיל. העלויות הן הערכות, על Haiku 5.5.

## הכנה כללית
- `uv pip install -r requirements.txt`, ואז `python -m pytest -q`: אמור לעבור כולו.
- משיעור 10: PyTorch ל-CPU ו-`requirements-local-models.txt` (ראה README). ההורדה הראשונה של multilingual-e5-small לוקחת כמה דקות.
- Docker נדרש לשיעורים 11, 22, 25 ו-27 ולפרויקטים. AWS נדרש רק לתרגילי הפריסה, שמסומנים בכסף.

## שלב 1: יסודות
**שיעור 1 (prompting, בערך 5 עד 50 סנט, לפי כמה ניסויים מריצים במלואם)**
- כל ניסוי: קודם `--dry-run`, אחר כך `--limit 3 --repeats 1`, ורק אז הריצה המלאה. `promptlab run` מדפיס תוכנית והערכה של המקרה הגרוע, ושואל לפני שהוא שולח. ההערכות הגרועות: תרגיל 2 כסנט וחצי, תרגיל 3 כ-36 סנט, תרגיל 4 כ-9, תרגיל 5 כ-6, תרגיל 6 כ-25. המחיר האמיתי נמוך מזה, כי רוב התשובות קצרות מ-`max_tokens`.
- תרגיל 2 צריך Ollama מקומי עם המודל שב-YAML. ה-variant של Haiku 5.5 עם temperature אמור להחזיר 400: לבדוק שזה עדיין המצב.
- תרגיל 3 כולל 15 בעיות, מהן חמש קשות (h01 עד h05), כלומר 90 קריאות ולא 60. ההבדל בין effort low ל-high אמור להופיע בעיקר בחמש הקשות.
- `python labs/01-prompting/arena.py` ו-promptfoo (`cd labs/01-prompting/promptfoo && npx promptfoo@latest eval`): צריך Node 20 ומעלה.
- `python labs/01-prompting/count_tokens.py`: היחס בין עברית לאנגלית. הספירה של Claude כוללת את מעטפת ההודעה, ולכן בטקסט קצר היחס מתקרב ל-1.

**שיעור 2 (LLM APIs, כמה סנטים): הורץ חי בבניית הקורס, אוקטובר 2026**
- `curl_examples.sh` ו-`raw_http.py` מול שלושת הספקים, `retry_demo.py`, ו-`bench.py --runs 10` עם Haiku, GPT ו-Gemini.
- ממצאים חיים שכבר נכנסו לקורס: `tok/s` לא כולל טוקני חשיבה; ב-Gemini זרם שנחתך מזוהה רק לפי `finishReason`; מפתח חינמי של Gemini נתקע ב-429 של מכסה, לא של קצב.

**שיעור 3 (structured outputs, כמה סנטים): הורץ חי בבניית הקורס, נובמבר 2026**
- `raw_structured.py --twice`, ואחר כך `--bad-schema` בארבע הגרסאות.
- ממצאים מ-Claude Haiku 5.5, בבדיקות מ-3 בנובמבר 2026:
  - `pattern` נדחה עם 400 ("Schema is too complex"), גם על תבנית מייל פשוטה.
  - `minLength` התקבל ונאכף: עם `minLength=40` ה-`tool` חזר באורך 63 תווים, אף ששם כלי אמיתי הוא כ-10.
  - `additionalProperties: true` התקבל עם 200.
  - המשמעות: לפחות `minLength` אפשר להשאיר בסכמה שנשלחת ל-Claude. לפני שמשנים את `UNSUPPORTED` ב-`llmkit/schema.py`, כדאי לבדוק באותה שיטה גם `maxLength` ו-`minimum`/`maximum`, ולהריץ את `minlength40` עוד פעם או פעמיים.
- `extract_eval.py --mode native` ו-`--mode prompt`, על `--set normal` ועל `--set hard`.

**שיעור 4 (context, כ-30 סנט לכל המעבדה)**
- `python labs/04-context-engineering/cache_experiment.py --mode all`: קריאה 1 כותבת כ-13K טוקנים למטמון, וקריאות 2 והלאה קוראות ממנו. לבדוק אם הזמן לטוקן הראשון יורד.
- אותו סקריפט עם `--parallel 3`: האם שלוש קריאות במקביל כולן כותבות.
- עם `--short`, על Haiku 5.5 מול Haiku 4.5: האם קידומת קצרה נשמרת במטמון.
- `context_budget.py --calibrate`: היחס האמיתי בין הטוקנייזר של Claude ל-o200k. הסקריפטים מניחים פי 1.3.
- `position_test.py` ו-`compaction_eval.py`, במצב חי.

**שיעור 5 (סוכני קוד)**
- `run_agent.py --dry-run`, ואחר כך הרצה אמיתית אחת של Claude Code.
- שה-hook עובד גם עם הרווח בנתיב של ה-venv.
- האם `--setting-sources project,local` משאיר את `~/.claude/CLAUDE.md` שלך מחוץ להרצות.

**שיעור 6 (spec-driven, כ-0.1 סנט)**
- `spec_review.py --model anthropic:claude-haiku-5-5`, על המפרט המלא ועל הטיוטה.
- תרגיל 6 עם Claude Code, כולל תחביר ה-deny `--disallowedTools "Read(./…/**)"`.

**שיעור 7 (לולאות אימות, עד 25 סנט)**
- `run_loop.py --generator llm --verifier strong --mine`, ואחר כך `--feedback raw` ו-`--feedback minimal`, ואז `report.py`.
- `compare_oracles.py --generator llm --allow-test-edits --include-impossible --max-iters 4`: האם Haiku עורך בדיקות, או מחזיר `cannot_solve`.

## שלב 2: ידע
**שיעור 8 (נתונים מובנים, כסנט)**
- `ask.py --live "How many open P1 tickets do we have right now?"`: שמשתמש בהגדרה ש-pending נחשב פתוח.
- `ask.py --live "Show everything about the employees of the Identity team."`: שה-guard דוחה ותור התיקון מתקן.
- `eval_sql.py --live` (כ-30 קריאות), ו-`render_context.py --exact`.

**שיעור 9 (ingestion, פחות מ-5 סנט)**
- `rag_answer.py --qid q041 --model anthropic:claude-haiku-5-5 --show-prompt`.
- `rag_eval.py --model anthropic:claude-haiku-5-5 --failures --yes`: להשוות לשורות של עברית, התנגשות גרסאות, multi-hop ושאלות בלי תשובה בשקופית.
- `long_context.py --live --claude-count --yes`, ו-`normalize_demo.py --tokenizer tiktoken --claude`.

**שיעור 10 (embeddings, פחות מסנט)**
- `similarity_demo.py`, ואז `embed_corpus.py` פעמיים: בפעם השנייה צפויות 289 פגיעות במטמון.
- `compare.py`: האם dense באמת מתקן את q039 ו-q069.
- `embed_corpus.py --model openai:text-embedding-3-small`, ואותו דבר עם `-large`.
- `dims.py --model openai:text-embedding-3-small --api-check`.

**שיעור 11 (vector DBs, Docker)**
- `docker compose -f labs/11-managed-vectors/compose.yaml up -d`: ששני הקונטיינרים healthy.
- `hnsw_sweep.py --backend qdrant`, ואותו דבר עם `--backend pgvector`.
- `filter_pitfall.py --qdrant --pgvector`, `quantization.py --real e5-small --qdrant`, `load_acme.py --qdrant --pgvector`.
- אופציונלי: תרגיל 8 מול S3 Vectors אמיתי (פחות מסנט, ואז teardown).

**שיעור 12 (hybrid ו-rerank, כ-5 סנט)**
- `hybrid_eval.py` עם e5-small, ו-`rewrite.py --llm anthropic:claude-haiku-5-5 --record`.
- `rerank_eval.py --rerankers ce:mmarco,ce:bge-m3`, ואותו דבר עם `--rerankers llm:anthropic:claude-haiku-5-5`.
- `ablation.py` המלא.

**שיעור 13 (אבחון, כ-20 סנט)**
- `claims.py --llm anthropic:claude-haiku-5-5`.
- `run_diagnosis.py --llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5 --yes`, ואחר כך `run_diagnosis.py --rejudge <קובץ ה-traces של Haiku> --judge heuristic` (חינם): כמה השופט הלקסיקלי רחוק מ-Haiku.
- `fix_loop.py --start best --llm anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5 --fix prompt --yes`.
- `claims.py --nli` (צריך את `requirements-local-models.txt`): שה-tokenizer נטען. אם הוא נכשל, `uv pip install protobuf`.

## שלב 3: פעולה
**שיעור 14 (tool calling, כ-3 סנט)**
- `raw_roundtrip.py`, ואחר כך `--parallel`. `tool_cost.py --live` (ה-endpoint של count_tokens חינמי).
- `route_eval.py --model anthropic:claude-haiku-5-5 --show`: במצב offline ה-router המדומה מגיע ל-15 מתוך 18 עם תיאורים טובים. המספר החי הוא התוצאה האמיתית.
- `injection_demo.py --model anthropic:claude-haiku-5-5 --defense none`, ואותו דבר עם `--defense all`: האם Haiku נופל לפסקה של Northwind.

**שיעור 15 (agent loops, 5 עד 15 סנט)**
- `run_agent.py t01 --model anthropic:claude-haiku-5-5 --approve yes`.
- `eval_tasks.py --modes react,plan --model anthropic:claude-haiku-5-5`, ו-`--modes workflow`.
- `faults_demo.py misleading --model anthropic:claude-haiku-5-5`, ו-`memory_demo.py`.

**שיעור 16 (LangGraph, 2 עד 5 סנט)**
- `run.py --reset`, ואז `run.py --all --model anthropic:claude-haiku-5-5`.
- `compare.py --model anthropic:claude-haiku-5-5 --repeat 3`: ההשוואה האמיתית בין workflow לסוכן חופשי. שקופית 16 ממתינה למספר הזה.

**שיעור 17 (MCP, 3 עד 5 סנט)**
- `agent.py --set`, ואחר כך `--set --mine`.
- `poison_demo.py --attack`, ואחר כך `--defense`.
- ה-Inspector (צריך Node 22.19 ומעלה):
  `npx @modelcontextprotocol/inspector --cli .venv/bin/python -m mcpkit -- --method tools/list`
- Claude Code: `claude mcp add --env PYTHONPATH="$PWD" --transport stdio acme -- "$PWD/.venv/bin/python" -m mcpkit`. לבדוק:
  - שהפקודה `/mcp` מראה 8 כלים;
  - שדיאלוג האישור של `create_access_request` מופיע;
  - באיזו גרסת פרוטוקול Claude Code מתחבר.

**שיעור 18 (multi-agent, עד 40 סנט)**
- `run_router.py --accuracy --model anthropic:claude-haiku-5-5`.
- `compare.py --mine --model anthropic:claude-haiku-5-5`: המדידה המרכזית. נעצר לבד ב-40 סנט.
- `failure_demo.py --fault route,lead --verify none,llm --model anthropic:claude-haiku-5-5`.

## שלב 4: פרודקשן
**שיעור 19**
- `critique_adr.py labs/19-ai-architecture/adr/0000-example-response-cache.md`.
- רינדור Mermaid: `npx -y @mermaid-js/mermaid-cli@12.0.0 -i labs/19-ai-architecture/results/company-brain.mmd -o labs/19-ai-architecture/results/company-brain.svg` (אחרי `diagram.py`).

**שיעור 20**
- `answer_demo.py ... --model anthropic:claude-haiku-5-5`: שהציטוטים יוצאים בפורמט `[doc_id]`.
- `BRAIN_LIVE_MODEL=anthropic:claude-haiku-5-5 pytest .../test_ex4_contract.py -k Live`.

**שיעור 21 (רב-מודאלי, 5 עד 8 סנט)**
- `send_image.py`, ו-`token_cost.py --live --live-openai`: האם detail=low באמת יקר יותר מ-high אצל OpenAI.
- `extract_eval.py --model anthropic:claude-haiku-5-5 --runs 3`, ו-`resize_sweep.py`.
- `voice_roundtrip.py --live`, ו-`latency_budget.py --live`, ו-`pdf_pages.py --live`.

**שיעור 22 (observability)**
- `trace_demo.py --live`, ו-`replay_trace.py <prefix> --live`.
- Phoenix ב-Docker: שתכונות `gen_ai.*` מופיעות. אחר כך להחליף את `:latest` בגרסה מדויקת ב-`compose.yaml`.
- `docker compose -f labs/22-observability/collector/compose.yaml up`.

**שיעור 23 (eval, כ-10 סנט)**
- `run_eval.py --model anthropic:claude-haiku-5-5`, ו-`judge_run.py --model anthropic:claude-haiku-5-5 --judge anthropic:claude-haiku-5-5`.
- `calibrate.py --judge anthropic:claude-haiku-5-5`: ה-kappa של Haiku.
- `gate_experiment.py --model anthropic:claude-haiku-5-5`: האם הסרת כלל הגרסאות באמת פוגעת ב-Haiku.
- promptfoo עם `promptfooconfig.live.yaml` (צריך Node 20 ומעלה).

**שיעור 24 (אבטחה, עד 25 סנט)**
- `run_attacks.py --model anthropic:claude-haiku-5-5 --show` (56 קריאות).
- `defense_ladder.py --model anthropic:claude-haiku-5-5`: נעצר לבד ב-25 סנט. התוצאות של Haiku צפויות להיות שונות מאוד מהסימולציה.

**שיעור 25 (gateway)**
- `setup_keys.py`, ואז `live_compare.py` (צריך מפתח Anthropic ומפתח OpenAI).
- LiteLLM: `cd labs/25-llm-gateway/litellm && ./make_env.sh && docker compose up -d`, ואז `scenarios.py --target litellm`. לבדוק:
  - שה-tag של ה-image נמשך;
  - איזה קוד סטטוס חוזר כשתקציב של מפתח נגמר.

**שיעור 26 (serving)**
- `python -m servekit --model anthropic:claude-haiku-5-5`, ואז `client.py` עם שאלה אחת.

**שיעור 27 (פריסה, כ-15 סנט לשלוש שעות ב-AWS)**
- `docker build` לשלושת ה-Dockerfiles, והשוואת גדלים: השקופיות אומרות כ-1GB מול כ-170MB.
- `docker compose up`, ואחר כך ה-profile האמיתי עם המפתח.
- ב-`terraform/`: `terraform init`, ואז `terraform validate` ואז `terraform plan`. צפויים 21 משאבים.
- תרגיל 8 המלא: פריסה, ואחר כך `terraform destroy` ורשימת הבדיקה של ה-teardown.

**שיעור 28 (ראיונות)**
- `mock_interview.py --category rag`, ואותו דבר עם `--lang en`.
- `design_check.py check system_design/model_answer.md --llm`.

## פרויקטים
**F2: המורה לעברית (כמה סנטים)**: מתוך `projects/f2-hebrew-tutor`.
- `TUTOR=llm python -m hebtutor chat --scenario bus_station --level A2`, ואחר כך עם `--addressing f --stream`.
- ה-eval עם הקלטה: `TUTOR=llm RECORD=data/recorded/claude-haiku-5-5.jsonl python -m hebtutor eval --misses --llm-judge --json results/eval_llm.json`, ואז שער הרגרסיה.
- `STT=openai TTS=openai TUTOR=llm python -m hebtutor voice --turns 3`: האם הקול הראשון מגיע תוך 1.5 שניות.
- `serve --demo-class` בדפדפן: כפתור ההקלטה ב-Chrome וב-Safari.
- `docker compose up --build -d`, ו-`terraform plan` ב-`deploy/terraform`.

**F3: סוכן המשרות (כ-3 סנט)**: מתוך `projects/f3-job-agent`.
- `python -m jobagent eval --extractor llm --limit 10 --no-digest --misses`, ואז ה-eval המלא עם `--record`, ושער הרגרסיה.
- `docker build -f deploy/Dockerfile .` (מהשורש), ו-`terraform plan` ב-`deploy/terraform`.
- אופציונלי: טיוטת Gmail אחת עם token אמיתי עם ה-scope `gmail.compose`.

**M1: Acme Knowledge Assistant (5 עד 8 סנט)**: מתוך `projects/m1-knowledge-assistant`.
- `python -m acmeqa --mode live ingest` (מוריד את e5-small).
- `python -m acmeqa --mode live cache-check`: יש cached input tokens בשאלה השנייה.
- `python -m acmeqa --mode live eval --record --misses --json results/eval_live.json`, ואז שער הרגרסיה.
- `python -m acmeqa serve`, בדפדפן.

**M2: חיפוש חכם אישי (כמעט חינם)**: מתוך `projects/m2-personal-search`.
- אחרי התקנת המודלים המקומיים: `python -m pss eval --embedder e5-small` (הורדה של כ-470MB), ואז שער הרגרסיה עם `PSS_GATE_EMBEDDER=e5-small`. לבדוק אם hybrid עוקף את BM25 בשאילתות הסמנטיות ובשאילתות שחוצות שפה. בסביבת הבנייה ה-embedder היה מזויף, ולכן הוא לא עקף.
- `ollama pull qwen3.5:4b`, ואז `python -m pss ask ...` ו-`eval --llm ollama:qwen3.5:4b --record`: איכות העברית, זמן תגובה, והאם `think:false` מכובד.
- `sudo apt install tesseract-ocr tesseract-ocr-heb`, אינדוקס מחדש, ולבדוק ששאילתה g47 מוצאת את הפתק של הגן בעברית.
- שאלה אחת עם `--cloud` ל-Haiku (כ-0.02 סנט), ואז `egress --payload`: לראות מה בדיוק נשלח.
- `python -m pss serve` בדפדפן: שה-PDF נפתח בעמוד הנכון ושהיישור לימין תקין.
- הרצה על תיקייה אמיתית שלך דרך `~/.config/pss/config.yaml`. קודם `scan --explain`, ואז לבדוק PDF-ים בעברית שלך: ייצוא מ-Word או מהבנק עשוי לצאת אחרת מה-PDF-ים של הבדיקות.

**F1: Company Brain (10 עד 15 סנט, ותקרה של 50 סנט)**: מתוך `projects/f1-company-brain`.
- `MODE=live python -m cbrain eval --json results/eval_live.json`. לבדוק:
  - את הניתוב של a09, a10, a13 ו-a14;
  - אם בקשת העברית w07 עוברת עכשיו (ה-FakeLLM נכשל בה על "ב-GitHub");
  - את שיעור ההתקפות שמצליחות מול Haiku, עם guards ובלי.
  
  אחר כך `python -m pytest -q tests/test_m10_regression_gate.py`, שבודק גם את הרצפות החיות.
- דרך ה-gateway: `MODE=live LLM_PATH=gateway python -m cbrain ask "How long was flow-api fully unavailable on August 19, 2026?" --user dana`. צריך מפתח Anthropic ומפתח OpenAI. בלי OpenAI, למחוק את `openai-global` מ-`data/gateway/gateway.yaml`. לבדוק את רשומת ה-audit: `classification: confidential`, ו-OpenAI לא מורשה.
- `docker compose up --build -d`, ואז `docker compose exec brain python -m cbrain seed`. לבנות גם את ה-target `runtime-e5`.
- Claude Code: `claude mcp add company-brain --env BRAIN_API_KEY=demo-dana --env BRAIN_DEMO_KEYS=1 -- python -m cbrain mcp`. שאלה עובדת, והגשת בקשה מקפיצה אישור.
- AWS (אופציונלי, כ-1.70 דולר ליום): `terraform validate` ואז `terraform plan` ב-`deploy/terraform`. אם מריצים apply, לבדוק:
  - ש-SQLite במצב EXCLUSIVE עובד על EFS אמיתי;
  - שהזרקת הסודות מ-Secrets Manager עובדת;
  - שהעלייה הראשונה נגמרת בתוך 180 שניות.
  
  אחר כך `terraform destroy`.
- קובץ ה-CI נמצא ב-`projects/f1-company-brain/ci/company-brain.yml`. הוא לא הועתק ל-`.github/workflows/`, כדי ש-push לא יפעיל CI בלי שהחלטת על זה.

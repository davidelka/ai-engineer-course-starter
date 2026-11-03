<!-- For the orchestrator: paste the section below into ragkit/README.md, after "## שיעור 10".
     Also suggested: in "## נקודות הרחבה לשיעורים הבאים", change the "Hybrid ו-reranking" bullet
     to "(שיעור 12, מומש)" and point to the modules below. Suggested ragkit/__init__.py _LAZY
     entries (optional): "HybridRetriever": ("ragkit.hybrid", "HybridRetriever"),
     "make_reranker": ("ragkit.rerank", "make_reranker"), "rrf": ("ragkit.fusion", "rrf"). -->

## שיעור 12: חיפוש היברידי, query rewriting, גרסאות ו-reranking

אף אחד מהמודולים האלה לא משנה קוד קיים. כולם עוטפים retrievers, ולכן כל אחד מהם הוא בעצמו retriever, עם `search(query, k, where)`, ועובד עם `rag.answer`, עם `evaluate` ועם `metrics.run_queries` בלי שינוי. כל שלב כותב את הציון שלו ל-`Hit.scores`, ושומר את זמני הריצה שלו ב-`last_timing`.

- **`fusion.py`:** `rrf(rankings, k=60, weights=None)` (Reciprocal Rank Fusion: לכל מזהה, סכום של `w/(k+rank)` על כל הרשימות שהוא מופיע בהן), `minmax`, `zscore` ו-`weighted_fusion(score_lists, weights, normalize)`. שוויון נשבר לפי הציון, אחר כך לפי המקום הטוב ביותר ברשימה כלשהי, ואחר כך לפי המזהה. הסכומים מחושבים עם `math.fsum`.
- **`hybrid.py`:** `HybridRetriever({"bm25": bm25, "dense": dense}, method="rrf" | "weighted", fetch_k=50)` ו-`fuse_hits`. כל retriever בפנים מתבקש בדיוק `fetch_k` תוצאות, ולכן הסדר לא תלוי ב-k. כל Hit נושא את הציון של כל retriever, את `rank:<name>` ואת `rrf` או `fused`. הוא גם Index: `add` ו-`remove` מועברים לכל retriever בפנים.
- **`query.py`:** `QueryRewriter(llm)` מבצע קריאה מובנית אחת עם llmkit, לפי הסכמה `QueryRewrite`. השדות הם language, translation, variants, subquestions, step_back ו-hypothetical_answer. הוא שומר תוצאות במטמון לפי שאלה, יכול להקליט ל-JSONL, ואם הקריאה נכשלת הוא ממשיך עם השאלה המקורית (fail-open). `RewritingRetriever(base, rewriter, modes=("multi", "decompose", "translate"))` מחפש כל שאילתה ומאחד עם RRF. התרגום מחופש רק בשפת היעד, ו-`orig_weight` נותן משקל לשאלה המקורית. `replay_rewriter(fixtures)` הוא המסלול הלא מקוון.
- **`versions.py`:** `drop_superseded(hits)` משמיט מסמך כשגרסה חדשה שלו נמצאת גם היא בתוצאות. עם `superseded_by=supersedes_map(chunks)` הוא משמיט כל מסמך שיש לו גרסה חדשה בקורפוס. בנוסף יש `boost_recent(hits, weight)`, `VersionAwareRetriever(base, mode="retrieved" | "corpus" | "recent")`, ו-`stale_docs` עם `stale_at_k` לתגיות `stale:<id>` של שאלות הזהב. הקישור מגיע מ-`supersedes` במטא-דאטה של הגרסה החדשה.
- **`rerank/`:** הפרוטוקול `Reranker.rerank(query, hits, top_n)`. ל-`BaseReranker` מממשים רק `score(query, texts)`. כשיש שוויון נשמר הסדר של השלב הראשון, וכל Hit מקבל `scores["rerank"]` ו-`first_stage_rank`. `stats` מחזיק את זמן הריצה, העלות והטוקנים. `RerankingRetriever(base, reranker, fetch_k=30)` מדרג מחדש את `fetch_k` המועמדים הראשונים, ואם מבקשים יותר, השאר נשארים בסדר המקורי. המימושים:
  - `CrossEncoderReranker`, עם ה-presets `bge-m3` (`BAAI/bge-reranker-v2-m3`, Apache-2.0) ו-`mmarco`.
  - `CohereReranker`, ב-httpx ל-`/v2/rerank`, עם ניסיונות חוזרים והערכת עלות שמסומנת כלא מאומתת.
  - `LLMReranker`, עם llmkit structured: ציון בין 0 ל-10 לכל קטע, וקטע שחסר בתשובה מקבל 1-.
  - `OverlapReranker`, תחליף לקסיקלי מזויף.
  - `make_reranker(spec)` בונה reranker ממחרוזת.
- **`replay.py`:** `replay_llm(responder)` מחזיר `llmkit.LLM` אמיתי, שה-HTTP שלו נענה מקומית דרך `httpx.MockTransport`. `dispatch` בוחר מי עונה לפי סמן בפרומפט המערכת. השימוש בטוקנים מוערך.
- **`ablation.py`:** `evaluate_stage(name, retriever, qa)` ו-`format_stage(report, prev)` מודדים recall@5 ו-MRR לפי סוג שאלה, stale@5, זמן תגובה (p50, p95) ועלות לשאלה. התוצאה מודפסת כרשימה, עם השינוי מהשלב הקודם.

נקודות הרחבה:
- **reranker חדש** (למשל Voyage או Jina): יורשים מ-`BaseReranker`, מממשים `score`, ומוסיפים ל-`make_reranker`.
- **מדיניות גרסאות חדשה:** פונקציה מ-`list[Hit]` ל-`list[Hit]`, בתוך wrapper כמו `VersionAwareRetriever`.
- **Company Brain:** `RerankingRetriever(VersionAwareRetriever(RewritingRetriever(HybridRetriever(...))))`, עם `where={"classification": ...}`. ה-where מועבר עד ה-retrievers הפנימיים, כך שהסינון קורה לפני הדירוג.

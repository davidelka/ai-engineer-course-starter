"""Rebuilds fixtures/traces.jsonl (exercise 5). The retrieval is real: ragkit over the Acme corpus with
the chunker, retriever and k each story names. What is NOT real: the answers and the judge verdicts
were written by hand in the style of a real model (each to show one failure), and T1 simulates a
broken PDF loader by removing the per diem table from one chunk and page 2 of the PDF.

    python labs/13-rag-diagnostics/fixtures/build_traces.py
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ragkit.acme import acme_documents, acme_qa
from ragkit.chunking import make_chunker
from ragkit.retrieval import BM25Index
from ragkit.evaluate import quote_coverage
from ragkit.diagnose import evidence_in_context, quote_locations, stale_of, case_from_trace, classify, quote_status_map, format_diagnosis
from ragkit.tokens import get_tokenizer
from ragkit.rag import parse_citations
from evalkit.metrics import fact_coverage
docs=acme_documents(); QA={q['id']:q for q in acme_qa()}
tok=get_tokenizer("approx")
def index(spec):
    cs=make_chunker(spec,"approx").split_all(docs); bm=BM25Index(); bm.add(cs); return cs,bm
base_cs, base_bm = index("heading:400:40:150")
f_cs, f_bm = index("fixed:100:0")
cov_base = quote_status_map(docs, base_cs, list(QA.values()))
cov_f = quote_status_map(docs, f_cs, list(QA.values()))

def make(tid, qid, story, hits, answer, claims, *, depth_hits=None, k=None, quote_status=None, chunker="heading:400:40:150", pipeline="baseline (BM25)", edit_ctx=None):
    q=QA[qid]
    ctx=hits[:k] if k else hits
    texts=[h.chunk.text for h in ctx]
    if edit_ctx:
        texts=[edit_ctx.get(h.chunk.id, t) for h,t in zip(ctx,texts)]
    quotes=[s['quote'] for s in q['source_quotes']]
    locs=quote_locations(quotes, texts)
    cits=parse_citations(answer)
    cited=list(dict.fromkeys(ctx[n-1].chunk.doc_id for n in cits if 1<=n<=len(ctx)))
    ab="not in the documents" in answer.lower()
    gl = None
    if claims is not None:
        sup=sum(1 for c in claims if c[1]=="supported")
        gl = "grounded" if (not claims or sup==len(claims)) else ("not_grounded" if sup==0 else "partially_grounded")
    tr={"trace_id": tid, "qid": qid, "qtype": q["type"], "question": q["question"], "story": story,
        "pipeline": pipeline, "chunker": chunker, "k": len(ctx), "model": "hand-written in the style of claude-haiku-5-5 (not a live call)",
        "source_ids": q["source_ids"], "stale_ids": stale_of(q), "quotes": quotes,
        "quote_status": quote_status or (cov_f if chunker.startswith("fixed") else cov_base).get(qid, []),
        "answer_facts": q["answer_facts"],
        "candidates": [h.chunk.doc_id for h in (depth_hits or hits)],
        "context": [{"n": i, "chunk": h.chunk.id, "doc": h.chunk.doc_id, "title": h.chunk.title, "effective_date": h.chunk.effective_date, "text": t} for i,(h,t) in enumerate(zip(ctx,texts),1)],
        "context_tokens": sum(tok.count(t) for t in texts),
        "quote_locations": [sorted(s) for s in locs],
        "answer": answer, "citations": cits, "cited": cited, "invalid_citations": len([n for n in cits if not 1<=n<=len(ctx)]),
        "abstained": ab, "fact_coverage": fact_coverage(answer, q["answer_facts"]) if q["source_ids"] else None,
        "cost_usd": 0.0}
    if claims is not None:
        tr["groundedness"]={"label": gl, "score": (sum(1 for c in claims if c[1]=="supported")/len(claims)) if claims else None,
            "claims":[{"claim":c[0],"verdict":c[1],"evidence":c[2],"source":c[3],"evidence_verified": (evidence_in_context(c[2], texts, c[3]) if (c[1]=="supported" and c[2]) else None)} for c in claims], "cost_usd":0.0, "error":None}
    return tr

out=[]
# T1 extraction_lost: q002, PDF loaded with a broken loader: the table rows and page 2 lost.
q=QA['q002']; hits=base_bm.search(q['question'],k=50)
broken = ("## 4. Per diem\n\nThe per diem covers meals, local transport within the city, and small expenses. It is paid with the salary after the trip, based on the number of days abroad, according to this table:\n\n"
          "The day of departure and the day of return count as full days when the flight leaves before 12:00 or lands after 18:00 local time; otherwise they count as half days.")
ids=[h.chunk.id for h in hits[:8]]
hits1=[h for h in hits if h.chunk.id!='fin-travel-2026#2']
t1=make("T1","q002","The two PDFs of the travel policy were re-ingested with a new PDF loader. Nobody looked at the extracted text.",
  hits1, "The per diem for a standard city is $75 per day [1]. The 2026 policy refers to a per diem table, but the table is not included in the sources [2].",
  [["The per diem for a standard city is $75 per day","supported","| Standard cities | $75 |",1],
   ["The 2026 policy refers to a per diem table","supported","according to this table:",2]],
  k=5, quote_status=["missing"], pipeline="baseline (BM25), new PDF loader", edit_ctx={"fin-travel-2026#1": broken})
out.append(t1)

# T2 chunk_split: q052 with fixed:100:0
q=QA['q052']; hits=f_bm.search(q['question'],k=50)
t2=make("T2","q052","A teammate switched the chunker to fixed 100-token windows without overlap, to 'make retrieval more precise'.",
  hits, "Production deploys are blocked during Quiet Hours unless a CAB exception is granted [2]. Quiet Hours run from Thursday 15:00 to Sunday 09:00 Israel time [1], and on the eve of an Israeli public holiday from 15:00 until midnight [1].",
  [["Production deploys are blocked during Quiet Hours unless a CAB exception is granted","supported","Production deploys are blocked during Quiet Hours unless a CAB exception is granted.",2],
   ["Quiet Hours run from Thursday 15:00 to Sunday 09:00 Israel time","supported","from Thursday 15:00 to Sunday 09:00 Israel time",1],
   ["On the eve of an Israeli public holiday, Quiet Hours start at 15:00","supported","from 15:00 on the eve of an Israeli public holiday until",1],
   ["On the eve of a public holiday, Quiet Hours last until midnight","not_found",None,None]],
  k=5, chunker="fixed:100:0", pipeline="baseline (BM25), chunker fixed:100:0")
out.append(t2)

# T3 ranked_low: q040 baseline real retrieval
q=QA['q040']; hits=base_bm.search(q['question'],k=50)
t3=make("T3","q040","Lesson 9 baseline, unchanged. A multi-hop question: the cause is in the postmortem, the owner in the service catalog.",
  hits, "The August 2026 flow-api outage was caused by a configuration change to auth-service that reduced its database connection pool from 200 to 20 [1]. The sources do not say who owns auth-service, who leads it, or when its on-call rotation hands over.",
  [["The August 2026 flow-api outage was caused by a configuration change to auth-service","supported","A configuration change to auth-service reduced its database connection pool from 200 to 20 connections per pod.",1],
   ["The change reduced the auth-service database connection pool from 200 to 20","supported","reduced its database connection pool from 200 to 20 connections per pod",1]],
  k=5)
out.append(t3)

# T4 false_refusal: q039, Hebrew source in the prompt at position 2
q=QA['q039']
cand_ids=["it-security-training#0"] if False else None
hits=base_bm.search(q['question'],k=50)
he=[h for h in base_cs if h.id=="hr-onboarding-he#1"][0]
from ragkit.types import Hit
from dataclasses import replace
hl=[h for h in hits if h.chunk.doc_id!="hr-onboarding-he"]
hits4=[hl[0], Hit(chunk=he, score=0.0, rank=2)] + hl[1:]
hits4=[replace(h, rank=i) for i,h in enumerate(hits4,1)]
t4=make("T4","q039","The best pipeline of lesson 12 (with translation) found the Hebrew onboarding procedure and put it second in the prompt.",
  hits4, "not in the documents", [], k=5, pipeline="best (lesson 12: hybrid + rewrite + version filter)")
out.append(t4)

# T5 lost_in_middle: q015, dense (fake embedder) with k=20
from ragkit.dense import DenseRetriever
from ragkit.embed import make_embedder
de=DenseRetriever(make_embedder("fake")); de.add(base_cs)
q=QA['q015']; hits=de.search(q['question'],k=50)
t5=make("T5","q015","To stop ranked_low failures, someone raised k from 5 to 20 on the dense retriever 'so nothing gets cut'. The prompt is now over 4,000 tokens of sources.",
  hits, "For the Business plan, overage costs $6 per additional 1,000 runs [8], and the plan includes SAML single sign-on and 1 year of audit log retention [8]. The sources do not give the API rate limit for Business customers.",
  [["Business plan overage costs $6 per additional 1,000 runs","supported","| Business | $6 |",8],
   ["The Business plan includes SAML single sign-on","supported","| SAML single sign-on | no | no | yes | yes |",8],
   ["The Business plan includes 1 year of audit log retention","supported","| Audit log retention | none | none | 1 year | 3 years |",8]],
  k=20, pipeline="dense retrieval (lesson 10, fake embedder), k=20")
out.append(t5)

# T6 hallucination: q014
q=QA['q014']; hits=base_bm.search(q['question'],k=50)
t6=make("T6","q014","Lesson 9 baseline. The postmortem is the first source in the prompt.",
  hits, "flow-api was down for about two hours on August 19, 2026 [1], which is typical for SEV1 incidents at Acme [1]. Service was restored after the database was failed over to the second region [2].",
  [["flow-api was down for about two hours on August 19, 2026","contradicted","Duration of full unavailability: 47 minutes (14:06 to 14:53 Israel time)",1],
   ["About two hours is typical for SEV1 incidents at Acme","not_found",None,None],
   ["Service was restored after the database was failed over to the second region","not_found",None,None]],
  k=5)
out.append(t6)

for t in out:
    for c in (t.get("groundedness") or {}).get("claims", []):
        if c["verdict"]=="supported" and c["evidence"]: assert c["evidence_verified"], (t["trace_id"], c)
    d=classify(case_from_trace(t))
    print(t["trace_id"], t["qid"], "->", d.stage, d.flags, "ctx tokens", t["context_tokens"], "ev", t["quote_locations"], "facts", t["fact_coverage"])
    print("   ctx:", [c["doc"] for c in t["context"]])
    print("   cand:", list(dict.fromkeys(t["candidates"]))[:10])
json_lines="".join(json.dumps(t, ensure_ascii=False)+"\n" for t in out)
open(Path(__file__).resolve().parent / "traces.jsonl", "w", encoding="utf-8").write(json_lines)

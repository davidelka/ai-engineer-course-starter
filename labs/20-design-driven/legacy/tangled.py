"""Company Brain answer service, version 0: "it works on my machine".

THIS FILE IS DELIBERATELY TANGLED. It is the starting point of lesson 20, not
an example to copy. One function does everything: logging, caching,
policy, reading files, search, prompt building, the model call, citation
parsing and storage. Every dependency is created inside the function or read
from a module-level global, so a test cannot replace any of them without
monkeypatching internals.

    python labs/20-design-driven/legacy/tangled.py "How many vacation days do I get in my first year?"
    BRAIN_MODEL=mock:mock-model python labs/20-design-driven/legacy/tangled.py "..."   # with python -m mockllm

Exercise 1 asks you to read it and mark which line belongs to which future port.
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from llmkit import LLM, LLMError, load_dotenv  # noqa: E402

DATA = ROOT / "data" / "acme"
CACHE_PATH = Path(os.path.expanduser("~/.cache/company_brain/answers.json"))
LOG_PATH = Path("brain.log")
STOP = set("a an and are as at be by can do does for from get got have how i if in is it its me my of on or our "
           "please should so than that the their them there they this to up us was we what when where which who "
           "will with would you your".split())


def answer_question(question, user_email, request_id=None):
    t0 = time.time()
    # log every question (with the email and the full text...)
    with open(LOG_PATH, "a") as f:
        f.write(f"{datetime.now().isoformat()} {user_email} asked: {question}\n")

    # cache = idempotency, sort of
    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())
    key = request_id or hashlib.sha1(question.encode()).hexdigest()
    if key in cache:
        print("cache hit", key)
        return cache[key]

    # policy
    if not user_email.lower().strip().endswith("@acme.example"):
        result = {"request_id": key, "status": "refused", "text": "Company Brain answers Acme employees only.",
                  "citations": [], "created_at": datetime.now(timezone.utc).isoformat()}
        cache[key] = result
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache))
        return result
    if re.search(r"\b(salar(y|ies)|payslips?|compensation)\b", question.lower()):
        result = {"request_id": key, "status": "refused",
                  "text": "Compensation questions go to HR directly, not to Company Brain.",
                  "citations": [], "created_at": datetime.now(timezone.utc).isoformat()}
        cache[key] = result
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache))
        return result
    if re.search(r"\b(passwords?|api keys?|credentials?|secrets?|tokens?)\b", question.lower()):
        result = {"request_id": key, "status": "refused",
                  "text": "Company Brain never handles passwords, keys or other credentials.",
                  "citations": [], "created_at": datetime.now(timezone.utc).isoformat()}
        cache[key] = result
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache))
        return result

    # read and split the documents (on every single question)
    passages = []
    for fname in ["hr_policies.md", "saas_access_policy.md"]:
        text = (DATA / fname).read_text(encoding="utf-8")
        docs = re.findall(r'<document source="([^"]+)">\s*(.*?)</document>', text, re.S)
        if docs:
            for source, body in docs:
                m = re.search(r"^# +(.+)$", body, re.M)
                title = re.sub(r"\s*\(.*?\)\s*$", "", m.group(1)).strip() if m else "Untitled"
                passages.append({"doc_id": source, "title": title, "text": " ".join(body[m.end():].split())})
        else:
            parts = re.split(r"^## +", text, flags=re.M)
            m = re.search(r"^# +(.+)$", parts[0], re.M)
            doc_title = re.sub(r"\s*\(.*?\)\s*$", "", m.group(1)).strip() if m else "Untitled"
            for part in parts[1:]:
                head, _, body = part.partition("\n")
                passages.append({"doc_id": f"{fname}#{head.strip()}", "title": f"{doc_title}: {head.strip()}",
                                 "text": " ".join(body.split())})

    # keyword search
    words = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in STOP and len(w) > 1}
    scored = []
    for p in passages:
        pw = {w for w in re.findall(r"[a-z0-9]+", (p["title"] + " " + p["text"]).lower()) if w not in STOP}
        s = round(len(words & pw) / len(words), 4) if words else 0.0
        if s >= 0.2:
            scored.append((s, p))
    scored.sort(key=lambda x: (-x[0], x[1]["doc_id"]))
    scored = scored[:4]
    if not scored:
        result = {"request_id": key, "status": "no_context",
                  "text": "I could not find this in Acme's documents, so I won't guess. "
                          "Try rephrasing, or ask HR or IT directly.",
                  "citations": [], "created_at": datetime.now(timezone.utc).isoformat()}
        cache[key] = result
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache))
        return result

    # prompt
    prompt = "<documents>\n" + "\n".join(
        f'<document id="{p["doc_id"]}" title="{p["title"]}">\n{p["text"]}\n</document>' for _, p in scored
    ) + f"\n</documents>\n\n<question>{question}</question>"

    # model
    load_dotenv(str(ROOT / ".env"))
    llm = LLM(os.environ.get("BRAIN_MODEL", "anthropic:claude-haiku-5-5"))
    try:
        r = llm.complete(prompt, system=(
            "You are Company Brain, Acme's internal assistant. Answer the employee's question using ONLY "
            "the documents provided. After every fact, cite its source as [doc_id], for example "
            "[vacation_policy.md]. If the documents do not contain the answer, say that you don't know. "
            "Be brief: at most four sentences."), max_tokens=512)
    except LLMError as e:
        print("model failed:", e)  # bad key? overloaded? who knows, same answer for all
        titles = "; ".join(f'{p["title"]} ({p["doc_id"]})' for _, p in scored)
        return {"request_id": key, "status": "degraded",
                "text": f"The answer service is temporarily unavailable. These documents look relevant: {titles}.",
                "citations": [p["doc_id"] for _, p in scored], "created_at": datetime.now(timezone.utc).isoformat()}

    ids = {p["doc_id"] for _, p in scored}
    cites = []
    for c in re.findall(r"\[([^\[\]\s]+)\]", r.text):
        if c in ids and c not in cites:
            cites.append(c)
    result = {"request_id": key, "status": "answered", "text": r.text, "citations": cites,
              "prompt_version": None, "model": f"{llm.provider.name}:{llm.model}", "cost_usd": r.cost_usd or 0.0,
              "created_at": datetime.now(timezone.utc).isoformat()}
    cache[key] = result
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache))
    print(f"answered in {time.time() - t0:.2f}s, cost ${r.cost_usd or 0:.6f}")
    return result


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "How many vacation days do I get in my first year?"
    print(json.dumps(answer_question(q, "dana@acme.example"), indent=2, ensure_ascii=False))

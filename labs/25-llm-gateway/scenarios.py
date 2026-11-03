"""Exercise 7: the same six scenarios against gatewaykit and against LiteLLM proxy.

    # gatewaykit (terminal 1: python labs/25-llm-gateway/run_gateway.py --with-mocks)
    python labs/25-llm-gateway/scenarios.py --target gatewaykit

    # LiteLLM (cd labs/25-llm-gateway/litellm && docker compose up -d; see README)
    python labs/25-llm-gateway/scenarios.py --target litellm

    python labs/25-llm-gateway/scenarios.py --compare      # both result files, side by side

Nothing here asserts: the script RECORDS what each gateway does (status codes, error
types, headers, spend) into results/scenarios_<target>.json. Where the two differ is
the interesting part, and some of LiteLLM's answers are exactly the things its docs
leave vague. Free: both setups route to mock servers.

S1  a normal call, OpenAI format (curl-like) and Anthropic format (llmkit)
S2  no key, and a made-up key
S3  a model the key may not use
S4  a key with a tiny budget: how many requests pass, what the refusal looks like, spend
S5  fallback: the primary of haiku-flaky is down
S6  overhead: median latency direct to the mock vs through the gateway
"""

import argparse
import json
import os
import statistics
import time
import uuid

import httpx

from lablib import LAB, load_env

from llmkit import LLM, LLMError, RetryPolicy
from llmkit import load_dotenv

TARGETS = {
    "gatewaykit": {"url": "http://127.0.0.1:4100", "master_env": "GATEWAY_MASTER_KEY",
                   "mock": "http://127.0.0.1:8765"},
    "litellm": {"url": "http://127.0.0.1:4000", "master_env": "LITELLM_MASTER_KEY",
                "mock": "http://127.0.0.1:18765"},
}
INTERESTING = ("x-gateway-", "x-litellm-", "retry-after", "x-ratelimit-")


def headers_of(r):
    return {k: v for k, v in r.headers.items() if k.startswith(INTERESTING)}


def err_of(r):
    try:
        body = r.json()
    except json.JSONDecodeError:
        return r.text[:200]
    e = body.get("error", body.get("detail", body))
    if isinstance(e, dict):
        return f"{e.get('type') or e.get('code')}: {str(e.get('message'))[:200]}"
    return str(e)[:200]


class Target:
    def __init__(self, name):
        self.name = name
        t = TARGETS[name]
        self.url, self.mock = t["url"], t["mock"]
        self.master = os.environ.get(t["master_env"])
        if not self.master:
            raise SystemExit(f"{t['master_env']} is not set (see README, exercise 7)")
        self.http = httpx.Client(base_url=self.url, timeout=60)

    def create_key(self, models, budget, alias):
        h = {"authorization": f"Bearer {self.master}"}
        if self.name == "gatewaykit":
            r = self.http.post("/admin/keys", headers=h, json={"key_id": alias, "team": "lab25", "models": models,
                                                               "max_budget_usd": budget})
        else:
            r = self.http.post("/key/generate", headers=h, json={"models": models, "max_budget": budget,
                                                                 "key_alias": alias, "metadata": {"team": "lab25"}})
        r.raise_for_status()
        return r.json()["key"]

    def spend(self, key):
        if self.name == "gatewaykit":
            return self.http.get("/v1/key/info", headers={"authorization": f"Bearer {key}"}).json().get("spent_usd")
        r = self.http.get("/key/info", params={"key": key}, headers={"authorization": f"Bearer {self.master}"})
        return (r.json().get("info") or {}).get("spend") if r.status_code == 200 else f"HTTP {r.status_code}"

    def chat(self, key, model, text="ping", max_tokens=30):
        h = {"authorization": f"Bearer {key}"} if key else {}
        t0 = time.perf_counter()
        r = self.http.post("/v1/chat/completions", headers=h, json={
            "model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": text}]})
        return r, (time.perf_counter() - t0) * 1000


def run(target_name):
    t = Target(target_name)
    tag = uuid.uuid4().hex[:6]
    out = {"target": target_name}
    models = ["haiku", "haiku-flaky"] + (["haiku-backup"] if target_name == "litellm" else [])
    key = t.create_key(models, 5.0, f"lab25-main-{tag}")

    r, _ = t.chat(key, "haiku")
    out["S1_openai_format"] = {"status": r.status_code, "headers": headers_of(r),
                               "answer": r.json()["choices"][0]["message"]["content"][:80] if r.status_code == 200 else err_of(r)}
    try:
        llm = LLM("anthropic:haiku", base_url=t.url, api_key=key, retry=RetryPolicy.none())
        res = llm.complete("ping via llmkit", max_tokens=30)
        out["S1_llmkit_anthropic_format"] = {"ok": True, "text": res.text[:80], "usage": [res.usage.input_tokens,
                                                                                         res.usage.output_tokens]}
    except LLMError as e:
        out["S1_llmkit_anthropic_format"] = {"ok": False, "error": str(e)[:200]}

    r, _ = t.chat(None, "haiku")
    out["S2_no_key"] = {"status": r.status_code, "error": err_of(r)}
    r, _ = t.chat("sk-made-up-" + tag, "haiku")
    out["S2_bad_key"] = {"status": r.status_code, "error": err_of(r)}

    r, _ = t.chat(key, "sonnet")
    out["S3_model_not_allowed"] = {"status": r.status_code, "error": err_of(r)}

    small = t.create_key(["sonnet"], 0.001, f"lab25-small-{tag}")
    passed, refusal = 0, None
    for i in range(30):
        r, _ = t.chat(small, "sonnet")
        if r.status_code != 200:
            refusal = {"after_requests": passed, "status": r.status_code, "error": err_of(r), "headers": headers_of(r)}
            break
        passed += 1
        time.sleep(0.2 if target_name == "litellm" else 0)  # give batched spend writes a chance
    out["S4_budget"] = {"budget_usd": 0.001, "passed": passed, "refusal": refusal, "spend_reported": t.spend(small)}

    r, ms = t.chat(key, "haiku-flaky")
    out["S5_fallback"] = {"status": r.status_code, "ms": round(ms), "headers": headers_of(r),
                          "error": None if r.status_code == 200 else err_of(r)}

    direct = LLM("anthropic:mock-model", base_url=t.mock, api_key="mock-key", retry=RetryPolicy.none())
    via = LLM("anthropic:haiku", base_url=t.url, api_key=key, retry=RetryPolicy.none())
    d_ms, v_ms = [], []
    for _ in range(20):
        t0 = time.perf_counter(); direct.complete("latency probe", max_tokens=20); d_ms.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter(); via.complete("latency probe", max_tokens=20); v_ms.append((time.perf_counter() - t0) * 1000)
    out["S6_overhead_ms"] = {"direct_median": round(statistics.median(d_ms), 1),
                             "via_gateway_median": round(statistics.median(v_ms), 1)}
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--target", choices=list(TARGETS))
    p.add_argument("--compare", action="store_true")
    a = p.parse_args()
    load_env()
    load_dotenv(str(LAB / "litellm" / ".env"))
    results = LAB / "results"
    results.mkdir(exist_ok=True)
    if a.compare:
        files = {n: results / f"scenarios_{n}.json" for n in TARGETS}
        data = {n: json.loads(f.read_text()) for n, f in files.items() if f.exists()}
        for s in [k for k in next(iter(data.values()), {}) if k.startswith("S")]:
            print(f"\n{s}")
            for n, d in data.items():
                print(f"  {n:11} {json.dumps(d.get(s), ensure_ascii=False)[:300]}")
        return
    if not a.target:
        raise SystemExit("use --target gatewaykit|litellm or --compare")
    out = run(a.target)
    path = results / f"scenarios_{a.target}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    for k, v in out.items():
        print(f"{k}: {json.dumps(v, ensure_ascii=False)[:300]}")
    print(f"\nsaved {path.relative_to(LAB.parents[1])}")


if __name__ == "__main__":
    main()

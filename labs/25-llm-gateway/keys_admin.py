"""Exercise 6, part 3: the leaked-key drill, against the RUNNING gateway's admin API.

Terminal 1:  python labs/25-llm-gateway/run_gateway.py --with-mocks
Terminal 2:
    python labs/25-llm-gateway/keys_admin.py state                 # breakers and spend per key
    python labs/25-llm-gateway/keys_admin.py revoke eng-copilot    # stop the key NOW
    python labs/25-llm-gateway/keys_admin.py try eng-copilot       # prove it is dead (expect 401)
    python labs/25-llm-gateway/keys_admin.py create eng-copilot-2 --team engineering \
        --models haiku,sonnet,gpt --budget 20 --soft 15
    python labs/25-llm-gateway/keys_admin.py audit eng-copilot     # what the audit log says about it

Uses GATEWAY_MASTER_KEY from state/demo_keys.env. A created key is printed ONCE and
appended to state/demo_keys.env, so the other scripts can use it.
"""

import argparse
import json
import os

import httpx

from lablib import DEMO_KEYS, GATEWAY_URL, STATE, demo_key, load_env

from gatewaykit.audit import read_audit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["state", "revoke", "create", "try", "audit"])
    p.add_argument("key_id", nargs="?")
    p.add_argument("--team", default="default")
    p.add_argument("--models", default="")
    p.add_argument("--budget", type=float, default=None)
    p.add_argument("--soft", type=float, default=None)
    a = p.parse_args()
    load_env()
    master = os.environ.get("GATEWAY_MASTER_KEY")
    http = httpx.Client(base_url=GATEWAY_URL, timeout=30, headers={"authorization": f"Bearer {master}"})

    if a.action == "state":
        print(json.dumps(http.get("/admin/state").json(), indent=2))
    elif a.action == "revoke":
        r = http.post(f"/admin/keys/{a.key_id}/revoke")
        print(r.status_code, r.json())
    elif a.action == "create":
        body = {"key_id": a.key_id, "team": a.team, "models": [m for m in a.models.split(",") if m],
                "max_budget_usd": a.budget, "soft_budget_usd": a.soft, "budget_period_days": 30}
        r = http.post("/admin/keys", json=body)
        data = r.json()
        if r.status_code == 200:
            var = "KEY_" + a.key_id.upper().replace("-", "_")
            with DEMO_KEYS.open("a", encoding="utf-8") as f:
                f.write(f"{var}={data['key']}\n")
            print(f"created {a.key_id}; saved as {var} in {DEMO_KEYS.name} (the value is not printed here)")
        else:
            print(r.status_code, data)
    elif a.action == "try":
        r = httpx.post(f"{GATEWAY_URL}/v1/chat/completions", headers={"authorization": f"Bearer {demo_key(a.key_id)}"},
                       json={"model": "haiku", "messages": [{"role": "user", "content": "ping"}]}, timeout=30)
        print(r.status_code, json.dumps(r.json(), ensure_ascii=False)[:300])
    else:
        rows = [r for r in read_audit(STATE / "audit.jsonl") if r.get("key_id") == a.key_id]
        for r in rows[-15:]:
            print(f"  {r.get('ts'):.0f} status={r.get('status')} reason={r.get('reason', '')} "
                  f"model={r.get('model', '')} admin={r.get('admin', '')}")
        print(f"{len(rows)} records for {a.key_id} in state/audit.jsonl")


if __name__ == "__main__":
    main()

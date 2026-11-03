"""Exercise 2: watch a budget run out, with YOUR ledger inside the gateway.

Terminal 1:  python labs/25-llm-gateway/run_gateway.py --with-mocks --mine budget
Terminal 2:  python labs/25-llm-gateway/budget_demo.py

The key is finance-reports (state/keys.yaml):
  models: sonnet (priced $2 / $10 per 1M tokens, like Claude Sonnet 5.5)
  hard budget $0.002, soft budget $0.001, period 30 days, floor: confidential

Then stop the gateway, start it again, and run:  python labs/25-llm-gateway/budget_demo.py --info
The spend survives the restart: the gateway rebuilds it from the audit log.
"""

import argparse

import httpx

from lablib import GATEWAY_URL, demo_key


def ask(http, key, max_tokens):
    return http.post("/v1/chat/completions", headers={"authorization": f"Bearer {key}"},
                     json={"model": "sonnet", "max_tokens": max_tokens,
                           "messages": [{"role": "user", "content": "Summarize Q3 travel spend by department."}]})


def line(i, r, max_tokens):
    h = r.headers
    if r.status_code == 200:
        return (f"  #{i:<2} max_tokens={max_tokens:<5} 200  cost=${float(h['x-gateway-cost-usd']):.6f}  "
                f"spent=${float(h['x-gateway-spent-usd']):.6f}  remaining=${float(h.get('x-gateway-budget-remaining-usd', 0)):.6f}"
                f"  {h.get('x-gateway-warning', '')}")
    err = r.json().get("error", {})
    return f"  #{i:<2} max_tokens={max_tokens:<5} {r.status_code}  {err.get('type')}: {err.get('message', '')[:150]}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--info", action="store_true", help="only show the key's spend")
    a = p.parse_args()
    key = demo_key("finance-reports")
    http = httpx.Client(base_url=GATEWAY_URL, timeout=30)
    info = http.get("/v1/key/info", headers={"authorization": f"Bearer {key}"}).json()
    print(f"finance-reports: spent ${info['spent_usd']:.6f} of ${info['max_budget_usd']} (soft ${info['soft_budget_usd']})")
    if a.info:
        return

    print("\nA. One request with max_tokens=1024. Worst case = 1024 x $10 / 1M = $0.01 > the whole budget:")
    print(line(0, ask(http, key, 1024), 1024))

    print("\nB. The same question with max_tokens=50, until the gateway says no:")
    for i in range(1, 30):
        r = ask(http, key, 50)
        print(line(i, r, 50))
        if r.status_code != 200:
            break

    print("\nQuestions for your notes:")
    print("  - Which request got the first soft_limit warning, and what would you do with that signal?")
    print("  - The 402 came while 'remaining' was still above zero. Why? (look at the estimate)")
    print("  - What would a client built on llmkit do if the gateway answered 429 here instead of 402?")


if __name__ == "__main__":
    main()

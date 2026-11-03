"""Exercise 1: call the gateway three ways, then make it say no five ways.

Terminal 1:  python labs/25-llm-gateway/run_gateway.py --with-mocks
Terminal 2:  python labs/25-llm-gateway/call_demo.py

Free: everything goes to local mock servers.
"""

import json

import httpx

from lablib import GATEWAY_URL, demo_key, gw_headers

from llmkit import LLM, LLMError, RetryPolicy
from llmkit.types import ChatRequest, Message


def show(title, resp):
    print(f"\n=== {title}\n  HTTP {resp.status_code}")
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = resp.text
    if resp.status_code == 200 and isinstance(body, dict) and "choices" in body:
        print("  answer:", body["choices"][0]["message"]["content"])
        print("  usage :", body["usage"])
    elif resp.status_code == 200 and isinstance(body, dict) and "content" in body:
        print("  answer:", body["content"][0]["text"])
        print("  usage :", body["usage"])
    else:
        print("  body  :", json.dumps(body, ensure_ascii=False)[:400])
    h = gw_headers(resp)
    if h:
        print(h)


def main() -> None:
    support = demo_key("support-bot")
    hr = demo_key("hr-assistant")
    http = httpx.Client(base_url=GATEWAY_URL, timeout=30)
    try:
        http.get("/health")
    except httpx.HTTPError:
        raise SystemExit(f"no gateway at {GATEWAY_URL}. Terminal 1: python labs/25-llm-gateway/run_gateway.py --with-mocks")

    print("The same call you could make with curl (the key comes from state/demo_keys.env):")
    print(f"""  curl -s {GATEWAY_URL}/v1/chat/completions \\
    -H "Authorization: Bearer $KEY_SUPPORT_BOT" -H 'content-type: application/json' \\
    -d '{{"model": "haiku", "messages": [{{"role": "user", "content": "Where is the VPN guide?"}}]}}'""")

    # 1. OpenAI Chat Completions format
    show("1. OpenAI format: POST /v1/chat/completions", http.post(
        "/v1/chat/completions", headers={"authorization": f"Bearer {support}"},
        json={"model": "haiku", "messages": [{"role": "user", "content": "Where is the VPN guide?"}]}))

    # 2. Anthropic Messages format
    show("2. Anthropic format: POST /v1/messages", http.post(
        "/v1/messages", headers={"x-api-key": support, "anthropic-version": "2023-06-01"},
        json={"model": "haiku", "max_tokens": 200, "messages": [{"role": "user", "content": "Where is the VPN guide?"}]}))

    # 3. llmkit, pointed at the gateway. Only base_url and the key change.
    print("\n=== 3. llmkit with base_url pointed at the gateway")
    llm = LLM("anthropic:haiku", base_url=GATEWAY_URL, api_key=support, retry=RetryPolicy.none())
    r = llm.complete("Where is the VPN guide?", max_tokens=200)
    print(f"  answer : {r.text}\n  usage  : in={r.usage.input_tokens} out={r.usage.output_tokens}")
    print(f"  llmkit cost_usd = {r.cost_usd}  <- None: 'haiku' is the gateway's alias, llmkit has no price for it.")
    print("  The gateway knows the real model, so the cost lives there (x-gateway-cost-usd, /v1/key/info).")

    # The gateway saying no
    show("4. no key", http.post("/v1/chat/completions", json={"model": "haiku", "messages": [{"role": "user", "content": "hi"}]}))
    show("5. a model this key may not use (support-bot -> sonnet)", http.post(
        "/v1/chat/completions", headers={"authorization": f"Bearer {support}"},
        json={"model": "sonnet", "messages": [{"role": "user", "content": "hi"}]}))
    show("6. an unsupported parameter is rejected, not dropped", http.post(
        "/v1/chat/completions", headers={"authorization": f"Bearer {support}"},
        json={"model": "haiku", "temperature": 0.2, "messages": [{"role": "user", "content": "hi"}]}))
    show("7. restricted data: the policy allows no deployment", http.post(
        "/v1/chat/completions", headers={"authorization": f"Bearer {support}", "x-data-classification": "restricted"},
        json={"model": "haiku", "messages": [{"role": "user", "content": "payroll for March"}]}))

    print("\n=== 8. the same policy denial through llmkit: classification travels in metadata")
    llm_hr = LLM("anthropic:haiku", base_url=GATEWAY_URL, api_key=hr, retry=RetryPolicy.none())
    try:
        llm_hr.complete(ChatRequest(messages=[Message("user", "salary of employee 123456782")],
                                    extra_body={"metadata": {"data_classification": "restricted"}}))
    except LLMError as e:
        print(f"  LLMError: status={e.status} kind={e.kind}\n  {e.message[:200]}")

    show("9. PII in the prompt. support-bot's floor is internal: phones and IDs are redacted, employee emails pass",
         http.post("/v1/chat/completions", headers={"authorization": f"Bearer {support}"},
        json={"model": "haiku", "messages": [{"role": "user", "content": "Reply to dana@acme.example, 054-1234567"}]}))

    print("  The answer shows the real number again: restore_pii_in_response put it back. The provider saw\n"
          "  [PHONE_IL_1]; exercise 4 (redact_demo.py) shows both sides.")
    show("10. GET /v1/key/info", http.get("/v1/key/info", headers={"authorization": f"Bearer {support}"}))
    print("\nNow open labs/25-llm-gateway/state/audit.jsonl: one line per request above, allowed or denied.")


if __name__ == "__main__":
    main()

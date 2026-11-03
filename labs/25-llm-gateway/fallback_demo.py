"""Exercise 3: fallback and circuit breakers, with YOUR router inside the gateway.

Terminal 1:  python labs/25-llm-gateway/run_gateway.py --with-mocks --mine router
Terminal 2:  python labs/25-llm-gateway/fallback_demo.py

Part A  "haiku-flaky": its primary (mock-down, port 8767) fails every request with 529.
        Watch the first requests pay for llmkit's retries on the dead primary, and
        the later ones skip it, once its circuit is open.
Part B  An outage in the middle of traffic: the script tells mock-a (port 8765) to fail
        everything, sends "haiku" requests, then heals it and waits for the half-open trial.
        One of the requests is CONFIDENTIAL (hr-assistant): see where it is allowed to go.
gateway.yaml: failure_threshold 3, cooldown_s 20, retries_per_deployment 1.
"""

import time

import httpx

from lablib import GATEWAY_URL, MOCK_PORTS, demo_key, load_env
import os


def call(http, key, model, text="status of ticket 4411?"):
    t0 = time.perf_counter()
    r = http.post("/v1/chat/completions", headers={"authorization": f"Bearer {key}"},
                  json={"model": model, "max_tokens": 50, "messages": [{"role": "user", "content": text}]})
    ms = (time.perf_counter() - t0) * 1000
    return r, ms


def report(i, r, ms):
    print(f"  #{i:<2} {r.status_code}  {ms:7.0f} ms  served by {r.headers.get('x-gateway-deployment', '-'):20} "
          f"attempts: {r.headers.get('x-gateway-attempts', '-')}")


def breakers(http):
    master = os.environ.get("GATEWAY_MASTER_KEY")
    r = http.get("/admin/state", headers={"authorization": f"Bearer {master}"})
    return r.json().get("breakers", {}) if r.status_code == 200 else {"?": "admin disabled"}


def mock_config(port, **cfg):
    httpx.post(f"http://127.0.0.1:{port}/__admin/config", json=cfg, timeout=5).raise_for_status()


def main() -> None:
    load_env()
    eng, hr = demo_key("eng-copilot"), demo_key("hr-assistant")
    http = httpx.Client(base_url=GATEWAY_URL, timeout=60)

    print("A. haiku-flaky: primary always down")
    for i in range(1, 7):
        report(i, *call(http, eng, "haiku-flaky"))
    print("  breakers:", breakers(http))

    print("\nB. outage of mock-a (port 8765) in the middle of 'haiku' traffic")
    port_a = MOCK_PORTS["mock-a"]
    try:
        mock_config(port_a, fail_rate=1.0, status=503)
        for i in range(1, 6):
            report(i, *call(http, eng, "haiku"))
        print("  breakers:", breakers(http))
        r, ms = call(http, hr, "haiku", "summarize the HR complaint of employee 123456782")
        print(f"  hr-assistant (floor: confidential) -> {r.status_code}: "
              f"{r.json().get('error', {}).get('message', 'ok')[:160]}")
    finally:
        mock_config(port_a, fail_rate=0.0)
    print("  mock-a healed. The circuit stays open until the cooldown ends (20 s). Waiting...")
    time.sleep(21)
    for i in range(1, 4):
        report(i, *call(http, eng, "haiku"))
    print("  breakers:", breakers(http))

    print("\nQuestions for your notes:")
    print("  - In part A, compare the requests before the circuit opened with the ones after it. Where did")
    print("    the extra time go? (llmkit retried the dead primary before the router fell back.)")
    print("  - In part B, why did the confidential request fail even though openai-global was healthy?")
    print("    Would you rather it failed, or went to openai-global? Who should decide that?")


if __name__ == "__main__":
    main()

"""Run gatewaykit for the lab.

    python labs/25-llm-gateway/run_gateway.py --with-mocks              # reference implementations
    python labs/25-llm-gateway/run_gateway.py --with-mocks --mine all   # YOUR mine.py inside the gateway
    python labs/25-llm-gateway/run_gateway.py --with-mocks --mine budget,router
    python labs/25-llm-gateway/run_gateway.py --with-mocks --cache       # turn on the response cache

--with-mocks starts the three mock servers of gateway.yaml in this process.
Stop with Ctrl+C. The audit log is labs/25-llm-gateway/state/audit.jsonl.
"""

import argparse

import uvicorn

from lablib import LAB, load_env, start_mocks, build

from gatewaykit.app import create_app


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(LAB / "gateway.yaml"))
    p.add_argument("--port", type=int, default=4100)
    p.add_argument("--with-mocks", action="store_true")
    p.add_argument("--mine", default="", help="budget,router,redact,policy or all")
    p.add_argument("--cache", action="store_true", help="enable the exact-match response cache")
    p.add_argument("-v", "--verbose", action="store_true", help="mock servers log every request")
    a = p.parse_args()
    load_env()
    if a.with_mocks:
        print("mock servers:")
        start_mocks(a.verbose)
    gw = build(a.config, a.mine)
    if a.cache:
        from gatewaykit.gateway import ResponseCache
        gw.cfg.cache_enabled = True
        gw.cache = ResponseCache(gw.cfg.cache_ttl_s, gw.monotonic)
    print(f"gatewaykit: http://127.0.0.1:{a.port}")
    print(f"  models : {', '.join(sorted(gw.cfg.models))}")
    print(f"  keys   : {', '.join(k.key_id for k in gw.keys.all()) or 'none - run setup_keys.py'}")
    print(f"  mine   : {a.mine or 'no (reference implementations)'}")
    print(f"  cache  : {'on' if gw.cache else 'off'}   audit: {gw.cfg.audit_path}")
    print(f"  admin  : {'enabled' if gw.master_key else 'disabled (no GATEWAY_MASTER_KEY)'}")
    uvicorn.run(create_app(gw), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()

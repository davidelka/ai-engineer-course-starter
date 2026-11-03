"""python -m gatewaykit --config labs/25-llm-gateway/gateway.yaml --port 4100"""

import argparse

import uvicorn

from llmkit import load_dotenv

from .app import build_gateway, create_app


def main() -> None:
    p = argparse.ArgumentParser(prog="gatewaykit", description="A small, readable LLM gateway (lesson 25)")
    p.add_argument("--config", required=True)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=4100)
    p.add_argument("--env", default=".env", help="dotenv file with provider keys and GATEWAY_MASTER_KEY")
    a = p.parse_args()
    load_dotenv(a.env)
    gw = build_gateway(a.config)
    print(f"gatewaykit on http://{a.host}:{a.port}  models={sorted(gw.cfg.models)}  keys={len(gw.keys.all())}"
          f"  audit={gw.cfg.audit_path}")
    uvicorn.run(create_app(gw), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()

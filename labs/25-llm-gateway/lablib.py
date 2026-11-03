"""Small helpers shared by the lab scripts. Nothing here is part of an exercise."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parents[1]
STATE = LAB / "state"
DEMO_KEYS = STATE / "demo_keys.env"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llmkit import load_dotenv  # noqa: E402

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:4100")
MOCK_PORTS = {"mock-a": 8765, "mock-b": 8766, "mock-down": 8767}


def load_env() -> None:
    """The repo's .env (provider keys) and the lab's demo keys. Values are never printed."""
    load_dotenv(str(ROOT / ".env"))
    load_dotenv(str(DEMO_KEYS))


def demo_key(key_id: str) -> str:
    """KEY_SUPPORT_BOT etc. from state/demo_keys.env (created by setup_keys.py)."""
    load_env()
    var = "KEY_" + key_id.upper().replace("-", "_")
    value = os.environ.get(var)
    if not value:
        sys.exit(f"{var} not found. Run first:  python labs/25-llm-gateway/setup_keys.py")
    return value


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def start_mocks(verbose: bool = False) -> list:
    """Start the three mock servers of gateway.yaml in this process (skips ports already in use)."""
    from mockllm import MockConfig
    from mockllm.server import State, make_handler
    from http.server import ThreadingHTTPServer

    servers = []
    for name, port in MOCK_PORTS.items():
        if port_open(port):
            print(f"  {name}: port {port} already in use, assuming a mock is running there")
            continue
        cfg = MockConfig(fail_rate=1.0, status=529) if name == "mock-down" else MockConfig()
        srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(State(cfg)))
        srv.daemon_threads = True
        srv.verbose = verbose
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        print(f"  {name}: http://127.0.0.1:{port}" + ("  (fails every request with 529)" if name == "mock-down" else ""))
    return servers


def mine_overrides(which: str) -> dict:
    """--mine budget,router,redact,policy (or all): plug your mine.py into the gateway."""
    if not which:
        return {}
    sys.path.insert(0, str(LAB))
    import mine  # noqa: WPS433

    parts = {p.strip() for p in which.split(",")} if which != "all" else {"budget", "router", "redact", "policy"}
    out: dict = {}
    if "budget" in parts:
        out["ledger_factory"] = mine.MyBudgetLedger
    if "router" in parts:
        out["route"] = mine.route_with_fallback
        out["breaker_factory"] = None  # set below, needs the config
        out["_breaker_cls"] = mine.MyCircuitBreaker
    if "redact" in parts:
        out["redact_fn"] = mine.redact
    if "policy" in parts:
        out["decide_fn"] = mine.decide
        out["classify_fn"] = mine.effective_classification
    return out


def build(config: Path, mine: str = "", **extra):
    """build_gateway() with your mine.py parts plugged in."""
    from gatewaykit.app import build_gateway
    from gatewaykit.config import load_config

    over = mine_overrides(mine)
    cls = over.pop("_breaker_cls", None)
    if cls is not None:
        cfg = load_config(config)
        over["breaker_factory"] = lambda dep_id: cls(cfg.failure_threshold, cfg.cooldown_s)
    else:
        over.pop("breaker_factory", None)
    over.update(extra)
    return build_gateway(config, **over)


def serve_in_thread(app, port: int = 0):
    """Run a FastAPI app with uvicorn in a background thread; returns (server, base_url)."""
    import uvicorn

    if port == 0:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}"


def gw_headers(resp) -> str:
    """The x-gateway-* headers of a response, one per line."""
    return "\n".join(f"    {k}: {v}" for k, v in resp.headers.items() if k.startswith("x-gateway") or k == "retry-after")

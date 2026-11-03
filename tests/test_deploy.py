"""Lesson 27 environment tests: deploykit (parser, reference rules, cost model), the lab's
Dockerfiles, compose file and Terraform, and the Company Brain mini API (offline, mockllm).
No Docker, terraform binary, AWS account or API key needed."""

from __future__ import annotations

import io
import json
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labs" / "27-deployment"
APP = LAB / "app"
sys.path.insert(0, str(ROOT))

from deploykit.cost import DeployConfig, monthly_cost  # noqa: E402
from deploykit.dockerfile import (  # noqa: E402
    env_pairs, lint_dockerfile, parse_dockerfile, rule_base_image_pinned, rule_dockerignore,
    split_image_ref, stages,
)
from deploykit.findings import Finding, errors  # noqa: E402


# ------------------------------------------------------------------ parser
def test_parser_continuations_comments_and_stages():
    text = ("# syntax=docker/dockerfile:1\nFROM python:3.12-slim AS builder\n"
            "RUN apt-get update \\\n    # a comment inside\n    && apt-get install -y gcc\n\n"
            "FROM builder AS final\nCOPY --from=builder --chown=app:app /a /b\nUSER app\n")
    ins = parse_dockerfile(text)
    assert [i.cmd for i in ins] == ["FROM", "RUN", "FROM", "COPY", "USER"]
    assert ins[1].line == 3 and "apt-get install -y gcc" in ins[1].args
    assert [i.stage for i in ins] == [0, 0, 1, 1, 1]
    assert ins[3].flags == {"from": "builder", "chown": "app:app"} and ins[3].rest == "/a /b"
    st = stages(ins)
    assert [(s.base, s.alias) for s in st] == [("python:3.12-slim", "builder"), ("builder", "final")]


def test_parser_heredoc_and_exec_form():
    ins = parse_dockerfile('FROM x:1\nRUN <<EOF\nset -e\necho hi\nEOF\nCMD ["uvicorn", "a:b"]\nCMD uvicorn a:b\n')
    assert ins[1].heredoc == "set -e\necho hi" and ins[2].line == 6
    assert ins[2].is_exec_form and not ins[3].is_exec_form


def test_parser_escape_directive():
    ins = parse_dockerfile("# escape=`\nFROM x:1\nRUN echo a `\n  b\n")
    assert ins[1].args == "echo a b"


def test_env_pairs_forms():
    p = lambda t: env_pairs(parse_dockerfile("FROM x:1\n" + t)[1])  # noqa: E731
    assert p('ENV A=1 B="two words"') == [("A", "1"), ("B", "two words")]
    assert p("ENV A some value") == [("A", "some value")]
    assert p("ARG NAME") == [("NAME", "")]


def test_split_image_ref():
    assert split_image_ref("python") == ("python", None, None)
    assert split_image_ref("localhost:5000/app") == ("localhost:5000/app", None, None)
    assert split_image_ref("ghcr.io/astral-sh/uv:0.13.6@sha256:ab") == ("ghcr.io/astral-sh/uv", "0.13.6", "sha256:ab")


def test_pinned_rule_reference():
    text = ("FROM python AS a\nFROM python:latest AS b\nFROM python:3.12.16-slim-trixie AS c\n"
            "FROM python@sha256:abc AS d\nFROM c\nCOPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/\n"
            "COPY --from=a /x /y\nARG IMG=python:3.12\nFROM ${IMG}\nFROM scratch\n")
    out = rule_base_image_pinned(parse_dockerfile(text))
    by_line = {int(f.where): f.severity for f in out}
    assert by_line == {1: "error", 2: "error", 3: "info", 6: "error", 9: "warning"}


def test_finding_rejects_bad_severity():
    with pytest.raises(ValueError):
        Finding("r", "fatal", "1", "m")


# ------------------------------------------------------------------ the lab's Dockerfiles
def _lint(name):
    ign = APP / f"{name}.dockerignore"
    return lint_dockerfile((APP / name).read_text(), ign.read_text() if ign.exists() else None)


def test_production_dockerfile_is_clean():
    out = _lint("Dockerfile")
    assert [f for f in out if f.severity != "info"] == []
    ins = parse_dockerfile((APP / "Dockerfile").read_text())
    assert [s.alias for s in stages(ins)] == ["builder", "runtime", "mockllm", "api"]  # api is the default target
    assert any(i.cmd == "HEALTHCHECK" for i in stages(ins)[-1].instructions)


def test_single_stage_dockerfile_has_the_expected_problems():
    rules = {f.rule for f in _lint("Dockerfile.single")}
    assert {"runs_as_non_root", "healthcheck", "exec_form", "lean_layers"} <= rules


def test_baked_dockerfile_leaks_are_found():
    out = errors(_lint("Dockerfile.baked"))
    assert {f.rule for f in out} == {"no_secrets_in_build"} and len(out) == 2


def test_dockerignore_allowlist_excludes_env_everywhere():
    ins = parse_dockerfile((APP / "Dockerfile").read_text())
    assert rule_dockerignore(ins, (APP / "Dockerfile.dockerignore").read_text()) == []
    bad = "*\n**/.env\n!llmkit/\n"  # .env re-included inside llmkit/ because the ! line comes last
    assert any(f.severity == "error" and "llmkit" in f.message for f in rule_dockerignore(ins, bad))
    assert any("no .dockerignore" in f.message for f in rule_dockerignore(parse_dockerfile("FROM x:1\nCOPY . /app\n"), None))


def test_lock_and_pyproject_agree():
    lock = (APP / "uv.lock").read_text()
    for dep in ("fastapi", "uvicorn", "httpx", "pydantic"):
        assert f'name = "{dep}"' in lock
        assert dep in (APP / "pyproject.toml").read_text()


# ------------------------------------------------------------------ compose
def test_compose_file_shape():
    c = yaml.safe_load((LAB / "compose.yaml").read_text())
    s = c["services"]
    assert set(s) == {"mockllm", "api", "api-real"}
    assert s["api"]["depends_on"]["mockllm"]["condition"] == "service_healthy"
    assert s["api"]["ports"] == ["127.0.0.1:8000:8000"]
    assert s["api"]["environment"]["MOCKLLM_URL"] == "http://mockllm:8765"
    assert s["api"]["read_only"] is True and s["api"]["cap_drop"] == ["ALL"]  # from the YAML anchor
    assert s["api-real"]["profiles"] == ["real"] and s["api-real"]["secrets"] == ["anthropic_api_key"]
    assert "ANTHROPIC_API_KEY" not in s["api-real"]["environment"]  # only the _FILE pointer
    assert c["secrets"]["anthropic_api_key"] == {"environment": "ANTHROPIC_API_KEY"}
    assert s["mockllm"]["build"]["target"] == "mockllm" and "ports" not in s["mockllm"]


# ------------------------------------------------------------------ terraform
def test_terraform_parses_and_passes_the_rules():
    pytest.importorskip("hcl2")
    from deploykit.terraform import lint_terraform, load_tf
    doc = load_tf(LAB / "terraform")
    types = {b.type for b in doc.resources}
    assert {"aws_ecs_cluster", "aws_ecs_task_definition", "aws_ecs_service", "aws_lb", "aws_lb_target_group",
            "aws_lb_listener", "aws_secretsmanager_secret", "aws_iam_role", "aws_cloudwatch_log_group",
            "aws_ecr_repository", "aws_appautoscaling_policy"} <= types
    assert "aws_secretsmanager_secret_version" not in types  # the value never goes through Terraform
    assert [f for f in lint_terraform(doc) if f.severity != "info"] == []
    c = doc.locals["api_container"]
    assert c["secrets"][0]["name"] == "ANTHROPIC_API_KEY" and "${aws_secretsmanager_secret" in c["secrets"][0]["valueFrom"]
    assert all("KEY" not in e["name"] for e in c["environment"])
    td = doc.of_type("aws_ecs_task_definition")[0].body
    assert td["execution_role_arn"] != td["task_role_arn"]


def test_budget_module_parses():
    pytest.importorskip("hcl2")
    from deploykit.terraform import load_tf
    doc = load_tf(LAB / "budget")
    b = doc.of_type("aws_budgets_budget")[0].body
    assert b["budget_type"] == "COST" and len(b["notification"]) == 3
    assert "default" not in doc.variables["alert_email"]


def test_bad_task_fixture_findings():
    pytest.importorskip("hcl2")
    from deploykit.terraform import lint_terraform, load_tf
    rules = {f.rule for f in errors(lint_terraform(load_tf(LAB / "fixtures" / "bad_task.tf")))}
    assert rules == {"roles_separated", "iam_least_privilege", "no_plaintext_secrets"}


# ------------------------------------------------------------------ cost model
def test_cost_model_reference_total():
    r = monthly_cost(DeployConfig())
    assert r["total"] == pytest.approx(37.42, abs=0.01)
    nat = monthly_cost(DeployConfig(task_public_ip=False, nat_gateways=1))
    vpce = monthly_cost(DeployConfig(task_public_ip=False, interface_endpoints=4))
    assert r["total"] < nat["total"] < vpce["total"]


# ------------------------------------------------------------------ layer_peek
def _tar_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as t:
        for name, data in files.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def test_layer_peek_finds_deleted_file(tmp_path):
    sys.path.insert(0, str(LAB))
    import layer_peek
    l1 = _tar_bytes({"app/.env": b"ANTHROPIC_API_KEY=sk-ant-lab27-FAKE-file-0000000000\n"})
    l2 = _tar_bytes({"app/.wh..env": b""})
    outer = tmp_path / "img.tar"
    manifest = json.dumps([{"Config": "c.json", "Layers": ["l1/layer.tar", "l2/layer.tar"]}]).encode()
    outer.write_bytes(_tar_bytes({"manifest.json": manifest, "l1/layer.tar": l1, "l2/layer.tar": l2}))
    hits = layer_peek.peek(str(outer), ".env")
    assert [(h["layer_index"], h["whiteout"]) for h in hits] == [(0, False), (1, True)]
    assert hits[0]["preview"].startswith("ANTHROPIC_API") and "0000000000" not in hits[0]["preview"]


# ------------------------------------------------------------------ the service
def _service():
    pytest.importorskip("fastapi")
    sys.path.insert(0, str(APP))
    from service import main, settings
    return main, settings


def test_settings_auto_model_and_key_file(tmp_path):
    _, settings = _service()
    S = settings.Settings
    assert S.from_env({}).llm_model == "mock:claude-haiku-5-5"
    s = S.from_env({"ANTHROPIC_API_KEY": "sk-test-not-real"})
    assert s.llm_model == "anthropic:claude-haiku-5-5" and s.key_source == "env"
    f = tmp_path / "key"
    f.write_text("from-file\n")
    s2 = S.from_env({"ANTHROPIC_API_KEY": "from-env", "ANTHROPIC_API_KEY_FILE": str(f)})
    assert s2.api_key == "from-file" and s2.key_source == "file"
    assert "from-file" not in repr(s2) and "from-file" not in json.dumps(s2.describe())
    with pytest.raises(settings.SettingsError):
        S.from_env({"LLM_MODEL": "anthropic:claude-haiku-5-5"})
    with pytest.raises(settings.SettingsError):
        S.from_env({"ANTHROPIC_API_KEY_FILE": str(tmp_path / "missing")})


def test_service_endpoints_against_mockllm(capsys):
    main, settings = _service()
    from fastapi.testclient import TestClient

    from mockllm.server import MockConfig, start_in_thread
    server, url = start_in_thread(MockConfig(ttft=0.0, tps=0))
    try:
        app = main.create_app(settings.Settings.from_env({"MOCKLLM_URL": url, "APP_VERSION": "t1"}))
        c = TestClient(app)
        assert c.get("/healthz").json() == {"status": "ok", "version": "t1"}
        assert c.get("/readyz").status_code == 200
        r = c.post("/v1/answer", json={"question": "What is the VPN policy?"}, headers={"x-request-id": "rid-1"})
        assert r.status_code == 200 and r.headers["x-request-id"] == "rid-1"
        body = r.json()
        assert "VPN" in body["answer"] and body["output_tokens"] > 0 and body["request_id"] == "rid-1"
        assert c.post("/v1/answer", json={"question": ""}).status_code == 422
        with c.stream("POST", "/v1/answer/stream", json={"question": "hello"}) as s:
            text = "".join(s.iter_text())
        assert "event: text" in text and "event: done" in text
        logs = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
        assert any(rec["msg"] == "answer" and rec["rid"] == "rid-1" for rec in logs)
    finally:
        server.shutdown()
    # mockllm is gone: alive, but not ready
    assert c.get("/healthz").status_code == 200
    assert c.get("/readyz").status_code == 503

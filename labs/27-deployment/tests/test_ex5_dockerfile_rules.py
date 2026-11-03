"""Exercise 5: Dockerfile rules (non-root user, no secrets in the build)."""

from pathlib import Path

from deploykit.dockerfile import parse_dockerfile
from mine import rule_no_secrets_in_build, rule_runs_as_non_root

APP = Path(__file__).resolve().parent.parent / "app"


def P(text: str):
    return parse_dockerfile(text)


def lines_of(findings):
    return sorted(int(f.where) for f in findings)


# ------------------------------------------------------------------ runs_as_non_root
def test_no_user_is_root():
    out = rule_runs_as_non_root(P("FROM python:3.12-slim\nRUN echo hi\nCMD [\"python\"]\n"))
    assert len(out) == 1
    f = out[0]
    assert (f.rule, f.severity, f.where) == ("runs_as_non_root", "error", "1") and "root" in f.message


def test_user_app_is_fine():
    assert rule_runs_as_non_root(P("FROM python:3.12-slim\nRUN useradd app\nUSER app\nCMD [\"python\"]\n")) == []


def test_numeric_uid_with_group_is_fine():
    assert rule_runs_as_non_root(P("FROM python:3.12-slim\nUSER 10001:10001\n")) == []


def test_switching_back_to_root_is_caught():
    out = rule_runs_as_non_root(P("FROM python:3.12-slim\nUSER app\nRUN x\nUSER root\nCMD [\"x\"]\n"))
    assert len(out) == 1 and out[0].where == "4"


def test_uid_zero_is_root():
    out = rule_runs_as_non_root(P("FROM python:3.12-slim\nUSER 0:0\n"))
    assert len(out) == 1 and out[0].where == "2"


def test_case_insensitive_root():
    assert len(rule_runs_as_non_root(P("FROM python:3.12-slim\nUSER ROOT\n"))) == 1


def test_only_the_final_stage_counts():
    text = "FROM python:3.12 AS builder\nRUN pip install x\nFROM python:3.12-slim\nUSER app\n"
    assert rule_runs_as_non_root(P(text)) == []
    text2 = "FROM python:3.12-slim AS builder\nUSER app\nFROM python:3.12-slim\nCMD [\"x\"]\n"
    out = rule_runs_as_non_root(P(text2))
    assert len(out) == 1 and out[0].where == "3"


def test_stage_inherits_user_from_earlier_stage():
    text = ("FROM python:3.12-slim AS runtime\nRUN useradd app\nUSER app\n"
            "FROM runtime AS api\nCOPY . /app\nCMD [\"x\"]\n")
    assert rule_runs_as_non_root(P(text)) == []


def test_inheritance_chain_and_case():
    text = ("FROM python:3.12-slim AS Base\nUSER app\nFROM base AS mid\nRUN x\nFROM MID\nRUN y\n")
    assert rule_runs_as_non_root(P(text)) == []


def test_inherits_root_from_earlier_stage():
    text = "FROM python:3.12-slim AS runtime\nRUN x\nFROM runtime\nRUN y\n"
    out = rule_runs_as_non_root(P(text))
    assert len(out) == 1 and out[0].where == "3"


def test_stage_referenced_by_index():
    text = "FROM python:3.12-slim\nUSER app\nFROM 0\nRUN y\n"
    assert rule_runs_as_non_root(P(text)) == []


def test_distroless_nonroot_image():
    assert rule_runs_as_non_root(P("FROM gcr.io/distroless/python3-debian12:nonroot\nCOPY a /a\n")) == []


def test_no_from():
    out = rule_runs_as_non_root(P("# empty\n"))
    assert len(out) == 1 and out[0].where == "1" and "FROM" in out[0].message


def test_lab_dockerfiles():
    assert rule_runs_as_non_root(P((APP / "Dockerfile").read_text())) == []
    assert len(rule_runs_as_non_root(P((APP / "Dockerfile.single").read_text()))) == 1
    assert rule_runs_as_non_root(P((APP / "Dockerfile.baked").read_text())) == []  # leaks, but not as root


# ------------------------------------------------------------------ no_secrets_in_build
def test_env_with_real_looking_key_is_one_finding():
    out = rule_no_secrets_in_build(P("FROM x:1\nENV ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijklmnop\n"))
    assert len(out) == 1
    f = out[0]
    assert (f.rule, f.severity, f.where) == ("no_secrets_in_build", "error", "2")
    assert "ANTHROPIC_API_KEY" in f.message


def test_env_secret_name_with_any_value():
    out = rule_no_secrets_in_build(P("FROM x:1\nENV DB_PASSWORD=hunter2\n"))
    assert len(out) == 1 and "DB_PASSWORD" in out[0].message


def test_legacy_env_form():
    out = rule_no_secrets_in_build(P("FROM x:1\nENV DB_PASSWORD hunter2 and more\n"))
    assert len(out) == 1 and "DB_PASSWORD" in out[0].message


def test_empty_placeholder_is_not_a_leak():
    assert rule_no_secrets_in_build(P('FROM x:1\nENV ANTHROPIC_API_KEY=""\n')) == []


def test_arg_with_secret_name_always_flagged():
    out = rule_no_secrets_in_build(P("FROM x:1\nARG GITHUB_TOKEN\n"))
    assert len(out) == 1 and "GITHUB_TOKEN" in out[0].message and "secret" in out[0].message.lower()


def test_pointers_and_lookalikes_are_fine():
    text = ("FROM x:1\nENV ANTHROPIC_API_KEY_FILE=/run/secrets/anthropic_api_key\n"
            "ENV MAX_TOKENS=400 LLM_MODEL=auto\nARG APP_VERSION=dev\nENV SECRET_ARN=arn:aws:secretsmanager:x\n")
    assert rule_no_secrets_in_build(P(text)) == []


def test_key_value_under_innocent_name():
    out = rule_no_secrets_in_build(P("FROM x:1\nENV A=1 CONFIG=sk-ant-api03-abcdefghijklmnop\n"))
    assert len(out) == 1 and "CONFIG" in out[0].message


def test_multiple_pairs_multiple_findings():
    out = rule_no_secrets_in_build(P("FROM x:1\nENV OPENAI_API_KEY=x1 DB_PASSWORD=x2 PORT=8000\n"))
    assert len(out) == 2 and lines_of(out) == [2, 2]


def test_literal_key_in_run():
    out = rule_no_secrets_in_build(P('FROM x:1\nRUN curl -H "x-api-key: sk-ant-api03-abcdefghijklmnop" https://x\n'))
    assert len(out) == 1 and out[0].where == "2"


def test_literal_key_in_heredoc():
    text = "FROM x:1\nRUN <<EOF\necho AKIAABCDEFGHIJKLMNOP > /tmp/k\nEOF\nUSER app\n"
    out = rule_no_secrets_in_build(P(text))
    assert len(out) == 1 and out[0].where == "2"


def test_lab_dockerfiles_secrets():
    assert rule_no_secrets_in_build(P((APP / "Dockerfile").read_text())) == []
    assert rule_no_secrets_in_build(P((APP / "Dockerfile.single").read_text())) == []
    text = (APP / "Dockerfile.baked").read_text()
    expected = sorted(i + 1 for i, line in enumerate(text.splitlines())
                      if line.startswith(("ARG ANTHROPIC_API_KEY", "ENV ANTHROPIC_API_KEY")))
    assert len(expected) == 2
    assert lines_of(rule_no_secrets_in_build(P(text))) == expected

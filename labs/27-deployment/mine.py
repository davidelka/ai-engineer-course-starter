"""Your code for lesson 27. Each part is checked by tests in ./tests.

The reference versions live in deploykit/ (dockerfile.py, terraform.py, cost.py).
Try not to read them before your tests pass.

    python -m pytest -q labs/27-deployment/tests

What you have to work with
--------------------------
deploykit.dockerfile.parse_dockerfile(text) -> list[Instruction]
    Instruction fields: line (1-based), cmd ("FROM", "USER", "ENV", ...: upper case),
    args (raw text after the keyword, continuations joined), stage (0 for the first FROM),
    flags (leading --flags as a dict, e.g. {"from": "builder"}), heredoc (body or "").
    ins.rest = args without the leading --flags.
deploykit.dockerfile.stages(instrs) -> list[Stage]
    Stage fields: index, base (image or stage name after FROM), alias (name after AS, or None),
    line (line of the FROM), instructions (this stage's instructions, FROM included).
deploykit.dockerfile.env_pairs(ins) -> [(key, value), ...] for ENV and ARG:
    ENV A=1 B="two words" -> [("A","1"), ("B","two words")]; ENV A some value -> [("A","some value")];
    ARG NAME -> [("NAME", "")]; ARG NAME=x -> [("NAME", "x")]
deploykit.dockerfile.looks_like_secret_name(name) -> bool
    True for ANTHROPIC_API_KEY, GITHUB_TOKEN, DB_PASSWORD, ...; False for names that POINT at a
    secret (..._FILE, _PATH, _ARN, _URL, _NAME) and for MAX_TOKENS.
deploykit.dockerfile.looks_like_secret_value(text) -> bool
    True when the text contains something shaped like a real key: sk-ant-..., AKIA..., ghp_...
deploykit.dockerfile.split_image_ref(ref) -> (name, tag or None, digest or None)
deploykit.terraform.PolicyStatement: where, effect, actions, not_actions, resources,
    not_resources, has_principals, sid.  STAR_ONLY_ACTIONS: lower-case action names whose
    only valid resource is "*" (e.g. "ecr:getauthorizationtoken").
deploykit.cost.DeployConfig, deploykit.cost.PRICES: see exercise 7 below.
deploykit.findings.Finding(rule, severity, where, message), severity "error" | "warning" | "info".
"""

from __future__ import annotations

from typing import Iterable

from deploykit.cost import PRICES, DeployConfig  # noqa: F401
from deploykit.dockerfile import (  # noqa: F401
    Instruction, env_pairs, from_parts, looks_like_secret_name, looks_like_secret_value,
    parse_dockerfile, split_image_ref, stages,
)
from deploykit.findings import Finding
from deploykit.terraform import STAR_ONLY_ACTIONS, PolicyStatement  # noqa: F401


# ------------------------------------------------------------------ exercise 5
# A worked example (already done, read it): every external image must be pinned.
def rule_base_image_pinned(instrs: list[Instruction]) -> list[Finding]:
    out: list[Finding] = []
    known: set[str] = set()  # names of earlier stages: "FROM builder" is not an external image
    for ins in instrs:
        ref = alias = None
        if ins.cmd == "FROM":
            ref, alias = from_parts(ins)
        elif ins.cmd == "COPY" and isinstance(ins.flags.get("from"), str):
            ref = ins.flags["from"]  # COPY --from=ghcr.io/astral-sh/uv:0.13.6 is an image too
        if ref is None:
            continue
        if ref.lower() in known or ref.lower() == "scratch":
            pass
        elif "$" in ref:
            out.append(Finding("base_image_pinned", "warning", str(ins.line),
                               f"image {ref!r} comes from a build arg: make sure its default is pinned"))
        else:
            name, tag, digest = split_image_ref(ref)
            if digest:
                pass
            elif tag is None or tag.lower() == "latest":
                out.append(Finding("base_image_pinned", "error", str(ins.line),
                                   f"image {ref!r} " + ("has no tag, which means :latest" if tag is None
                                                        else "uses :latest") + ": pin a version"))
            else:
                out.append(Finding("base_image_pinned", "info", str(ins.line),
                                   f"image {ref!r} is pinned by tag only; add @sha256:... for reproducible builds"))
        if ins.cmd == "FROM":
            known.add(str(ins.stage))
            if alias:
                known.add(alias.lower())
    return out


def rule_runs_as_non_root(instrs: list[Instruction]) -> list[Finding]:
    """The FINAL stage (the one `docker build` produces by default) must not run as root.

    rule name "runs_as_non_root", severity "error", at most ONE finding.
    The effective user of a stage is the value of its LAST USER instruction (only the part
    before ":", so "app:app" -> "app", "10001:10001" -> "10001"). A stage with no USER:
      - built FROM an earlier stage (its base equals an earlier stage's alias, case-insensitive,
        or its index as a string): inherits that stage's effective user (follow the chain);
      - built FROM an external image: root, unless the image name contains "nonroot"
        (distroless images like gcr.io/distroless/python3-debian12:nonroot run as non-root).
    The user is root when it is "root" or "0" (case-insensitive).
    If the final stage runs as root, return one Finding whose message contains "root";
    where = str(line of the final stage's last USER), or of its FROM if it has no USER.
    No FROM at all: one error, where "1", message "no FROM instruction".
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement rule_runs_as_non_root")


def rule_no_secrets_in_build(instrs: list[Instruction]) -> list[Finding]:
    """No secret may be baked into the image.

    rule name "no_secrets_in_build", severity "error", where = str(ins.line).
    For every instruction:
      1. If it is ENV or ARG, look at each (key, value) of env_pairs(ins):
         a. looks_like_secret_value(value)            -> a finding (message contains the key)
         b. else looks_like_secret_name(key) and (it is an ARG, or the value is non-empty)
                                                      -> a finding (message contains the key)
            ARG: mention "secret" in the message (hint: RUN --mount=type=secret).
            ENV ANTHROPIC_API_KEY= (empty) is a placeholder, not a leak: no finding.
      2. If step 1 did NOT already report a key-shaped VALUE for this instruction, check the
         whole text ins.args + "\\n" + ins.heredoc with looks_like_secret_value -> one finding.
         (This catches RUN curl -H "x-api-key: sk-ant-..." and secrets in heredocs.)
    So ENV ANTHROPIC_API_KEY=sk-ant-... gives exactly ONE finding (1a), not two.
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement rule_no_secrets_in_build")


# ------------------------------------------------------------------ exercise 6
def rule_iam_least_privilege(statements: Iterable[PolicyStatement]) -> list[Finding]:
    """Least privilege, statement by statement. rule name "iam_least_privilege", where = st.where.

    Skip statements whose effect is "Deny" (case-insensitive). For each other statement:
      1. for EACH action a (compare lower-cased, stripped):
           a == "*" or a ends with ":*"     -> error, message contains the action as written
           else "*" in a  ("s3:Get*")       -> warning, message contains the action as written
      2. not_actions is non-empty           -> one error, message contains "not_actions"
      3. let star = any resource equals "*"; acts = the set of lower-cased actions
           star and "iam:passrole" in acts  -> one error, message contains "PassRole"
           elif star and not (acts and acts <= STAR_ONLY_ACTIONS)
                                            -> one warning, message contains "'*'" and the
                                               sorted lower-cased actions NOT in STAR_ONLY_ACTIONS
                                               joined with ", "
    Trust policies (has_principals, no resources) produce nothing in step 3 because star is False.
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement rule_iam_least_privilege")


# ------------------------------------------------------------------ exercise 7
def monthly_cost(cfg: DeployConfig, prices: dict = PRICES) -> dict:
    """Monthly AWS cost of the deployment, as explained line items.

    Return {"items": {...}, "total": float, "per_day": float} where items has EXACTLY these
    keys (USD), with h = cfg.hours and f = prices["fargate"][cfg.arch]:
      fargate_cpu      tasks_avg * vcpu * h * f["vcpu_hour"]
      fargate_memory   tasks_avg * memory_gb * h * f["gb_hour"]
      alb_hours        alb_count * h * prices["alb_hour"]
      alb_lcu          alb_count * lcu_avg * h * prices["lcu_hour"]
      public_ipv4      ((tasks_avg if task_public_ip else 0) + alb_count * azs) * h * prices["public_ipv4_hour"]
                       (every running task with a public IP, plus one address per AZ per ALB)
      nat_gateway      nat_gateways * h * prices["nat_hour"] + nat_gb * prices["nat_gb"]
      vpc_endpoints    interface_endpoints * azs * h * prices["vpce_hour_per_az"]
      secrets_manager  secrets * prices["secret_month"] + secret_api_calls / 10_000 * prices["secret_per_10k_calls"]
      cloudwatch_logs  log_gb * (prices["logs_ingest_gb"] + prices["logs_store_gb_month"])
      ecr_storage      image_gb * prices["ecr_gb_month"]
      alarms           alarms * prices["alarm_month"]
    total = sum of the items; per_day = total * 24 / h (0.0 when h == 0).
    Raise KeyError (naturally, from the dict lookup) for an unknown cfg.arch.
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement monthly_cost")

"""Your code for lesson 27. Each part is checked by tests in ./tests.

The reference versions live in deploykit/ (dockerfile.py, terraform.py, cost.py).
Try not to read them before your tests pass. Stuck? HINTS.md in this folder has graded hints.

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

    Returns [] or exactly ONE Finding("runs_as_non_root", "error", where, message).
    - The user a stage runs as is set by its last USER ("app:app" means user "app"). A
      stage without USER inherits from its base: an earlier stage it is built FROM (by
      alias, case-insensitive, or by index), or an external image, which runs as root
      unless its name contains "nonroot" (gcr.io/distroless/python3-debian12:nonroot).
    - Root means "root" or "0" (case-insensitive).
    - Final stage as root: message contains "root"; where = str(line) of the final
      stage's last USER, or of its FROM if it has none.
    - No FROM at all: one finding, where "1", message "no FROM instruction".

    Stuck? HINTS.md -> rule_runs_as_non_root
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement rule_runs_as_non_root")


def rule_no_secrets_in_build(instrs: list[Instruction]) -> list[Finding]:
    """No secret may be baked into the image.

    Findings: Finding("no_secrets_in_build", "error", str(ins.line), message).
    Must be reported:
      - ENV or ARG whose value looks like a real key (message contains the variable name);
      - ENV with a secret-looking NAME and a non-empty value (message contains the name);
      - ARG with a secret-looking name, even without a value (message contains the name
        and the word "secret": the fix is RUN --mount=type=secret);
      - a key-shaped value anywhere else in an instruction or its heredoc
        (RUN curl -H "x-api-key: sk-ant-...").
    Not reported: ENV ANTHROPIC_API_KEY= (empty) is a placeholder, not a leak.
    One leak, one finding: ENV ANTHROPIC_API_KEY=sk-ant-... gives exactly ONE, not two.
    Use the helpers listed at the top of this file.

    Stuck? HINTS.md -> rule_no_secrets_in_build
    """
    # TODO(ex5)
    raise NotImplementedError("exercise 5: implement rule_no_secrets_in_build")


# ------------------------------------------------------------------ exercise 6
def rule_iam_least_privilege(statements: Iterable[PolicyStatement]) -> list[Finding]:
    """Least privilege, statement by statement:
    Finding("iam_least_privilege", severity, st.where, message). Deny statements
    (effect "Deny", any case) produce nothing. For an Allow statement:
      - each full wildcard action ("*", "s3:*", any case) -> error naming the action as written;
      - each partial wildcard action ("s3:Get*")          -> warning naming it as written;
      - not_actions used at all                           -> one error, message contains "not_actions";
      - Resource "*" together with iam:PassRole           -> one error, message contains "PassRole";
      - otherwise Resource "*" with any action that does not require it (that is, not in
        STAR_ONLY_ACTIONS) -> one warning; the message contains "'*'" and those actions,
        lower-cased, sorted, joined with ", ".
    Trust policies (has_principals, no resources) have no Resource "*" warning.

    Stuck? HINTS.md -> rule_iam_least_privilege
    """
    # TODO(ex6)
    raise NotImplementedError("exercise 6: implement rule_iam_least_privilege")


# ------------------------------------------------------------------ exercise 7
def monthly_cost(cfg: DeployConfig, prices: dict = PRICES) -> dict:
    """Monthly AWS cost of the deployment, as explained line items.

    Return {"items": {...}, "total": float, "per_day": float}. items has EXACTLY these
    keys, in USD for the month of cfg.hours running hours, priced from `prices`
    (Fargate rates from prices["fargate"][cfg.arch]):
      fargate_cpu, fargate_memory   the average number of tasks, each with its vCPU / GB
      alb_hours, alb_lcu            each ALB's hours, and its average LCUs per hour
      public_ipv4                   every running task with a public IP, plus one address
                                    per AZ per ALB
      nat_gateway                   NAT gateway hours plus the data processed (nat_gb)
      vpc_endpoints                 each interface endpoint, in every AZ
      secrets_manager               secrets per month plus API calls (priced per 10,000)
      cloudwatch_logs               log GB ingested and stored
      ecr_storage, alarms           per GB-month / per alarm-month
    total = sum of the items; per_day = the total for 24 running hours (0.0 when hours == 0).
    An unknown cfg.arch raises KeyError (naturally, from the dict lookup).
    cfg fields: vcpu, memory_gb, arch, tasks_avg, hours, alb_count, lcu_avg, azs,
      task_public_ip, nat_gateways, nat_gb, interface_endpoints, secrets,
      secret_api_calls, log_gb, image_gb, alarms.
    prices keys: fargate[arch]["vcpu_hour" | "gb_hour"], alb_hour, lcu_hour,
      public_ipv4_hour, nat_hour, nat_gb, vpce_hour_per_az, secret_month,
      secret_per_10k_calls, logs_ingest_gb, logs_store_gb_month, ecr_gb_month, alarm_month.

    Stuck? HINTS.md -> monthly_cost
    """
    # TODO(ex7)
    raise NotImplementedError("exercise 7: implement monthly_cost")

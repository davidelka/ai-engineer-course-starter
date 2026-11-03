"""Static checks for the lesson 27 Terraform (reference implementation).

Parses .tf files with python-hcl2 (pure Python, no terraform binary, no AWS account)
and runs the lesson's rules: least-privilege IAM, no plaintext secrets, separated
task/execution roles, log retention, pinned providers, open ingress.

    doc = load_tf("labs/27-deployment/terraform")
    findings = lint_terraform(doc)

This is NOT a replacement for `terraform validate`, `terraform plan`, tflint, Checkov
or Trivy's misconfiguration scanner. It checks the handful of rules this lesson is about,
in code you can read.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Union

from .dockerfile import looks_like_secret_name, looks_like_secret_value
from .findings import Finding


# ------------------------------------------------------------------ loading
def _unquote(v: Any) -> Any:
    if isinstance(v, str) and len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        inner = v[1:-1]
        # a quoted string that is ONLY an interpolation is an expression
        return inner
    return v


def normalize(obj: Any) -> Any:
    """python-hcl2 >= 7 keeps the quotes of string literals and marks blocks with
    __is_block__. Strip both, so literals are plain strings and expressions stay '${...}'."""
    if isinstance(obj, dict):
        return {_unquote(k): normalize(v) for k, v in obj.items() if k != "__is_block__"}
    if isinstance(obj, list):
        return [normalize(x) for x in obj]
    return _unquote(obj)


def is_expr(v: Any) -> bool:
    """True for a Terraform expression (a reference, a function call), False for a literal."""
    return isinstance(v, str) and "${" in v


@dataclass
class Block:
    kind: str  # "resource" | "data"
    type: str  # "aws_iam_role"
    name: str  # "exec"
    body: dict
    file: str = ""

    @property
    def address(self) -> str:
        return f"{'data.' if self.kind == 'data' else ''}{self.type}.{self.name}"


@dataclass
class TfDoc:
    resources: list = field(default_factory=list)
    data: list = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    locals: dict = field(default_factory=dict)
    terraform: list = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    files: list = field(default_factory=list)

    def of_type(self, type_: str, kind: str = "resource") -> list:
        return [b for b in (self.resources if kind == "resource" else self.data) if b.type == type_]


def _merge(doc: TfDoc, raw: dict, fname: str) -> None:
    raw = normalize(raw)
    for kind, target in (("resource", doc.resources), ("data", doc.data)):
        for entry in raw.get(kind, []):
            for type_, named in entry.items():
                for name, body in named.items():
                    target.append(Block(kind, type_, name, body if isinstance(body, dict) else {}, fname))
    for entry in raw.get("variable", []):
        for name, body in entry.items():
            doc.variables[name] = body or {}
    for entry in raw.get("locals", []):
        doc.locals.update(entry)
    for entry in raw.get("output", []):
        for name, body in entry.items():
            doc.outputs[name] = body
    doc.terraform.extend(raw.get("terraform", []))


def load_tf(src: Union[str, Path], text: Optional[str] = None) -> TfDoc:
    """Load a directory of .tf files, one .tf file, or (with text=...) a string."""
    import hcl2

    doc = TfDoc()
    if text is not None:
        _merge(doc, hcl2.loads(text), str(src))
        doc.files.append(str(src))
        return doc
    p = Path(src)
    files = sorted(p.glob("*.tf")) if p.is_dir() else [p]
    for f in files:
        with open(f, encoding="utf-8") as fh:
            _merge(doc, hcl2.load(fh), f.name)
        doc.files.append(f.name)
    return doc


# ------------------------------------------------------------------ IAM statements
@dataclass
class PolicyStatement:
    where: str  # "data.aws_iam_policy_document.exec[0]" or "fixture.json[2]"
    effect: str = "Allow"
    actions: list = field(default_factory=list)
    not_actions: list = field(default_factory=list)
    resources: list = field(default_factory=list)
    not_resources: list = field(default_factory=list)
    has_principals: bool = False  # trust policies (who may assume a role) have principals, not resources
    sid: str = ""


def _as_list(v) -> list:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def statements_from_tf(doc: TfDoc) -> list[PolicyStatement]:
    """Statements of every data "aws_iam_policy_document" block."""
    out = []
    for b in doc.of_type("aws_iam_policy_document", "data"):
        for k, st in enumerate(_as_list(b.body.get("statement"))):
            out.append(PolicyStatement(
                where=f"{b.file}: {b.address}[{k}]" if b.file else f"{b.address}[{k}]",
                effect=st.get("effect", "Allow"),
                actions=_as_list(st.get("actions")), not_actions=_as_list(st.get("not_actions")),
                resources=_as_list(st.get("resources")), not_resources=_as_list(st.get("not_resources")),
                has_principals=bool(st.get("principals")), sid=st.get("sid", "")))
    return out


def statements_from_json(policy: Union[str, dict], where: str = "policy") -> list[PolicyStatement]:
    """Statements of a JSON IAM policy (Action/Resource may be a string or a list)."""
    if isinstance(policy, str):
        policy = json.loads(policy)
    out = []
    for k, st in enumerate(_as_list(policy.get("Statement"))):
        out.append(PolicyStatement(
            where=f"{where}[{k}]", effect=st.get("Effect", "Allow"),
            actions=_as_list(st.get("Action")), not_actions=_as_list(st.get("NotAction")),
            resources=_as_list(st.get("Resource")), not_resources=_as_list(st.get("NotResource")),
            has_principals="Principal" in st or "NotPrincipal" in st, sid=st.get("Sid", "")))
    return out


# Actions that do not support resource-level permissions: "*" is the only valid Resource.
STAR_ONLY_ACTIONS = {
    "ecr:getauthorizationtoken", "sts:getcalleridentity", "cloudwatch:putmetricdata",
    "xray:puttracesegments", "xray:puttelemetryrecords",
}


def rule_iam_least_privilege(statements: Iterable[PolicyStatement]) -> list[Finding]:
    """Least privilege, statement by statement (Deny statements are skipped):
    - an action that is "*" or "<service>:*"            -> error
    - any other action with a wildcard ("s3:Get*")       -> warning
    - not_actions in an Allow statement                  -> error (allows everything else)
    - "iam:PassRole" with resource "*"                   -> error (privilege escalation)
    - resource "*" with an action outside STAR_ONLY_ACTIONS -> warning
      (skip for trust policies: has_principals and no resources)"""
    out: list[Finding] = []
    for st in statements:
        if str(st.effect).lower() == "deny":
            continue
        for a in st.actions:
            a_l = str(a).strip().lower()
            if a_l == "*" or a_l.endswith(":*"):
                out.append(Finding("iam_least_privilege", "error", st.where,
                                   f"wildcard action {a!r}: list the exact actions the role needs"))
            elif "*" in a_l:
                out.append(Finding("iam_least_privilege", "warning", st.where,
                                   f"partial wildcard {a!r} may grant more than you think: list exact actions"))
        if st.not_actions:
            out.append(Finding("iam_least_privilege", "error", st.where,
                               "Allow with not_actions allows every action except the listed ones"))
        star = any(str(r).strip() == "*" for r in st.resources)
        acts = {str(a).strip().lower() for a in st.actions}
        if star and "iam:passrole" in acts:
            out.append(Finding("iam_least_privilege", "error", st.where,
                               "iam:PassRole on '*' lets the holder hand ANY role to a service: scope it to role ARNs"))
        elif star and not (acts and acts <= STAR_ONLY_ACTIONS):
            extra = sorted(acts - STAR_ONLY_ACTIONS)
            out.append(Finding("iam_least_privilege", "warning", st.where,
                               f"resource '*' for {', '.join(extra) or 'these actions'}: scope it to ARNs"))
    return out


# ------------------------------------------------------------------ other rules
def _walk(obj, path=""):
    """Yield (path, value) for every leaf and dict in a nested structure."""
    if isinstance(obj, dict):
        yield path, obj
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def rule_tf_no_plaintext_secrets(doc: TfDoc) -> list[Finding]:
    out: list[Finding] = []
    for b in doc.of_type("aws_secretsmanager_secret_version"):
        v = b.body.get("secret_string")
        if v is not None:
            sev = "warning" if is_expr(v) else "error"
            out.append(Finding("no_plaintext_secrets", sev, b.address,
                               "secret_string is stored in plain text in the Terraform state: use secret_string_wo "
                               "(Terraform >= 1.11) or put the value with the AWS CLI"))
    for name, body in doc.variables.items():
        if looks_like_secret_name(name):
            if "default" in body:
                out.append(Finding("no_plaintext_secrets", "error", f"var.{name}",
                                   "a secret variable must not have a default (it would live in git)"))
            if body.get("sensitive") is not True:
                out.append(Finding("no_plaintext_secrets", "warning", f"var.{name}",
                                   "mark secret variables sensitive = true so plan/apply output hides them"))
    sources = [(f"local.{k}", v) for k, v in doc.locals.items()] + [(b.address, b.body) for b in doc.resources]
    for where, obj in sources:
        for path, node in _walk(obj):
            if isinstance(node, dict):
                for item in _as_list(node.get("environment")):
                    if isinstance(item, dict) and looks_like_secret_name(str(item.get("name", ""))):
                        out.append(Finding("no_plaintext_secrets", "error", where,
                                           f"environment variable {item.get('name')} looks like a secret: "
                                           "use the container's secrets list with valueFrom"))
                for item in _as_list(node.get("secrets")):
                    if isinstance(item, dict) and "valueFrom" in item:
                        vf = item["valueFrom"]
                        if not (is_expr(vf) or re.match(r"arn:aws[\w-]*:(secretsmanager|ssm):", str(vf))):
                            out.append(Finding("no_plaintext_secrets", "error", where,
                                               f"secret {item.get('name')}: valueFrom must be a Secrets Manager "
                                               "or SSM Parameter Store ARN"))
            elif isinstance(node, str) and not is_expr(node) and looks_like_secret_value(node):
                out.append(Finding("no_plaintext_secrets", "error", where, f"{path} contains a literal that looks like a key"))
    return out


def rule_tf_roles_separated(doc: TfDoc) -> list[Finding]:
    out = []
    for b in doc.of_type("aws_ecs_task_definition"):
        ex, task = b.body.get("execution_role_arn"), b.body.get("task_role_arn")
        if not ex:
            out.append(Finding("roles_separated", "warning", b.address,
                               "no execution_role_arn: ECS cannot pull from ECR, write logs or read secrets"))
        if not task:
            out.append(Finding("roles_separated", "info", b.address,
                               "no task_role_arn: fine if the app never calls AWS, but make it explicit"))
        if ex and task and ex == task:
            out.append(Finding("roles_separated", "error", b.address,
                               "execution role and task role are the same: the app gets the agent's permissions"))
    return out


def rule_tf_log_retention(doc: TfDoc) -> list[Finding]:
    return [Finding("log_retention", "warning", b.address,
                    "no retention_in_days: logs are kept (and billed) forever")
            for b in doc.of_type("aws_cloudwatch_log_group") if "retention_in_days" not in b.body]


def rule_tf_provider_pinned(doc: TfDoc) -> list[Finding]:
    out = []
    tf = {}
    for t in doc.terraform:
        tf.update(t)
    if "required_version" not in tf:
        out.append(Finding("provider_pinned", "warning", "terraform", "no required_version for the Terraform CLI"))
    rp = {}
    for x in _as_list(tf.get("required_providers")):
        rp.update(x)
    aws = rp.get("aws")
    if not isinstance(aws, dict) or not aws.get("version"):
        out.append(Finding("provider_pinned", "warning", "terraform",
                           "aws provider has no version constraint: a new major version can change behavior"))
    return out


def _ports(body: dict) -> tuple[int, int]:
    try:
        return int(body.get("from_port", 0)), int(body.get("to_port", 0))
    except (TypeError, ValueError):
        return -1, -1


def rule_tf_open_ingress(doc: TfDoc) -> list[Finding]:
    out = []
    rules = [(b.address, b.body) for b in doc.of_type("aws_vpc_security_group_ingress_rule")]
    for b in doc.of_type("aws_security_group"):
        rules += [(b.address, r) for r in _as_list(b.body.get("ingress")) if isinstance(r, dict)]
    for where, r in rules:
        cidrs = _as_list(r.get("cidr_blocks")) + _as_list(r.get("cidr_ipv4"))
        if "0.0.0.0/0" in cidrs:
            lo, hi = _ports(r)
            if not (lo == hi and lo in (80, 443)):
                out.append(Finding("open_ingress", "warning", where,
                                   f"port {lo}-{hi} open to the whole internet: only the load balancer should be public"))
    return out


def rule_tf_budget(doc: TfDoc) -> list[Finding]:
    if doc.of_type("aws_budgets_budget"):
        return []
    return [Finding("budget", "info", "account",
                    "no aws_budgets_budget here: make sure a budget exists (labs/27-deployment/budget)")]


TF_RULES = [rule_tf_no_plaintext_secrets, rule_tf_roles_separated, rule_tf_log_retention,
            rule_tf_provider_pinned, rule_tf_open_ingress, rule_tf_budget]


def lint_terraform(doc: TfDoc, *, rules: Optional[dict] = None) -> list[Finding]:
    """All Terraform rules. `rules={"rule_iam_least_privilege": fn}` swaps in your version."""
    iam = (rules or {}).get("rule_iam_least_privilege", rule_iam_least_privilege)
    out = list(iam(statements_from_tf(doc)))
    for rule in TF_RULES:
        out.extend((rules or {}).get(rule.__name__, rule)(doc))
    return out

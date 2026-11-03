"""Monthly cost of Company Brain at 200 employees: model tokens + AWS. One command, two models.

    python -m cbrain cost

Tokens: archkit's cost model (lesson 19) on the `budget` section of arch/company_brain.arch.yaml (request
rates, calls per request, token sizes, prompt-cache hit rate). Prices from llmkit/pricing.py.
AWS: deploykit's model (lesson 27) for what deploy/terraform creates: one Fargate task (0.5 vCPU, 2 GB,
x86_64, always on), one ALB in 2 AZs, public IPv4s, no NAT gateway, 2 secrets, logs, ECR. Plus EFS, which
deploykit does not model: price from the EFS pricing page (us-east-1, Standard storage, checked
2026-11-02, see the README), for ~1 GB of state and index.
"""

from __future__ import annotations

from . import PROJECT

ARCH = PROJECT / "arch" / "company_brain.arch.yaml"
EFS_GB_MONTH = 0.30          # EFS Standard storage, us-east-1, USD per GB-month
EFS_GB = 1.0


def monthly_costs(employees: int = 200) -> dict:
    from archkit import load_spec
    from archkit.cost import monthly_cost as token_month, profiles_from_spec
    from deploykit import DeployConfig, monthly_cost as aws_month
    spec = load_spec(ARCH)
    scale = employees / 200.0
    paths = {}
    for p in spec.budget.paths:
        m = token_month(profiles_from_spec(p), p.requests_per_day * scale, days=p.days,
                        prompt_cache_hit_rate=p.prompt_cache_hit_rate,
                        response_cache_hit_rate=p.response_cache_hit_rate)
        paths[p.name] = {"requests_month": m["requests_month"], "per_request_usd": m["per_request_usd"],
                         "monthly_usd": m["total_monthly_usd"]}
    tokens = sum(v["monthly_usd"] for v in paths.values())
    cfg = DeployConfig(vcpu=0.5, memory_gb=2.0, tasks_avg=1.0, secrets=2, log_gb=0.5, image_gb=1.5, alarms=2)
    aws = aws_month(cfg)
    aws_items = dict(aws.get("items", aws))
    efs = EFS_GB * EFS_GB_MONTH
    aws_total = float(aws["total"]) + efs if "total" in aws else sum(v for v in aws_items.values()
                                                                     if isinstance(v, (int, float))) + efs
    return {"employees": employees, "token_paths": paths, "tokens_usd": tokens, "aws": aws, "efs_usd": efs,
            "aws_usd": aws_total, "total_usd": tokens + aws_total,
            "per_employee_usd": (tokens + aws_total) / employees}


def format_costs(c: dict) -> str:
    L = [f"Company Brain at {c['employees']} employees, per month (22 working days)", "",
         "Model tokens (archkit, Claude Haiku 5.5 via the gateway):"]
    for name, p in c["token_paths"].items():
        L.append(f"  {name:<15} {p['requests_month']:>7.0f} requests x ${p['per_request_usd']:.5f} = ${p['monthly_usd']:.2f}")
    L.append(f"  tokens total   ${c['tokens_usd']:.2f}")
    L.append("")
    L.append("AWS (deploykit: Fargate 0.5 vCPU / 2 GB always on, ALB, 2 AZ, no NAT, 2 secrets) + EFS:")
    items = c["aws"].get("items", {})
    for k, v in items.items():
        if isinstance(v, (int, float)) and v >= 0.005:
            L.append(f"  {k:<18} ${v:.2f}")
    L.append(f"  efs (~1 GB)        ${c['efs_usd']:.2f}")
    L.append(f"  AWS total      ${c['aws_usd']:.2f}")
    L.append("")
    L.append(f"TOTAL ${c['total_usd']:.2f}/month  =  ${c['per_employee_usd']:.3f} per employee. The ALB and the "
             "always-on task are most of it; the tokens are a rounding error at this scale.")
    return "\n".join(L)

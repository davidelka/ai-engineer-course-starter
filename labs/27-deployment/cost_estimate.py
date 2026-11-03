"""What will the AWS deployment cost? Line items, per month, per day and per lab session.

    python labs/27-deployment/cost_estimate.py                     # the lab's Terraform, 24/7
    python labs/27-deployment/cost_estimate.py --hours 3           # one 3-hour lab session
    python labs/27-deployment/cost_estimate.py --arch ARM64
    python labs/27-deployment/cost_estimate.py --private-nat       # private subnets + 1 NAT gateway
    python labs/27-deployment/cost_estimate.py --private-endpoints # private subnets + 4 VPC endpoints
    python labs/27-deployment/cost_estimate.py --tasks 2.5 --vcpu 0.5 --memory 1

Uses your monthly_cost from mine.py (exercise 7), or the reference with --reference.
Prices: us-east-1, on-demand, November 2026 (deploykit/cost.py lists the sources).
Free tier and credits are ignored on purpose. The model API (Anthropic) is billed
separately, per token: see llmkit/pricing.py.
"""

from __future__ import annotations

import argparse
from dataclasses import fields

from _lab import pick

from deploykit.cost import EXPLAIN, HOURS_PER_MONTH, DeployConfig


def main() -> None:
    ap = argparse.ArgumentParser(description="Monthly AWS cost estimate for the lesson 27 setup")
    ap.add_argument("--hours", type=float, default=HOURS_PER_MONTH, help="hours the stack exists (730 = a month)")
    ap.add_argument("--vcpu", type=float, default=0.25)
    ap.add_argument("--memory", type=float, default=0.5, help="GB")
    ap.add_argument("--arch", default="X86_64", choices=["X86_64", "ARM64"])
    ap.add_argument("--tasks", type=float, default=1.0, help="average running tasks")
    ap.add_argument("--private-nat", action="store_true", help="tasks in private subnets, one NAT gateway")
    ap.add_argument("--nat-gb", type=float, default=5.0, help="GB through the NAT per month (with --private-nat)")
    ap.add_argument("--private-endpoints", action="store_true", help="private subnets + 4 interface endpoints, no NAT")
    ap.add_argument("--log-gb", type=float, default=0.2)
    ap.add_argument("--reference", action="store_true")
    a = ap.parse_args()

    cfg = DeployConfig(vcpu=a.vcpu, memory_gb=a.memory, arch=a.arch, tasks_avg=a.tasks, hours=a.hours, log_gb=a.log_gb)
    if a.private_nat:
        cfg.task_public_ip, cfg.nat_gateways, cfg.nat_gb = False, 1, a.nat_gb
    if a.private_endpoints:
        cfg.task_public_ip, cfg.interface_endpoints = False, 4
    if a.hours < HOURS_PER_MONTH:  # a short session: monthly items are prorated by the hour
        scale = a.hours / HOURS_PER_MONTH
        cfg.log_gb *= scale
        cfg.image_gb *= scale
        cfg.alarms *= scale
        cfg.secrets *= scale
        cfg.nat_gb *= scale

    res = pick("monthly_cost", a.reference)(cfg)
    label = "month" if a.hours >= HOURS_PER_MONTH else f"{a.hours:g} hours"
    print("config: " + ", ".join(f"{f.name}={getattr(cfg, f.name):g}" if isinstance(getattr(cfg, f.name), float)
                                 else f"{f.name}={getattr(cfg, f.name)}" for f in fields(cfg)))
    print(f"\nline items for one {label} (USD):")
    for k, v in sorted(res["items"].items(), key=lambda kv: -kv[1]):
        if v == 0:
            continue
        share = v / res["total"] * 100 if res["total"] else 0
        print(f"  {k:16} {v:9.2f}  {share:5.1f}%  {EXPLAIN.get(k, '')}")
    print(f"  {'TOTAL':16} {res['total']:9.2f}")
    print(f"\nper day: ${res['per_day']:.2f}   per hour: ${res['per_day'] / 24:.3f}")
    fixed = res["items"]["alb_hours"] + res["items"]["public_ipv4"] + res["items"]["nat_gateway"] + res["items"]["vpc_endpoints"]
    print(f"the network around the app (ALB, public IPs, NAT, endpoints): ${fixed:.2f} "
          f"({fixed / res['total'] * 100:.0f}% of the total)" if res["total"] else "")


if __name__ == "__main__":
    main()

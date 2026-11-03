"""Monthly cost model for the lesson 27 AWS setup (reference implementation).

Prices: US East (N. Virginia), on-demand, checked on the AWS pricing pages on 2026-11-01.
Prices change: check them before you quote a number to anyone.
  Fargate        https://aws.amazon.com/fargate/pricing/
  ALB            https://aws.amazon.com/elasticloadbalancing/pricing/
  Public IPv4 and NAT gateway   https://aws.amazon.com/vpc/pricing/
  Interface VPC endpoints       https://aws.amazon.com/privatelink/pricing/
  Secrets Manager https://aws.amazon.com/secrets-manager/pricing/
  CloudWatch      https://aws.amazon.com/cloudwatch/pricing/
  ECR             https://aws.amazon.com/ecr/pricing/
Free tiers and credits are ignored on purpose: the model answers "what will this cost
once the free tier is gone", which is the number you plan with.
"""

from __future__ import annotations

from dataclasses import dataclass

PRICES = {
    "fargate": {  # per vCPU-hour and per GB-hour of memory
        "X86_64": {"vcpu_hour": 0.0404784, "gb_hour": 0.004446},
        "ARM64": {"vcpu_hour": 0.03237984, "gb_hour": 0.00356004},
    },
    "alb_hour": 0.0225,
    "lcu_hour": 0.008,
    "public_ipv4_hour": 0.005,  # every public IPv4 address, in use or idle
    "nat_hour": 0.045,
    "nat_gb": 0.045,
    "vpce_hour_per_az": 0.01,  # one interface endpoint in one AZ
    "secret_month": 0.40,
    "secret_per_10k_calls": 0.05,
    "logs_ingest_gb": 0.50,
    "logs_store_gb_month": 0.03,
    "ecr_gb_month": 0.10,
    "alarm_month": 0.10,
}

HOURS_PER_MONTH = 730


@dataclass
class DeployConfig:
    """What the Terraform in labs/27-deployment/terraform creates, as numbers."""

    vcpu: float = 0.25  # task size: Fargate allows 0.25 vCPU with 0.5, 1 or 2 GB
    memory_gb: float = 0.5
    arch: str = "X86_64"  # or "ARM64" (Graviton): about 20% cheaper, needs an arm64 image
    tasks_avg: float = 1.0  # average number of running tasks over the month (autoscaling!)
    hours: float = HOURS_PER_MONTH  # hours the stack exists this month
    alb_count: int = 1
    lcu_avg: float = 0.05  # average LCUs; a quiet internal service uses a small fraction of one
    azs: int = 2  # an ALB needs at least two AZs; it has one public IPv4 per AZ
    task_public_ip: bool = True  # public subnet + public IP instead of a NAT gateway
    nat_gateways: int = 0
    nat_gb: float = 0.0  # GB through the NAT gateways per month
    interface_endpoints: int = 0  # e.g. ecr.api, ecr.dkr, logs, secretsmanager
    secrets: int = 1
    secret_api_calls: int = 0  # ECS reads the secret once per task start: tiny
    log_gb: float = 0.2  # GB of logs ingested per month (and stored)
    image_gb: float = 0.4  # GB stored in ECR (the lifecycle policy keeps the last 5 images)
    alarms: int = 2  # target-tracking autoscaling creates two CloudWatch alarms (counted conservatively)


def monthly_cost(cfg: DeployConfig, prices: dict = PRICES) -> dict:
    """Line items in USD for one month (cfg.hours), plus the total and the cost per day."""
    f = prices["fargate"][cfg.arch]
    h = cfg.hours
    items = {
        "fargate_cpu": cfg.tasks_avg * cfg.vcpu * h * f["vcpu_hour"],
        "fargate_memory": cfg.tasks_avg * cfg.memory_gb * h * f["gb_hour"],
        "alb_hours": cfg.alb_count * h * prices["alb_hour"],
        "alb_lcu": cfg.alb_count * cfg.lcu_avg * h * prices["lcu_hour"],
        "public_ipv4": ((cfg.tasks_avg if cfg.task_public_ip else 0) + cfg.alb_count * cfg.azs)
        * h * prices["public_ipv4_hour"],
        "nat_gateway": cfg.nat_gateways * h * prices["nat_hour"] + cfg.nat_gb * prices["nat_gb"],
        "vpc_endpoints": cfg.interface_endpoints * cfg.azs * h * prices["vpce_hour_per_az"],
        "secrets_manager": cfg.secrets * prices["secret_month"]
        + cfg.secret_api_calls / 10_000 * prices["secret_per_10k_calls"],
        "cloudwatch_logs": cfg.log_gb * (prices["logs_ingest_gb"] + prices["logs_store_gb_month"]),
        "ecr_storage": cfg.image_gb * prices["ecr_gb_month"],
        "alarms": cfg.alarms * prices["alarm_month"],
    }
    total = sum(items.values())
    return {"items": items, "total": total, "per_day": total * 24 / h if h else 0.0}


EXPLAIN = {
    "fargate_cpu": "vCPU-hours of the running tasks",
    "fargate_memory": "GB-hours of memory of the running tasks",
    "alb_hours": "the load balancer exists: billed every hour, even with zero traffic",
    "alb_lcu": "load balancer capacity units: connections, bytes, rule evaluations",
    "public_ipv4": "every public IPv4: one per running task + one per ALB availability zone",
    "nat_gateway": "lets tasks in private subnets reach the internet",
    "vpc_endpoints": "private access to AWS APIs without a NAT gateway, per endpoint per AZ",
    "secrets_manager": "per secret per month + API calls",
    "cloudwatch_logs": "ingestion + storage of the container logs",
    "ecr_storage": "image storage in the registry",
    "alarms": "CloudWatch alarms (autoscaling creates them)",
}

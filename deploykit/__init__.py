"""deploykit: lesson 27 (Containers and Public-Cloud Deployment) reference code.

  dockerfile.py  Dockerfile parser + lint rules (non-root, pinned base, no secrets, ...)
  terraform.py   Terraform checks via python-hcl2 (least-privilege IAM, secrets, roles, ...)
  cost.py        monthly AWS cost model for the ECS Fargate + ALB setup
  findings.py    the Finding type shared by the checks

Pure Python: no Docker, no terraform binary, no AWS account needed.
"""

from .cost import PRICES, DeployConfig, monthly_cost
from .dockerfile import Instruction, lint_dockerfile, parse_dockerfile
from .findings import Finding, errors, format_findings

__all__ = ["PRICES", "DeployConfig", "monthly_cost", "Instruction", "lint_dockerfile",
           "parse_dockerfile", "Finding", "errors", "format_findings"]

"""One finding of a static check, shared by the Dockerfile and Terraform linters."""

from __future__ import annotations

from dataclasses import dataclass

SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True)
class Finding:
    rule: str  # e.g. "base_image_pinned"
    severity: str  # "error" | "warning" | "info"
    where: str  # "Dockerfile:12", "data.aws_iam_policy_document.exec[1]", ...
    message: str

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}, got {self.severity!r}")


def errors(findings) -> list[Finding]:
    return [f for f in findings if f.severity == "error"]


def format_findings(findings, path: str = "") -> str:
    order = {s: i for i, s in enumerate(SEVERITIES)}
    lines = []
    for f in sorted(findings, key=lambda f: (order[f.severity], f.where)):
        where = f"{path}:{f.where}" if path and f.where[:1].isdigit() else f.where
        lines.append(f"  {f.severity.upper():7} {f.rule:24} {where:28} {f.message}")
    return "\n".join(lines)

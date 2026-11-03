"""Static checks for the lesson's rules: Dockerfiles, .dockerignore files, Terraform, IAM JSON.

    python labs/27-deployment/checks.py                       # everything in the lab
    python labs/27-deployment/checks.py labs/27-deployment/app/Dockerfile.single
    python labs/27-deployment/checks.py labs/27-deployment/terraform
    python labs/27-deployment/checks.py labs/27-deployment/fixtures/bad_iam.json
    python labs/27-deployment/checks.py --reference           # only the deploykit versions

Your functions from mine.py are used for: rule_runs_as_non_root, rule_no_secrets_in_build
(exercise 5) and rule_iam_least_privilege (exercise 6). Exit code 1 when any target has an
error, so the same command can gate a CI pipeline.

No Docker, terraform binary or AWS account needed. Real tools to compare with:
`docker build --check` (BuildKit's checks), hadolint, `terraform validate`, tflint,
Checkov, and `trivy config` (misconfigurations in Dockerfiles and Terraform).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _lab import LAB, ROOT, pick

from deploykit.dockerfile import lint_dockerfile
from deploykit.findings import errors, format_findings

DEFAULT_TARGETS = ["app/Dockerfile", "app/Dockerfile.single", "app/Dockerfile.baked",
                   "terraform", "budget", "fixtures/bad_iam.json", "fixtures/bad_task.tf"]


def ignore_file_for(dockerfile: Path):
    """BuildKit's lookup: <Dockerfile>.dockerignore next to the Dockerfile wins over
    .dockerignore at the root of the build context (here: the repo root)."""
    specific = dockerfile.with_name(dockerfile.name + ".dockerignore")
    if specific.exists():
        return specific
    root = ROOT / ".dockerignore"
    return root if root.exists() else None


def check_dockerfile(path: Path, reference: bool):
    ign = ignore_file_for(path)
    rules = {n: pick(n, reference) for n in ("rule_runs_as_non_root", "rule_no_secrets_in_build")}
    findings = lint_dockerfile(path.read_text(encoding="utf-8"),
                               ign.read_text(encoding="utf-8") if ign else None, rules=rules)
    return findings, f"ignore file: {ign.relative_to(ROOT) if ign else 'none'}"


def check_terraform(path: Path, reference: bool):
    try:
        from deploykit.terraform import lint_terraform, load_tf
    except ImportError:
        raise SystemExit("python-hcl2 is missing: uv pip install -r labs/27-deployment/requirements.txt")
    doc = load_tf(path)
    findings = lint_terraform(doc, rules={"rule_iam_least_privilege": pick("rule_iam_least_privilege", reference)})
    return findings, f"{len(doc.resources)} resources, {len(doc.data)} data sources"


def check_policy_json(path: Path, reference: bool):
    from deploykit.terraform import statements_from_json
    sts = statements_from_json(path.read_text(encoding="utf-8"), where=path.name)
    return pick("rule_iam_least_privilege", reference)(sts), f"{len(sts)} statements"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("targets", nargs="*", help="Dockerfile, .tf file, Terraform folder or IAM policy .json")
    ap.add_argument("--reference", action="store_true", help="use only the deploykit reference rules")
    ap.add_argument("--quiet", action="store_true", help="hide info findings")
    a = ap.parse_args()
    targets = [Path(t) for t in a.targets] or [LAB / t for t in DEFAULT_TARGETS]
    failed = 0
    for t in targets:
        t = t if t.is_absolute() else (Path.cwd() / t)
        if not t.exists():
            print(f"\n{t}: not found")
            failed += 1
            continue
        if t.is_dir() or t.suffix == ".tf":
            findings, note = check_terraform(t, a.reference)
        elif t.suffix == ".json":
            findings, note = check_policy_json(t, a.reference)
        else:
            findings, note = check_dockerfile(t, a.reference)
        if a.quiet:
            findings = [f for f in findings if f.severity != "info"]
        n_err = len(errors(findings))
        n_warn = sum(f.severity == "warning" for f in findings)
        rel = t.relative_to(ROOT) if t.is_relative_to(ROOT) else t
        print(f"\n{rel}  ({note})  -> {n_err} errors, {n_warn} warnings")
        if findings:
            print(format_findings(findings, path=t.name))
        failed += n_err > 0
    print(f"\n{len(targets) - failed}/{len(targets)} targets without errors")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

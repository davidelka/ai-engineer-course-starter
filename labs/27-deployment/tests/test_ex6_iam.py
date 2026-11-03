"""Exercise 6: least-privilege IAM."""

from pathlib import Path

import pytest

from deploykit.terraform import PolicyStatement, statements_from_json
from mine import rule_iam_least_privilege

LAB = Path(__file__).resolve().parent.parent


def S(actions=(), resources=("arn:aws:s3:::acme-docs/*",), **kw):
    return PolicyStatement(where=kw.pop("where", "t[0]"), actions=list(actions), resources=list(resources), **kw)


def sev(findings):
    return sorted(f.severity for f in findings)


def test_scoped_statement_is_clean():
    assert rule_iam_least_privilege([S(["s3:GetObject"])]) == []


def test_star_action():
    out = rule_iam_least_privilege([S(["*"])])
    assert sev(out) == ["error"] and out[0].rule == "iam_least_privilege" and out[0].where == "t[0]"
    assert "'*'" in out[0].message or '"*"' in out[0].message or "*" in out[0].message


def test_service_wildcard_case_insensitive():
    out = rule_iam_least_privilege([S(["S3:*"])])
    assert sev(out) == ["error"] and "S3:*" in out[0].message


def test_partial_wildcard_is_a_warning():
    out = rule_iam_least_privilege([S(["s3:Get*", "s3:ListBucket"])])
    assert sev(out) == ["warning"] and "s3:Get*" in out[0].message


def test_not_actions():
    out = rule_iam_least_privilege([S([], not_actions=["iam:*"])])
    assert sev(out) == ["error"] and "not_actions" in out[0].message


def test_deny_is_skipped():
    assert rule_iam_least_privilege([S(["*"], resources=["*"], effect="Deny")]) == []
    assert rule_iam_least_privilege([S(["*"], resources=["*"], effect="deny")]) == []


def test_star_resource_warning_lists_actions():
    out = rule_iam_least_privilege([S(["s3:GetObject", "ecr:GetAuthorizationToken"], resources=["*"])])
    assert sev(out) == ["warning"]
    assert "'*'" in out[0].message and "s3:getobject" in out[0].message
    assert "ecr:getauthorizationtoken" not in out[0].message


def test_star_only_actions_are_fine():
    assert rule_iam_least_privilege([S(["ecr:GetAuthorizationToken"], resources=["*"])]) == []


def test_passrole_star():
    out = rule_iam_least_privilege([S(["ecs:UpdateService", "iam:PassRole"], resources=["*"])])
    assert sev(out) == ["error"] and "PassRole" in out[0].message


def test_trust_policy_is_fine():
    st = S(["sts:AssumeRole"], resources=[], has_principals=True)
    assert rule_iam_least_privilege([st]) == []


def test_star_star_gives_error_and_warning():
    assert sev(rule_iam_least_privilege([S(["*"], resources=["*"])])) == ["error", "warning"]


def test_bad_iam_fixture():
    sts = statements_from_json((LAB / "fixtures" / "bad_iam.json").read_text(), where="bad")
    out = rule_iam_least_privilege(sts)
    errs = sorted(f.where for f in out if f.severity == "error")
    assert errs == ["bad[0]", "bad[1]", "bad[3]", "bad[4]"]
    assert not any(f.where in ("bad[5]", "bad[6]") for f in out)  # EcrLogin and the Deny are fine


def test_lab_terraform_is_least_privilege():
    pytest.importorskip("hcl2")
    from deploykit.terraform import load_tf, statements_from_tf
    sts = statements_from_tf(load_tf(LAB / "terraform"))
    assert len(sts) >= 5
    assert rule_iam_least_privilege(sts) == []


def test_bad_task_fixture():
    pytest.importorskip("hcl2")
    from deploykit.terraform import load_tf, statements_from_tf
    out = rule_iam_least_privilege(statements_from_tf(load_tf(LAB / "fixtures" / "bad_task.tf")))
    assert sev(out) == ["error", "warning"]

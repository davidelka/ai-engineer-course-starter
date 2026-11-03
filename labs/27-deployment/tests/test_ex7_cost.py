"""Exercise 7: the monthly cost model."""

import pytest

from deploykit.cost import PRICES, DeployConfig
from mine import monthly_cost

KEYS = {"fargate_cpu", "fargate_memory", "alb_hours", "alb_lcu", "public_ipv4", "nat_gateway",
        "vpc_endpoints", "secrets_manager", "cloudwatch_logs", "ecr_storage", "alarms"}


def test_shape():
    r = monthly_cost(DeployConfig())
    assert set(r) == {"items", "total", "per_day"}
    assert set(r["items"]) == KEYS
    assert r["total"] == pytest.approx(sum(r["items"].values()))


def test_lab_default_numbers():
    r = monthly_cost(DeployConfig())
    i = r["items"]
    assert i["fargate_cpu"] == pytest.approx(0.25 * 730 * 0.0404784)
    assert i["fargate_memory"] == pytest.approx(0.5 * 730 * 0.004446)
    assert i["alb_hours"] == pytest.approx(16.425)
    assert i["public_ipv4"] == pytest.approx(3 * 730 * 0.005)  # 1 task + 2 ALB AZs
    assert i["nat_gateway"] == 0 and i["vpc_endpoints"] == 0
    assert r["total"] == pytest.approx(37.42, abs=0.01)
    assert r["per_day"] == pytest.approx(r["total"] * 24 / 730)


def test_arm_is_cheaper():
    x86 = monthly_cost(DeployConfig())["items"]
    arm = monthly_cost(DeployConfig(arch="ARM64"))["items"]
    assert arm["fargate_cpu"] == pytest.approx(0.25 * 730 * 0.03237984)
    assert arm["fargate_cpu"] < x86["fargate_cpu"] and arm["alb_hours"] == x86["alb_hours"]


def test_private_with_nat():
    r = monthly_cost(DeployConfig(task_public_ip=False, nat_gateways=1, nat_gb=10))
    assert r["items"]["public_ipv4"] == pytest.approx(2 * 730 * 0.005)
    assert r["items"]["nat_gateway"] == pytest.approx(730 * 0.045 + 10 * 0.045)


def test_endpoints_per_az():
    r = monthly_cost(DeployConfig(task_public_ip=False, interface_endpoints=4, azs=2))
    assert r["items"]["vpc_endpoints"] == pytest.approx(4 * 2 * 730 * 0.01)


def test_scaling_tasks_and_short_session():
    r = monthly_cost(DeployConfig(tasks_avg=2.5, hours=3))
    assert r["items"]["fargate_cpu"] == pytest.approx(2.5 * 0.25 * 3 * 0.0404784)
    assert r["items"]["public_ipv4"] == pytest.approx((2.5 + 2) * 3 * 0.005)
    assert r["per_day"] == pytest.approx(r["total"] * 8)


def test_secrets_logs_ecr_alarms():
    r = monthly_cost(DeployConfig(secrets=2, secret_api_calls=20_000, log_gb=10, image_gb=1, alarms=3))
    i = r["items"]
    assert i["secrets_manager"] == pytest.approx(0.80 + 0.10)
    assert i["cloudwatch_logs"] == pytest.approx(10 * 0.53)
    assert i["ecr_storage"] == pytest.approx(0.10) and i["alarms"] == pytest.approx(0.30)


def test_custom_prices_are_used():
    cheap = {**PRICES, "alb_hour": 0.0}
    assert monthly_cost(DeployConfig(), cheap)["items"]["alb_hours"] == 0


def test_zero_hours():
    assert monthly_cost(DeployConfig(hours=0))["per_day"] == 0.0


def test_unknown_arch():
    with pytest.raises(KeyError):
        monthly_cost(DeployConfig(arch="RISCV"))

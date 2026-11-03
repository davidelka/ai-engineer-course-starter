"""Exercise 3: get_oncall_for_service, as a function and as a tool served by acme-mcp."""
import pytest
from conftest import run
from mcp import Client

import mine
from mcpkit.server import build_acme_server
from toolkit import ToolError

KEYS = {"service", "owner_team", "team_lead", "tier", "rotation", "schedule", "secondary", "shared_with", "channel",
        "pagerduty_service", "coverage", "ack_minutes", "runbook", "source"}


def test_flow_api():
    assert mine.get_oncall_for_service("flow-api") == {
        "service": "flow-api", "owner_team": "Core API", "team_lead": "Itai Barak", "tier": 1,
        "rotation": "core-api-oncall", "schedule": "weekly, handover Sunday 10:00", "secondary": None,
        "shared_with": None, "channel": None, "pagerduty_service": "flow-api-prod", "coverage": "24/7",
        "ack_minutes": 5, "runbook": "eng-runbook-flow-api", "source": "eng-service-catalog"}


def test_shared_rotation_copies_the_schedule_and_finds_the_hebrew_runbook():
    r = mine.get_oncall_for_service("flow-scheduler")
    assert r["rotation"] == "engine-oncall" and r["shared_with"] == "flow-engine"
    assert r["schedule"] == "weekly, handover Sunday 10:00" and r["runbook"] == "eng-oncall-scheduler-he"
    n = mine.get_oncall_for_service("notifications")
    assert (n["tier"], n["ack_minutes"], n["schedule"]) == (2, 15, "weekly, handover Monday 10:00")
    assert n["runbook"] is None


def test_secondary_and_business_hours():
    a = mine.get_oncall_for_service("auth-service")
    assert a["secondary"] == "platform-oncall" and a["schedule"] == "weekly, handover Thursday 10:00"
    lh = mine.get_oncall_for_service("lighthouse")
    assert lh == {**lh, "rotation": None, "schedule": None, "channel": "#data-help", "pagerduty_service": None,
                  "coverage": "business hours", "ack_minutes": None, "tier": 3}


@pytest.mark.parametrize("name", ["flow-api", "flow-engine", "flow-scheduler", "auth-service", "billing-service",
                                  "connectors-hub", "notifications", "web-app", "lighthouse"])
def test_every_service_has_exactly_the_keys(name):
    r = mine.get_oncall_for_service(name)
    assert set(r) == KEYS and r["service"] == name and isinstance(r["tier"], int)


def test_normalizes_the_name():
    assert mine.get_oncall_for_service("  Billing_Service ")["service"] == "billing-service"


def test_reads_the_catalog_it_is_given():
    fake = ("# Catalog\n\n## Production services\n\n| Service | Owner team | Team lead | Tier | On-call rotation | "
            "PagerDuty service |\n|---|---|---|---|---|---|\n| search-api | Search | Noa Peretz | 2 | search-oncall: "
            "weekly, handover Tuesday 09:00 | search-prod |\n\n## Platform components\n\n| x | y |\n|---|---|\n| a | b |\n")
    r = mine.get_oncall_for_service("search-api", catalog=fake)
    assert (r["owner_team"], r["rotation"], r["schedule"], r["ack_minutes"]) == \
        ("Search", "search-oncall", "weekly, handover Tuesday 09:00", 15)
    with pytest.raises(ToolError):
        mine.get_oncall_for_service("flow-api", catalog=fake)


def test_errors_are_written_for_the_model():
    with pytest.raises(ToolError, match="empty"):
        mine.get_oncall_for_service("  ")
    with pytest.raises(ToolError) as e:
        mine.get_oncall_for_service("flow-ap")
    assert "flow-ap" in str(e.value) and "flow-api" in str(e.value)
    with pytest.raises(ToolError) as e:
        mine.get_oncall_for_service("kafka")
    assert "kafka" in str(e.value) and "lighthouse" in str(e.value)  # nothing close: list the known services


def test_served_over_mcp(reg):
    srv = build_acme_server(reg, oncall_fn=mine.get_oncall_for_service, resources=False, prompts=False)

    async def go():
        async with Client(srv) as c:
            tools = {t.name: t for t in (await c.list_tools()).tools}
            ok = await c.call_tool("get_oncall_for_service", {"service": "billing-service"})
            bad = await c.call_tool("get_oncall_for_service", {"service": "kafka"})
            return tools, ok, bad

    tools, ok, bad = run(go())
    assert tools["get_oncall_for_service"].annotations.read_only_hint is True
    assert tools["get_oncall_for_service"].input_schema["required"] == ["service"]
    assert not ok.is_error and ok.structured_content["rotation"] == "billing-oncall"
    assert bad.is_error and "kafka" in bad.content[0].text  # errors are data (isError), not a JSON-RPC error

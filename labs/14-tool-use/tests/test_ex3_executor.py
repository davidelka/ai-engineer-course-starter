"""Exercise 3: execute_tool never raises; every failure is an is_error result the model can act on."""
import json
import time

from pydantic import BaseModel

import mine
from llmkit.types import ToolCall
from toolkit.registry import Registry, ToolError, ToolSpec


def call(name, args=None, **kw):
    return ToolCall(f"id_{name}", name, args if args is not None else {}, **kw)


def test_success_returns_json(reg):
    r = mine.execute_tool(call("lookup_employee", {"employee": "dana.levi@acme.example"}), reg)
    assert not r.is_error and r.call_id == "id_lookup_employee" and r.name == "lookup_employee"
    assert json.loads(r.text)["manager"]["id"] == "E005"


def test_unknown_tool_lists_available(reg):
    r = mine.execute_tool(call("find_employee", {"email": "x"}), reg)
    assert r.is_error and "Unknown tool" in r.text and "lookup_employee" in r.text


def test_bad_json_arguments(reg):
    r = mine.execute_tool(call("lookup_employee", {}, parse_error="arguments are not valid JSON: Expecting value"), reg)
    assert r.is_error and "Invalid arguments" in r.text and "not valid JSON" in r.text


def test_validation_errors_name_the_field(reg):
    r = mine.execute_tool(call("check_policy", {"system": "figma", "access_level": "superuser",
                                                "external_sharing": False, "holds_customer_or_financial_data": None}), reg)
    assert r.is_error and "Invalid arguments for check_policy" in r.text
    assert "access_level" in r.text and "superuser" in r.text


def test_tool_error_text_passes_through(reg):
    r = mine.execute_tool(call("get_system_info", {"system": "salesforc"}), reg)
    assert r.is_error and r.text == "Unknown system 'salesforc'. Close matches: salesforce."


def test_side_effect_not_run_without_confirmation(reg, tmp_path):
    args = {"employee": "E016", "system": "figma", "access_level": "editor", "justification": "review",
            "duration_days": None, "idempotency_key": "k"}
    r = mine.execute_tool(call("create_access_request", args), reg)
    assert r.is_error and r.text.startswith("NOT executed")
    assert not (tmp_path / "requests.db").exists()  # the function was never called
    r = mine.execute_tool(call("create_access_request", args), reg, confirmed=lambda c: False)
    assert r.is_error
    ok = mine.execute_tool(call("create_access_request", args), reg, confirmed=lambda c: True)
    assert not ok.is_error and json.loads(ok.text)["route"] == "needs_manager"


class Empty(BaseModel):
    pass


def tiny_registry():
    r = Registry()
    r.register(ToolSpec("slow", "Sleeps for a while.", Empty, lambda a: time.sleep(1.5)))
    r.register(ToolSpec("slow_fast_limit", "Sleeps, with its own limit.", Empty, lambda a: time.sleep(1.5), timeout_s=0.1))
    r.register(ToolSpec("boom", "Crashes.", Empty, lambda a: {}["secret-key-123"]))
    r.register(ToolSpec("polite", "Fails politely.", Empty, lambda a: (_ for _ in ()).throw(ToolError("try again later"))))
    return r


def test_timeout():
    t0 = time.perf_counter()
    r = mine.execute_tool(call("slow"), tiny_registry(), timeout_s=0.2)
    assert r.is_error and "timed out" in r.text and time.perf_counter() - t0 < 1.0


def test_spec_timeout_wins():
    r = mine.execute_tool(call("slow_fast_limit"), tiny_registry(), timeout_s=10)
    assert r.is_error and "timed out" in r.text


def test_crash_hides_details():
    r = mine.execute_tool(call("boom"), tiny_registry())
    assert r.is_error and "internal error" in r.text and "KeyError" in r.text
    assert "secret-key-123" not in r.text and "Traceback" not in r.text


def test_toolerror_from_function():
    r = mine.execute_tool(call("polite"), tiny_registry())
    assert r.is_error and r.text == "try again later"

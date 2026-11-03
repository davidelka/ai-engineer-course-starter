"""Exercise 3: which errors are worth retrying."""

import pytest

from llmkit.errors import LLMError
from mine import classify_error


@pytest.mark.parametrize("status,kind", [
    (429, "rate_limit_error"), (500, "api_error"), (502, ""), (503, "UNAVAILABLE"),
    (529, "overloaded_error"), (408, ""),
])
def test_transient_http_errors_are_retried(status, kind):
    assert classify_error(LLMError("x", status=status, kind=kind)).retry is True


@pytest.mark.parametrize("status,kind", [
    (400, "invalid_request_error"), (401, "authentication_error"), (403, "permission_error"),
    (404, "not_found_error"), (413, "request_too_large"), (422, ""),
])
def test_request_errors_are_not_retried(status, kind):
    assert classify_error(LLMError("x", status=status, kind=kind)).retry is False


@pytest.mark.parametrize("kind", ["timeout", "network", "stream_truncated", "overloaded_error", "malformed_response"])
def test_errors_without_status_that_are_transient(kind):
    assert classify_error(LLMError("x", status=None, kind=kind)).retry is True


def test_error_inside_stream_with_request_kind_is_not_retried():
    assert classify_error(LLMError("x", status=None, kind="invalid_request_error")).retry is False


def test_retry_after_is_passed_through():
    d = classify_error(LLMError("x", status=429, kind="rate_limit_error", retry_after=12))
    assert d.retry and d.retry_after == 12

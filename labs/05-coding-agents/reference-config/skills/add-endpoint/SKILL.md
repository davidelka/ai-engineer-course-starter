---
name: add-endpoint
description: Adds a new HTTP endpoint to the Acme access-request service with models, storage changes and tests for every status code. Use when asked to add or extend an API endpoint or route in this repo.
argument-hint: "[endpoint description]"
---

# Add an endpoint

The endpoint to build: $ARGUMENTS

Read `docs/policy.md` first if the endpoint touches routing or decisions.

## Steps

1. Write down the contract before coding: method and path, request body, response model,
   and every status code with its condition (404 unknown id, 409 wrong state, 403 not
   allowed, 422 invalid body). If the request leaves a status unclear, ask.
2. Models in `app/models.py`: a request-body model with `model_config = ConfigDict(extra="forbid")`
   and `Literal[...]` for fixed values. New fields on `AccessRequest` get a default
   (`None`) so existing requests stay valid.
3. Storage in `app/store.py`: add a method if the endpoint needs one. Replace stored items
   with `item.model_copy(update={...})` and `store.save(...)`; never mutate `_items` from an endpoint.
4. Endpoint in `app/main.py`: one function, declare `response_model`, check the error
   conditions in the order the contract lists them, raise `HTTPException` with a specific `detail`.
5. Tests in `tests/test_api.py` (or a new `tests/test_<feature>.py`): use the `client`
   fixture and `make_request()` from `tests/conftest.py`. One test for the success path,
   one per error status, and one that reads the item back with GET.
6. Run `python -m pytest -q tests/test_api.py` while iterating, then `make test` and `make lint`.
   Fix formatting with `make fmt`. Both `make test` and `make lint` must pass before you report.
7. Report: the contract (one line per status code), the files changed, and the test count.

## Example contract

```
POST /requests/{id}/decision  body DecisionIn  -> 200 AccessRequest
404 unknown id | 409 not pending | 403 needs_security | 403 self-approval | 422 invalid body
```

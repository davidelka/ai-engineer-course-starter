# impl/

Empty on purpose. In exercise 6 Claude Code writes the implementation of SPEC-006 here,
from `spec/access-requests.spec.md` and `spec/openapi.yaml` alone (see `IMPLEMENT_PROMPT.md`).

Expected layout after the exercise:

- `app.py` with `create_app() -> FastAPI`
- `routing.py`, `store.py`
- `tests/` with tests marked `@pytest.mark.req("REQ-n")`
- `DECISIONS.md` with the choices the agent made where the spec was ambiguous

Grade it with `python labs/06-spec-driven/grade.py --app impl`.

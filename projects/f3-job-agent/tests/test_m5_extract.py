"""M5: one post -> its jobs, with a structured-output call (mine.extract_post).

The tests use GoldOracleLLM (jobagent/extract.py): a fake model that finds the labeled post in the
prompt and answers with its gold extraction, priced like Haiku 5.5. Offline and free.
"""

from jobagent.evaluate import load_posts, raw_post
from jobagent.extract import SYSTEM_PROMPT, GoldOracleLLM
from jobagent.models import PostExtraction
from mine import extract_post

POSTS = load_posts()
JOB_POST = next(p for p in POSTS if p["gold"]["is_job_post"] and len(p["gold"]["jobs"]) >= 2)


class Spy(GoldOracleLLM):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.requests = []

    def complete(self, req, **kw):
        self.requests.append(req)
        return super().complete(req, **kw)


class Broken(GoldOracleLLM):
    """Always answers invalid JSON."""

    def complete(self, req, **kw):
        r = super().complete(req, **kw)
        r.text = "{not json"
        return r


def test_returns_the_jobs_of_the_post():
    llm = GoldOracleLLM(POSTS)
    r = extract_post(llm, raw_post(JOB_POST), name="test")
    assert isinstance(r.extraction, PostExtraction)
    assert r.extraction.is_job_post is True
    assert [j.title for j in r.extraction.jobs] == [j["title"] for j in JOB_POST["gold"]["jobs"]]
    assert r.error is None and r.extractor == "test"
    assert r.attempts == 1 and r.input_tokens > 0 and r.output_tokens > 0 and r.cost_usd > 0
    assert r.latency_s >= 0


def test_cached_system_block_in_native_mode():
    llm = Spy(POSTS)
    extract_post(llm, raw_post(JOB_POST))
    req = llm.requests[0]
    assert not isinstance(req.system, str)
    assert req.system[0].text == SYSTEM_PROMPT and req.system[0].cache == "5m"
    assert "<<post nonce=" in req.messages[-1].text


def test_no_cache_block_when_disabled():
    llm = Spy(POSTS)
    extract_post(llm, raw_post(JOB_POST), cache_system=False)
    sys_ = llm.requests[0].system
    assert isinstance(sys_, str) or all(getattr(b, "cache", None) is None for b in sys_)


def test_repairs_an_invalid_first_reply():
    llm = GoldOracleLLM(POSTS, first_reply_invalid=True)
    r = extract_post(llm, raw_post(JOB_POST))
    assert r.error is None and r.attempts == 2 and r.extraction.jobs


def test_fails_closed():
    r = extract_post(Broken(POSTS), raw_post(JOB_POST), max_repairs=1, name="x")
    assert r.extraction.is_job_post is False and r.extraction.jobs == []
    assert r.error and r.error.startswith("structured_")
    assert r.extractor == "x" and r.attempts >= 1

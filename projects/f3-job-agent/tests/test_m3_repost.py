"""M3: a reposted message is caught before the model is called (mine.find_repost)."""

from mine import find_repost

POST = """🔥 Backend Engineer – Cobalt Pay
Tel Aviv, hybrid. Go, gRPC, Postgres. 4+ years.
Apply: cv@cobaltpay.example"""


def test_exact_copy_is_found():
    assert find_repost(POST, [("a", "Data Analyst at Quill, Haifa"), ("b", POST)]) == "b"


def test_small_edit_is_still_a_repost():
    edited = POST.replace("🔥 ", "").replace("4+ years", "4+ years!")
    assert find_repost(edited, [("x", POST)]) == "x"


def test_different_message_is_not_a_repost():
    other = "Junior QA Engineer – Lumen Labs\nHaifa, onsite. Manual testing, no experience needed.\nqa@lumen.example"
    assert find_repost(other, [("x", POST)]) is None


def test_returns_the_most_similar_key():
    close = POST.replace("Postgres", "Postgres, Redis")
    far = POST.replace("Go, gRPC, Postgres", "Java, Spring, Kafka, Oracle, Kubernetes").replace("Tel Aviv", "Haifa")
    assert find_repost(POST, [("far", far), ("close", close)], threshold=0.5) == "close"


def test_threshold_is_inclusive_and_respected():
    edited = POST.replace("Postgres", "MySQL")
    assert find_repost(edited, [("x", POST)], threshold=0.99) is None
    assert find_repost(POST, [("x", POST)], threshold=1.0) == "x"


def test_nothing_to_compare():
    assert find_repost(POST, []) is None
    assert find_repost(POST, iter([])) is None

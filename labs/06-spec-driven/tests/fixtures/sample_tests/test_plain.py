import pytest
from pytest import mark


@pytest.mark.req("REQ-1")
def test_one():
    pass


@pytest.mark.req("REQ-1", "REQ-2")
@pytest.mark.parametrize("x", [1, 2])
def test_two(x):
    pass


@mark.req("REQ-3")
def test_from_import():
    pass


@pytest.mark.slow
def test_no_req():
    pass


@pytest.mark.req("REQ-9")
def helper_not_a_test():
    pass


@pytest.mark.req("REQ-4")
class TestGroup:
    def test_a(self):
        pass

    @pytest.mark.req("REQ-5")
    def test_b(self):
        pass

    def not_a_test(self):
        pass


@pytest.mark.req("REQ-8")
class NotATestClass:
    def test_x(self):
        pass

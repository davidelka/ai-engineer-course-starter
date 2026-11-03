import pytest

pytestmark = [pytest.mark.req("REQ-6"), pytest.mark.slow]


def test_c():
    pass


@pytest.mark.req("REQ-99")
def test_d():
    pass

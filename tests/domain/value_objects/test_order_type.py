from src.domain.value_objects import OrderType


def test_market():

    assert OrderType.MARKET.value == "MARKET"


def test_limit():

    assert OrderType.LIMIT.value == "LIMIT"
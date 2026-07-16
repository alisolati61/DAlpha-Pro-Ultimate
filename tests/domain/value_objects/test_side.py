from src.domain.value_objects import Side


def test_buy():

    assert Side.BUY.value == "BUY"


def test_sell():

    assert Side.SELL.value == "SELL"
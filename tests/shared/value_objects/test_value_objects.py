from decimal import Decimal

from src.shared.value_objects import (
    Price,
    Quantity,
    Money,
    Percentage,
    Symbol,
)


def test_price():

    p = Price.from_float(10.5)

    assert p.value == Decimal("10.5")


def test_quantity():

    q = Quantity.from_float(2)

    assert q.value == Decimal("2")


def test_money():

    m = Money(Decimal("100"))

    assert m.currency == "USDT"


def test_percentage():

    p = Percentage(Decimal("0.25"))

    assert p.value == Decimal("0.25")


def test_symbol():

    s = Symbol("BTCUSDT")

    assert s.value == "BTCUSDT"
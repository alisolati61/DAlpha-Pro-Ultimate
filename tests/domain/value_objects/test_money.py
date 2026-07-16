from decimal import Decimal

import pytest

from src.domain.value_objects import Money


def test_create():

    m = Money(
        Decimal("10"),
        "usd",
    )

    assert m.currency == "USD"


def test_add():

    a = Money(
        Decimal("10"),
        "USD",
    )

    b = Money(
        Decimal("5"),
        "USD",
    )

    c = a + b

    assert c.amount == Decimal("15")


def test_sub():

    a = Money(
        Decimal("10"),
        "USD",
    )

    b = Money(
        Decimal("3"),
        "USD",
    )

    c = a - b

    assert c.amount == Decimal("7")


def test_currency_mismatch():

    a = Money(
        Decimal("10"),
        "USD",
    )

    b = Money(
        Decimal("5"),
        "EUR",
    )

    with pytest.raises(ValueError):
        _ = a + b
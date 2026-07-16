from decimal import Decimal

import pytest

from src.domain.value_objects import Price


def test_create():

    price = Price(
        Decimal("105000"),
        "usdt",
    )

    assert price.value == Decimal("105000")

    assert price.quote_currency == "USDT"


def test_zero():

    with pytest.raises(ValueError):

        Price(
            Decimal("0"),
            "USD",
        )


def test_negative():

    with pytest.raises(ValueError):

        Price(
            Decimal("-1"),
            "USD",
        )


def test_empty_currency():

    with pytest.raises(ValueError):

        Price(
            Decimal("100"),
            "",
        )
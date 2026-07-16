from decimal import Decimal

import pytest

from src.domain.value_objects import Quantity


def test_create():

    q = Quantity(Decimal("2.5"))

    assert q.value == Decimal("2.5")


def test_add():

    a = Quantity(Decimal("1"))

    b = Quantity(Decimal("2"))

    c = a + b

    assert c.value == Decimal("3")


def test_sub():

    a = Quantity(Decimal("5"))

    b = Quantity(Decimal("2"))

    c = a - b

    assert c.value == Decimal("3")


def test_zero():

    with pytest.raises(ValueError):

        Quantity(Decimal("0"))


def test_negative():

    with pytest.raises(ValueError):

        Quantity(Decimal("-1"))
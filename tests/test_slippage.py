"""Tests for validated execution-slippage calculations."""

from dataclasses import FrozenInstanceError
from fractions import Fraction
from math import inf, nan

import pytest

from src.execution.slippage import (
    OrderSide,
    SlippageCalculator,
    SlippageResult,
)


def calculate(
    **overrides: object,
) -> SlippageResult:
    values: dict[str, object] = {
        "expected_price": 100,
        "executed_price": 101,
        "side": "buy",
    }
    values.update(overrides)

    return SlippageCalculator.calculate(
        **values,  # type: ignore[arg-type]
    )


def test_order_side_values() -> None:
    assert OrderSide.BUY.value == "buy"
    assert OrderSide.SELL.value == "sell"


def test_buy_adverse_slippage() -> None:
    result = calculate()

    assert isinstance(
        result,
        SlippageResult,
    )
    assert result.expected_price == 100.0
    assert result.executed_price == 101.0
    assert result.absolute_slippage == 1.0
    assert result.slippage_percent == 1.0
    assert result.adverse is True
    assert result.favorable is False
    assert result.neutral is False


def test_buy_favorable_slippage() -> None:
    result = calculate(
        executed_price=99,
    )

    assert result.absolute_slippage == 1.0
    assert result.slippage_percent == 1.0
    assert result.adverse is False
    assert result.favorable is True
    assert result.neutral is False


def test_sell_adverse_slippage() -> None:
    result = calculate(
        executed_price=99,
        side=OrderSide.SELL,
    )

    assert result.absolute_slippage == 1.0
    assert result.slippage_percent == 1.0
    assert result.adverse is True
    assert result.favorable is False


def test_sell_favorable_slippage() -> None:
    result = calculate(
        executed_price=101,
        side="sell",
    )

    assert result.adverse is False
    assert result.favorable is True


def test_zero_slippage() -> None:
    result = calculate(
        executed_price=100,
    )

    assert result.absolute_slippage == 0.0
    assert result.slippage_percent == 0.0
    assert result.adverse is False
    assert result.favorable is False
    assert result.neutral is True


@pytest.mark.parametrize(
    "side",
    [
        "buy",
        "BUY",
        "Buy",
        " bUy ",
        OrderSide.BUY,
    ],
)
def test_buy_side_normalization(
    side: OrderSide | str,
) -> None:
    assert calculate(
        side=side,
    ).adverse is True


@pytest.mark.parametrize(
    "side",
    [
        "sell",
        "SELL",
        "Sell",
        " sElL ",
        OrderSide.SELL,
    ],
)
def test_sell_side_normalization(
    side: OrderSide | str,
) -> None:
    result = calculate(
        executed_price=99,
        side=side,
    )

    assert result.adverse is True


def test_price_difference_positive() -> None:
    result = calculate()

    assert result.price_difference == 1.0


def test_price_difference_negative() -> None:
    result = calculate(
        executed_price=99,
    )

    assert result.price_difference == -1.0


def test_adverse_slippage_percent() -> None:
    adverse = calculate()
    favorable = calculate(
        executed_price=99,
    )

    assert adverse.adverse_slippage_percent == 1.0
    assert favorable.adverse_slippage_percent == 0.0


def test_favorable_slippage_percent() -> None:
    favorable = calculate(
        executed_price=99,
    )
    adverse = calculate()

    assert (
        favorable.favorable_slippage_percent
        == 1.0
    )
    assert (
        adverse.favorable_slippage_percent
        == 0.0
    )


def test_fractional_slippage() -> None:
    result = calculate(
        expected_price=200,
        executed_price=200.5,
    )

    assert result.absolute_slippage == 0.5
    assert result.slippage_percent == 0.25


def test_fraction_real_values_are_supported() -> None:
    result = calculate(
        expected_price=Fraction(
            100,
            1,
        ),
        executed_price=Fraction(
            101,
            1,
        ),
    )

    assert result.expected_price == 100.0
    assert result.executed_price == 101.0


def test_result_values_have_exact_types() -> None:
    result = calculate()

    assert type(result.expected_price) is float
    assert type(result.executed_price) is float
    assert type(result.absolute_slippage) is float
    assert type(result.slippage_percent) is float
    assert type(result.adverse) is bool


def test_result_is_immutable() -> None:
    result = calculate()

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.adverse = False  # type: ignore[misc]


def test_direct_result_construction_remains_available() -> None:
    result = SlippageResult(
        expected_price=100.0,
        executed_price=101.0,
        absolute_slippage=1.0,
        slippage_percent=1.0,
        adverse=True,
    )

    assert result.adverse is True


def test_exceeds_limit_when_adverse() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=102,
        side="buy",
        max_slippage_percent=1,
    ) is True


def test_equal_limit_is_not_exceeded() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=101,
        side="buy",
        max_slippage_percent=1,
    ) is False


def test_below_limit_is_not_exceeded() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=100.5,
        side="buy",
        max_slippage_percent=1,
    ) is False


def test_favorable_slippage_never_exceeds_limit() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=50,
        side="buy",
        max_slippage_percent=0,
    ) is False


def test_zero_slippage_does_not_exceed_zero_limit() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=100,
        side="buy",
        max_slippage_percent=0,
    ) is False


def test_non_zero_adverse_exceeds_zero_limit() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=100.01,
        side="buy",
        max_slippage_percent=0,
    ) is True


def test_sell_adverse_limit() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=98,
        side="sell",
        max_slippage_percent=1,
    ) is True


def test_sell_favorable_limit() -> None:
    assert SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=102,
        side="sell",
        max_slippage_percent=0,
    ) is False


def test_within_limit_is_inverse_of_exceeds() -> None:
    arguments = {
        "expected_price": 100,
        "executed_price": 101,
        "side": "buy",
        "max_slippage_percent": 1,
    }

    assert SlippageCalculator.within_limit(
        **arguments,
    ) is True
    assert SlippageCalculator.exceeds_limit(
        **arguments,
    ) is False


def test_within_limit_returns_exact_bool() -> None:
    result = SlippageCalculator.within_limit(
        expected_price=100,
        executed_price=102,
        side="buy",
        max_slippage_percent=1,
    )

    assert type(result) is bool
    assert result is False


@pytest.mark.parametrize(
    "expected_price",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_non_positive_expected_price(
    expected_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "expected_price must be "
            "greater than zero"
        ),
    ):
        calculate(
            expected_price=expected_price,
        )


@pytest.mark.parametrize(
    "executed_price",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_non_positive_executed_price(
    executed_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "executed_price must be "
            "greater than zero"
        ),
    ):
        calculate(
            executed_price=executed_price,
        )


@pytest.mark.parametrize(
    "expected_price",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_expected_price(
    expected_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="expected_price must be finite",
    ):
        calculate(
            expected_price=expected_price,
        )


@pytest.mark.parametrize(
    "executed_price",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_executed_price(
    executed_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="executed_price must be finite",
    ):
        calculate(
            executed_price=executed_price,
        )


@pytest.mark.parametrize(
    "expected_price",
    [
        True,
        False,
        "100",
        None,
        [],
        {},
        object(),
    ],
)
def test_invalid_expected_price_type(
    expected_price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="expected_price must be a number",
    ):
        calculate(
            expected_price=expected_price,
        )


@pytest.mark.parametrize(
    "executed_price",
    [
        True,
        False,
        "101",
        None,
        [],
        {},
        object(),
    ],
)
def test_invalid_executed_price_type(
    executed_price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="executed_price must be a number",
    ):
        calculate(
            executed_price=executed_price,
        )


@pytest.mark.parametrize(
    "side",
    [
        "",
        " ",
        "\t",
        "\n",
        "hold",
        "unknown",
        "long",
        "short",
    ],
)
def test_invalid_side_value(
    side: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):
        calculate(
            side=side,
        )


@pytest.mark.parametrize(
    "side",
    [
        None,
        1,
        True,
        [],
        {},
        object(),
    ],
)
def test_invalid_side_type(
    side: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "side must be an OrderSide "
            "or string"
        ),
    ):
        calculate(
            side=side,
        )


@pytest.mark.parametrize(
    "max_slippage_percent",
    [
        -1,
        -0.1,
    ],
)
def test_negative_slippage_limit(
    max_slippage_percent: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_slippage_percent "
            "cannot be negative"
        ),
    ):
        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=101,
            side="buy",
            max_slippage_percent=(
                max_slippage_percent
            ),
        )


@pytest.mark.parametrize(
    "max_slippage_percent",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_slippage_limit(
    max_slippage_percent: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_slippage_percent "
            "must be finite"
        ),
    ):
        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=101,
            side="buy",
            max_slippage_percent=(
                max_slippage_percent
            ),
        )


@pytest.mark.parametrize(
    "max_slippage_percent",
    [
        True,
        False,
        "1",
        None,
        [],
        {},
        object(),
    ],
)
def test_invalid_slippage_limit_type(
    max_slippage_percent: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "max_slippage_percent "
            "must be a number"
        ),
    ):
        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=101,
            side="buy",
            max_slippage_percent=(
                max_slippage_percent
            ),  # type: ignore[arg-type]
        )


def test_fraction_slippage_limit_is_supported() -> None:
    result = SlippageCalculator.exceeds_limit(
        expected_price=100,
        executed_price=102,
        side="buy",
        max_slippage_percent=Fraction(
            3,
            2,
        ),
    )

    assert result is True


def test_extreme_slippage_overflow_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "slippage calculation "
            "must be finite"
        ),
    ):
        calculate(
            expected_price=1e-308,
            executed_price=1e308,
        )


def test_validation_order_checks_expected_first() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "expected_price must be "
            "greater than zero"
        ),
    ):
        SlippageCalculator.calculate(
            expected_price=0,
            executed_price=0,
            side="invalid",
        )


def test_validation_order_checks_executed_second() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "executed_price must be "
            "greater than zero"
        ),
    ):
        SlippageCalculator.calculate(
            expected_price=100,
            executed_price=0,
            side="invalid",
        )


def test_validation_order_checks_side_last() -> None:
    with pytest.raises(
        ValueError,
        match="side must be 'buy' or 'sell'",
    ):
        SlippageCalculator.calculate(
            expected_price=100,
            executed_price=101,
            side="invalid",
        )
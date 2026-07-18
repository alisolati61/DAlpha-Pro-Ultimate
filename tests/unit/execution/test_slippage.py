import pytest

from src.execution.slippage import (
    OrderSide,
    SlippageCalculator,
    SlippageResult,
)


def test_buy_adverse_slippage():

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=101,
        side=OrderSide.BUY,
    )

    assert isinstance(
        result,
        SlippageResult,
    )

    assert result.absolute_slippage == 1.0

    assert result.slippage_percent == 1.0

    assert result.adverse is True


def test_buy_favorable_slippage():

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=99,
        side=OrderSide.BUY,
    )

    assert result.adverse is False


def test_sell_adverse_slippage():

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=99,
        side=OrderSide.SELL,
    )

    assert result.absolute_slippage == 1.0

    assert result.slippage_percent == 1.0

    assert result.adverse is True


def test_sell_favorable_slippage():

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=101,
        side=OrderSide.SELL,
    )

    assert result.adverse is False


@pytest.mark.parametrize(
    "side",
    [
        "buy",
        "BUY",
        " Buy ",
        OrderSide.BUY,
    ],
)
def test_buy_side_normalization(side):

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=101,
        side=side,
    )

    assert result.adverse is True


@pytest.mark.parametrize(
    "side",
    [
        "sell",
        "SELL",
        " Sell ",
        OrderSide.SELL,
    ],
)
def test_sell_side_normalization(side):

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=99,
        side=side,
    )

    assert result.adverse is True


def test_zero_slippage():

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=100,
        side="buy",
    )

    assert result.absolute_slippage == 0.0

    assert result.slippage_percent == 0.0

    assert result.adverse is False


def test_slippage_result_is_immutable():

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=101,
        side="buy",
    )

    with pytest.raises(
        AttributeError,
    ):

        result.adverse = False


def test_exceeds_limit_when_adverse():

    assert (
        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=102,
            side="buy",
            max_slippage_percent=1,
        )
        is True
    )


def test_does_not_exceed_limit_within_limit():

    assert (
        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=101,
            side="buy",
            max_slippage_percent=1,
        )
        is False
    )


def test_favorable_slippage_does_not_exceed_limit():

    assert (
        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=98,
            side="buy",
            max_slippage_percent=0.1,
        )
        is False
    )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
    ],
)
def test_invalid_expected_price(price):

    with pytest.raises(
        ValueError,
    ):

        SlippageCalculator.calculate(
            expected_price=price,
            executed_price=100,
            side="buy",
        )


@pytest.mark.parametrize(
    "price",
    [
        0,
        -1,
    ],
)
def test_invalid_executed_price(price):

    with pytest.raises(
        ValueError,
    ):

        SlippageCalculator.calculate(
            expected_price=100,
            executed_price=price,
            side="buy",
        )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_expected_price_values(value):

    with pytest.raises(
        ValueError,
    ):

        SlippageCalculator.calculate(
            expected_price=value,
            executed_price=100,
            side="buy",
        )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_executed_price_values(value):

    with pytest.raises(
        ValueError,
    ):

        SlippageCalculator.calculate(
            expected_price=100,
            executed_price=value,
            side="buy",
        )


@pytest.mark.parametrize(
    "side",
    [
        "hold",
        "",
        "unknown",
    ],
)
def test_invalid_side(side):

    with pytest.raises(
        ValueError,
    ):

        SlippageCalculator.calculate(
            expected_price=100,
            executed_price=101,
            side=side,
        )


def test_invalid_side_type():

    with pytest.raises(
        TypeError,
    ):

        SlippageCalculator.calculate(
            expected_price=100,
            executed_price=101,
            side=None,
        )


@pytest.mark.parametrize(
    "limit",
    [
        -1,
        -0.1,
    ],
)
def test_negative_slippage_limit(limit):

    with pytest.raises(
        ValueError,
    ):

        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=101,
            side="buy",
            max_slippage_percent=limit,
        )


def test_slippage_limit_must_be_finite():

    with pytest.raises(
        ValueError,
    ):

        SlippageCalculator.exceeds_limit(
            expected_price=100,
            executed_price=101,
            side="buy",
            max_slippage_percent=float(
                "inf"
            ),
        )


def test_result_values_are_floats():

    result = SlippageCalculator.calculate(
        expected_price=100,
        executed_price=101,
        side="buy",
    )

    assert isinstance(
        result.expected_price,
        float,
    )

    assert isinstance(
        result.executed_price,
        float,
    )

    assert isinstance(
        result.absolute_slippage,
        float,
    )

    assert isinstance(
        result.slippage_percent,
        float,
    )

    assert isinstance(
        result.adverse,
        bool,
    )
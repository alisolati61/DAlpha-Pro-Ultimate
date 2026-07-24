"""Tests for validated risk-based position sizing."""

from dataclasses import FrozenInstanceError
from fractions import Fraction
from math import inf, nan

import pytest

from src.risk.position_sizer import (
    PositionSizeResult,
    PositionSizer,
)


def calculate(
    **overrides: object,
) -> PositionSizeResult:
    values: dict[str, object] = {
        "balance": 10_000,
        "risk_percent": 1,
        "entry_price": 100,
        "stop_loss": 95,
    }
    values.update(overrides)

    return PositionSizer.calculate_position_size(
        **values,  # type: ignore[arg-type]
    )


def test_calculates_one_percent_risk() -> None:
    result = calculate()

    assert isinstance(
        result,
        PositionSizeResult,
    )
    assert result.risk_amount == 100.0
    assert result.stop_distance == 5.0
    assert result.position_size == 20.0


def test_calculates_fractional_position_size() -> None:
    result = calculate(
        risk_percent=2,
        stop_loss=97.5,
    )

    assert result.risk_amount == 200.0
    assert result.stop_distance == 2.5
    assert result.position_size == 80.0


def test_supports_stop_above_entry() -> None:
    result = calculate(
        stop_loss=105,
    )

    assert result.stop_distance == 5.0
    assert result.position_size == 20.0


def test_supports_fractional_risk_percent() -> None:
    result = calculate(
        risk_percent=0.5,
    )

    assert result.risk_amount == 50.0
    assert result.position_size == 10.0


def test_supports_full_balance_risk() -> None:
    result = calculate(
        risk_percent=100,
    )

    assert result.risk_amount == 10_000.0
    assert result.position_size == 2_000.0


def test_supports_fraction_real_values() -> None:
    result = PositionSizer.calculate_position_size(
        balance=Fraction(10_000, 1),
        risk_percent=Fraction(1, 1),
        entry_price=Fraction(100, 1),
        stop_loss=Fraction(95, 1),
    )

    assert result == PositionSizeResult(
        position_size=20.0,
        risk_amount=100.0,
        stop_distance=5.0,
    )


def test_result_values_are_exact_floats() -> None:
    result = calculate()

    assert type(result.position_size) is float
    assert type(result.risk_amount) is float
    assert type(result.stop_distance) is float


def test_notional_alias() -> None:
    result = calculate()

    assert (
        result.notional_per_price_unit
        == result.position_size
    )


def test_repeating_position_size_is_rounded() -> None:
    result = calculate(
        balance=1_000,
        entry_price=10,
        stop_loss=7,
    )

    assert result.position_size == 3.33333333


@pytest.mark.parametrize(
    "balance",
    [
        0,
        -1,
    ],
)
def test_invalid_balance_value(
    balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Balance must be greater than zero",
    ):
        calculate(
            balance=balance,
        )


@pytest.mark.parametrize(
    "balance",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_balance(
    balance: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Balance must be finite",
    ):
        calculate(
            balance=balance,
        )


@pytest.mark.parametrize(
    "balance",
    [
        True,
        False,
        "10000",
        None,
        object(),
    ],
)
def test_non_numeric_balance(
    balance: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="Balance must be a number",
    ):
        calculate(
            balance=balance,
        )


@pytest.mark.parametrize(
    "risk_percent",
    [
        0,
        -1,
    ],
)
def test_invalid_risk_percent_value(
    risk_percent: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Risk percent must be "
            "greater than zero"
        ),
    ):
        calculate(
            risk_percent=risk_percent,
        )


@pytest.mark.parametrize(
    "risk_percent",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_risk_percent(
    risk_percent: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Risk percent must be finite",
    ):
        calculate(
            risk_percent=risk_percent,
        )


@pytest.mark.parametrize(
    "risk_percent",
    [
        True,
        False,
        "1",
        None,
        object(),
    ],
)
def test_non_numeric_risk_percent(
    risk_percent: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="Risk percent must be a number",
    ):
        calculate(
            risk_percent=risk_percent,
        )


@pytest.mark.parametrize(
    "risk_percent",
    [
        100.00000001,
        101,
        1_000,
    ],
)
def test_risk_percent_cannot_exceed_one_hundred(
    risk_percent: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Risk percent cannot "
            "exceed 100"
        ),
    ):
        calculate(
            risk_percent=risk_percent,
        )


@pytest.mark.parametrize(
    "entry_price",
    [
        0,
        -1,
    ],
)
def test_invalid_entry_price_value(
    entry_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Entry price must be "
            "greater than zero"
        ),
    ):
        calculate(
            entry_price=entry_price,
        )


@pytest.mark.parametrize(
    "entry_price",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_entry_price(
    entry_price: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Entry price must be finite",
    ):
        calculate(
            entry_price=entry_price,
        )


@pytest.mark.parametrize(
    "entry_price",
    [
        True,
        False,
        "100",
        None,
        object(),
    ],
)
def test_non_numeric_entry_price(
    entry_price: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="Entry price must be a number",
    ):
        calculate(
            entry_price=entry_price,
        )


@pytest.mark.parametrize(
    "stop_loss",
    [
        0,
        -1,
    ],
)
def test_invalid_stop_loss_value(
    stop_loss: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Stop-loss price must be "
            "greater than zero"
        ),
    ):
        calculate(
            stop_loss=stop_loss,
        )


@pytest.mark.parametrize(
    "stop_loss",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_non_finite_stop_loss(
    stop_loss: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="Stop-loss price must be finite",
    ):
        calculate(
            stop_loss=stop_loss,
        )


@pytest.mark.parametrize(
    "stop_loss",
    [
        True,
        False,
        "95",
        None,
        object(),
    ],
)
def test_non_numeric_stop_loss(
    stop_loss: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="Stop-loss price must be a number",
    ):
        calculate(
            stop_loss=stop_loss,
        )


def test_zero_stop_distance() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Stop distance must be "
            "greater than zero"
        ),
    ):
        calculate(
            stop_loss=100,
        )


def test_large_finite_risk_amount_does_not_overflow() -> None:
    result = calculate(
        balance=1.79e308,
        risk_percent=100,
        entry_price=1.79e308,
        stop_loss=1.0,
    )

    assert result.risk_amount == 1.79e308
    assert result.position_size == 1.0


def test_overflowed_position_size_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Position size calculation "
            "must be finite"
        ),
    ):
        calculate(
            balance=1e308,
            risk_percent=1,
            entry_price=2e-308,
            stop_loss=1e-308,
        )


def test_risk_amount_below_precision_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Risk amount is below "
            "supported precision"
        ),
    ):
        calculate(
            balance=1e-10,
            risk_percent=1,
            entry_price=2,
            stop_loss=1,
        )


def test_position_size_below_precision_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "Position size is below "
            "supported precision"
        ),
    ):
        calculate(
            balance=1,
            risk_percent=1,
            entry_price=1e8,
            stop_loss=1,
        )


def test_result_is_immutable() -> None:
    result = calculate()

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.position_size = 1.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "field",
    [
        "position_size",
        "risk_amount",
        "stop_distance",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_result_rejects_non_positive_values(
    field: str,
    value: float,
) -> None:
    arguments: dict[str, object] = {
        "position_size": 20.0,
        "risk_amount": 100.0,
        "stop_distance": 5.0,
    }
    arguments[field] = value

    with pytest.raises(
        ValueError,
        match="must be greater than zero",
    ):
        PositionSizeResult(
            **arguments,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "position_size",
        "risk_amount",
        "stop_distance",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_result_rejects_non_finite_values(
    field: str,
    value: float,
) -> None:
    arguments = {
        "position_size": 20.0,
        "risk_amount": 100.0,
        "stop_distance": 5.0,
    }
    arguments[field] = value

    with pytest.raises(
        ValueError,
        match="must be finite",
    ):
        PositionSizeResult(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "position_size",
        "risk_amount",
        "stop_distance",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "1",
        None,
        object(),
    ],
)
def test_result_rejects_non_numeric_values(
    field: str,
    value: object,
) -> None:
    arguments: dict[str, object] = {
        "position_size": 20.0,
        "risk_amount": 100.0,
        "stop_distance": 5.0,
    }
    arguments[field] = value

    with pytest.raises(
        TypeError,
        match="must be a number",
    ):
        PositionSizeResult(
            **arguments,  # type: ignore[arg-type]
        )


def test_result_rejects_inconsistent_values() -> None:
    with pytest.raises(
        ValueError,
        match="are inconsistent",
    ):
        PositionSizeResult(
            position_size=20.0,
            risk_amount=101.0,
            stop_distance=5.0,
        )


def test_result_normalizes_integer_values() -> None:
    result = PositionSizeResult(
        position_size=20,
        risk_amount=100,
        stop_distance=5,
    )

    assert result.position_size == 20.0
    assert result.risk_amount == 100.0
    assert result.stop_distance == 5.0
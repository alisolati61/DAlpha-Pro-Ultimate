"""Tests for the core backtest result evaluator."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestResult,
)


def test_evaluates_mixed_trade_results() -> None:
    result = BacktestEngine().evaluate(
        [
            120,
            -50,
            90,
            40,
            -30,
            150,
            -70,
        ]
    )

    assert result.total_trades == 7
    assert result.wins == 4
    assert result.losses == 3
    assert result.breakevens == 0

    assert result.win_rate == 57.14
    assert result.loss_rate == 42.86
    assert result.breakeven_rate == 0.0

    assert result.gross_profit == 400.0
    assert result.gross_loss == 150.0
    assert result.net_profit == 250.0

    assert result.profitable is True
    assert result.unprofitable is False
    assert result.flat is False


def test_empty_trades_return_zero_result() -> None:
    result = BacktestEngine().evaluate([])

    assert result == BacktestResult(
        total_trades=0,
        wins=0,
        losses=0,
        breakevens=0,
        win_rate=0.0,
        loss_rate=0.0,
        breakeven_rate=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        net_profit=0.0,
    )

    assert result.flat is True


def test_zero_pnl_is_classified_as_breakeven() -> None:
    result = BacktestEngine().evaluate(
        [
            10.0,
            0.0,
            -5.0,
            0,
        ]
    )

    assert result.wins == 1
    assert result.losses == 1
    assert result.breakevens == 2

    assert result.win_rate == 25.0
    assert result.loss_rate == 25.0
    assert result.breakeven_rate == 50.0


def test_all_wins() -> None:
    result = BacktestEngine().evaluate(
        [
            1.0,
            2.0,
            3.0,
        ]
    )

    assert result.wins == 3
    assert result.losses == 0
    assert result.breakevens == 0

    assert result.win_rate == 100.0
    assert result.loss_rate == 0.0

    assert result.gross_profit == 6.0
    assert result.gross_loss == 0.0
    assert result.net_profit == 6.0

    assert result.profitable is True


def test_all_losses() -> None:
    result = BacktestEngine().evaluate(
        [
            -1.0,
            -2.0,
            -3.0,
        ]
    )

    assert result.wins == 0
    assert result.losses == 3
    assert result.breakevens == 0

    assert result.win_rate == 0.0
    assert result.loss_rate == 100.0

    assert result.gross_profit == 0.0
    assert result.gross_loss == 6.0
    assert result.net_profit == -6.0

    assert result.unprofitable is True


def test_flat_result_from_equal_profit_and_loss() -> None:
    result = BacktestEngine().evaluate(
        [
            10.0,
            -10.0,
        ]
    )

    assert result.net_profit == 0.0
    assert result.profitable is False
    assert result.unprofitable is False
    assert result.flat is True


def test_accepts_generator_without_double_consumption() -> None:
    result = BacktestEngine().evaluate(
        value
        for value in [
            5,
            -2,
            0,
        ]
    )

    assert result.total_trades == 3
    assert result.wins == 1
    assert result.losses == 1
    assert result.breakevens == 1
    assert result.net_profit == 3.0


def test_accepts_tuple() -> None:
    result = BacktestEngine().evaluate(
        (
            2,
            -1,
        )
    )

    assert result.total_trades == 2
    assert result.net_profit == 1.0


def test_integer_values_are_normalized_to_float() -> None:
    result = BacktestEngine().evaluate(
        [
            10,
            -4,
        ]
    )

    assert result.gross_profit == 10.0
    assert result.gross_loss == 4.0
    assert isinstance(
        result.gross_profit,
        float,
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        10.0,
        object(),
        "1,2",
        b"1,2",
    ],
)
def test_rejects_invalid_trade_collection(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="trades must be an iterable",
    ):
        BacktestEngine().evaluate(
            value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        "10",
        None,
        object(),
    ],
)
def test_rejects_non_numeric_trade(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            r"trades\[1\] "
            r"must be a real number"
        ),
    ):
        BacktestEngine().evaluate(
            [
                1.0,
                value,
            ]  # type: ignore[list-item]
        )


@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_rejects_non_finite_trade(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            r"trades\[1\] "
            r"must be finite"
        ),
    ):
        BacktestEngine().evaluate(
            [
                1.0,
                value,
            ]
        )


def test_result_is_immutable() -> None:
    result = BacktestEngine().evaluate(
        [
            1.0,
        ]
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.wins = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "field",
    [
        "total_trades",
        "wins",
        "losses",
        "breakevens",
    ],
)
def test_result_rejects_non_integer_counts(
    field: str,
) -> None:
    values: dict[str, object] = {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
        "win_rate": 0.0,
    }

    values[field] = True

    with pytest.raises(
        TypeError,
        match=rf"{field} must be an integer",
    ):
        BacktestResult(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "total_trades",
        "wins",
        "losses",
        "breakevens",
    ],
)
def test_result_rejects_negative_counts(
    field: str,
) -> None:
    values = {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
        "win_rate": 0.0,
    }

    values[field] = -1

    with pytest.raises(
        ValueError,
        match=rf"{field} must be greater",
    ):
        BacktestResult(**values)


def test_result_rejects_count_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "wins, losses, and breakevens "
            "must sum to total_trades"
        ),
    ):
        BacktestResult(
            total_trades=3,
            wins=1,
            losses=1,
            breakevens=0,
            win_rate=33.33,
            loss_rate=33.33,
        )


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    [
        (
            "win_rate",
            -0.01,
        ),
        (
            "loss_rate",
            100.01,
        ),
        (
            "breakeven_rate",
            inf,
        ),
    ],
)
def test_result_validates_percentages(
    field: str,
    value: float,
) -> None:
    values = {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
        "win_rate": 0.0,
        "loss_rate": 0.0,
        "breakeven_rate": 0.0,
    }

    values[field] = value

    with pytest.raises(ValueError):
        BacktestResult(**values)


def test_result_rejects_win_rate_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="win_rate does not match",
    ):
        BacktestResult(
            total_trades=2,
            wins=1,
            losses=1,
            win_rate=40.0,
            loss_rate=50.0,
        )


def test_result_rejects_loss_rate_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="loss_rate does not match",
    ):
        BacktestResult(
            total_trades=2,
            wins=1,
            losses=1,
            win_rate=50.0,
            loss_rate=40.0,
        )


def test_result_rejects_breakeven_rate_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="breakeven_rate does not match",
    ):
        BacktestResult(
            total_trades=2,
            wins=1,
            losses=0,
            breakevens=1,
            win_rate=50.0,
            loss_rate=0.0,
            breakeven_rate=40.0,
        )


@pytest.mark.parametrize(
    "field",
    [
        "gross_profit",
        "gross_loss",
    ],
)
def test_result_rejects_negative_gross_values(
    field: str,
) -> None:
    values = {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
    }

    values[field] = -1.0

    with pytest.raises(
        ValueError,
        match=rf"{field} must be greater",
    ):
        BacktestResult(**values)


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "error",
        "message",
    ),
    [
        (
            "gross_profit",
            "10",
            TypeError,
            "gross_profit must be a real number",
        ),
        (
            "gross_loss",
            True,
            TypeError,
            "gross_loss must be a real number",
        ),
        (
            "net_profit",
            nan,
            ValueError,
            "net_profit must be finite",
        ),
    ],
)
def test_result_validates_financial_values(
    field: str,
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    values: dict[str, object] = {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "net_profit": 0.0,
    }

    values[field] = value

    with pytest.raises(
        error,
        match=message,
    ):
        BacktestResult(
            **values,  # type: ignore[arg-type]
        )


def test_result_rejects_inconsistent_net_profit() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "net_profit must equal "
            "gross_profit minus gross_loss"
        ),
    ):
        BacktestResult(
            total_trades=1,
            wins=1,
            losses=0,
            win_rate=100.0,
            gross_profit=10.0,
            net_profit=9.0,
        )


def test_rate_rounding_preserves_existing_contract() -> None:
    result = BacktestEngine().evaluate(
        [
            120,
            -50,
            90,
            40,
            -30,
            150,
            -70,
        ]
    )

    assert result.win_rate == 57.14
    assert result.loss_rate == 42.86


def test_backward_compatible_empty_result_construction() -> None:
    result = BacktestResult(
        total_trades=0,
        wins=0,
        losses=0,
        win_rate=0.0,
    )

    assert result.breakevens == 0
    assert result.loss_rate == 0.0
    assert result.breakeven_rate == 0.0
    assert result.net_profit == 0.0
"""Tests for validated backtest statistics."""

from dataclasses import FrozenInstanceError
from math import inf, nan

import pytest

from src.ai.performance_tracker import TradePerformance
from src.backtesting.statistics_engine import (
    BacktestStatistics,
    StatisticsEngine,
)


def trade(
    pnl: float,
) -> TradePerformance:
    return TradePerformance(
        strategy="SMC",
        symbol="BTCUSDT",
        timeframe="1h",
        pnl=pnl,
        risk_reward=2.0,
        win=pnl > 0,
        confidence=80.0,
        duration_minutes=60,
    )


def empty_statistics() -> BacktestStatistics:
    return BacktestStatistics(
        total_trades=0,
        wins=0,
        losses=0,
        breakevens=0,
        win_rate=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        net_profit=0.0,
        average_win=0.0,
        average_loss=0.0,
        profit_factor=0.0,
        expectancy=0.0,
        max_drawdown=0.0,
        sharpe_ratio=0.0,
    )


def valid_statistics_values() -> dict[str, object]:
    return {
        "total_trades": 2,
        "wins": 1,
        "losses": 1,
        "breakevens": 0,
        "win_rate": 50.0,
        "gross_profit": 10.0,
        "gross_loss": 5.0,
        "net_profit": 5.0,
        "average_win": 10.0,
        "average_loss": 5.0,
        "profit_factor": 2.0,
        "expectancy": 2.5,
        "max_drawdown": 5.0,
        "sharpe_ratio": 0.0,
    }


def zero_statistics_values() -> dict[str, object]:
    return {
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "breakevens": 0,
        "win_rate": 0.0,
        "gross_profit": 0.0,
        "gross_loss": 0.0,
        "net_profit": 0.0,
        "average_win": 0.0,
        "average_loss": 0.0,
        "profit_factor": 0.0,
        "expectancy": 0.0,
        "max_drawdown": 0.0,
        "sharpe_ratio": 0.0,
    }


def test_empty_statistics() -> None:
    result = StatisticsEngine().calculate([])

    assert result == empty_statistics()

    assert result.loss_rate == 0.0
    assert result.breakeven_rate == 0.0

    assert result.profitable is False
    assert result.unprofitable is False
    assert result.flat is True


def test_calculates_complete_mixed_statistics() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(100.0),
            trade(-50.0),
            trade(80.0),
            trade(0.0),
        ]
    )

    assert result.total_trades == 4

    assert result.wins == 2
    assert result.losses == 1
    assert result.breakevens == 1

    assert result.win_rate == 50.0
    assert result.loss_rate == 25.0
    assert result.breakeven_rate == 25.0

    assert result.gross_profit == 180.0
    assert result.gross_loss == 50.0
    assert result.net_profit == 130.0

    assert result.average_win == 90.0
    assert result.average_loss == 50.0

    assert result.profit_factor == 3.6
    assert result.expectancy == 32.5
    assert result.max_drawdown == 50.0

    assert isinstance(
        result.sharpe_ratio,
        float,
    )

    assert result.profitable is True
    assert result.unprofitable is False
    assert result.flat is False


def test_classifies_zero_as_breakeven_not_loss() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(0.0),
            trade(-1.0),
            trade(1.0),
        ]
    )

    assert result.wins == 1
    assert result.losses == 1
    assert result.breakevens == 1


def test_all_wins_preserve_zero_profit_factor_contract() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(10.0),
            trade(20.0),
        ]
    )

    assert result.gross_profit == 30.0
    assert result.gross_loss == 0.0

    assert result.average_win == 15.0
    assert result.average_loss == 0.0

    assert result.profit_factor == 0.0
    assert result.profitable is True


def test_all_losses() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(-10.0),
            trade(-20.0),
        ]
    )

    assert result.gross_profit == 0.0
    assert result.gross_loss == 30.0
    assert result.net_profit == -30.0

    assert result.average_win == 0.0
    assert result.average_loss == 15.0

    assert result.profit_factor == 0.0
    assert result.unprofitable is True


def test_all_breakevens() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(0.0),
            trade(0.0),
        ]
    )

    assert result.wins == 0
    assert result.losses == 0
    assert result.breakevens == 2

    assert result.win_rate == 0.0
    assert result.loss_rate == 0.0
    assert result.breakeven_rate == 100.0

    assert result.expectancy == 0.0
    assert result.max_drawdown == 0.0
    assert result.sharpe_ratio == 0.0

    assert result.flat is True


def test_maximum_drawdown_uses_chronological_order() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(100.0),
            trade(-40.0),
            trade(-80.0),
            trade(50.0),
        ]
    )

    assert result.max_drawdown == 120.0


def test_initial_loss_counts_toward_drawdown() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(-25.0),
            trade(10.0),
        ]
    )

    assert result.max_drawdown == 25.0


def test_drawdown_recovers_after_new_peak() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(100.0),
            trade(-20.0),
            trade(50.0),
            trade(-40.0),
        ]
    )

    assert result.max_drawdown == 40.0


def test_single_trade_has_zero_sharpe() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(10.0),
        ]
    )

    assert result.sharpe_ratio == 0.0


def test_constant_pnls_have_zero_sharpe() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(10.0),
            trade(10.0),
            trade(10.0),
        ]
    )

    assert result.sharpe_ratio == 0.0


def test_sharpe_preserves_population_standard_deviation_contract() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(20.0),
            trade(10.0),
            trade(15.0),
            trade(-5.0),
            trade(30.0),
        ]
    )

    assert result.sharpe_ratio == 1.2094


def test_values_are_rounded() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(10.005),
            trade(-3.333),
            trade(1.111),
        ]
    )

    assert result.gross_profit == 11.12
    assert result.gross_loss == 3.33
    assert result.net_profit == 7.79

    assert result.average_win == 5.56
    assert result.average_loss == 3.33

    assert result.profit_factor == 3.34
    assert result.expectancy == 2.6


def test_accepts_tuple() -> None:
    result = StatisticsEngine().calculate(
        (
            trade(10.0),
            trade(-5.0),
        )
    )

    assert result.total_trades == 2
    assert result.net_profit == 5.0


def test_accepts_generator_once() -> None:
    consumed: list[int] = []

    def generate():
        for index, pnl in enumerate(
            (
                10.0,
                -5.0,
                0.0,
            )
        ):
            consumed.append(index)
            yield trade(pnl)

    result = StatisticsEngine().calculate(
        generate(),
    )

    assert consumed == [
        0,
        1,
        2,
    ]

    assert result.total_trades == 3


def test_does_not_mutate_trade_pnl() -> None:
    item = trade(
        10,  # type: ignore[arg-type]
    )

    StatisticsEngine().calculate(
        [
            item,
        ]
    )

    assert item.pnl == 10

    assert isinstance(
        item.pnl,
        int,
    )


def test_integer_pnl_is_normalized_for_calculation() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(
                10,  # type: ignore[arg-type]
            ),
            trade(
                -4,  # type: ignore[arg-type]
            ),
        ]
    )

    assert result.gross_profit == 10.0
    assert result.gross_loss == 4.0
    assert result.net_profit == 6.0

    assert isinstance(
        result.net_profit,
        float,
    )


@pytest.mark.parametrize(
    "values",
    [
        None,
        1,
        1.5,
        object(),
        "trade",
        b"trade",
    ],
)
def test_rejects_invalid_trade_collection(
    values: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "trades must be an iterable "
            "of TradePerformance instances"
        ),
    ):
        StatisticsEngine().calculate(
            values,  # type: ignore[arg-type]
        )


def test_rejects_invalid_trade_element_with_index() -> None:
    with pytest.raises(
        TypeError,
        match=(
            r"trades\[1\] must be a "
            r"TradePerformance instance"
        ),
    ):
        StatisticsEngine().calculate(
            [
                trade(1.0),
                object(),
            ]  # type: ignore[list-item]
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        "10",
        None,
        object(),
    ],
)
def test_rejects_non_numeric_pnl(
    value: object,
) -> None:
    item = trade(1.0)
    item.pnl = value  # type: ignore[assignment]

    with pytest.raises(
        TypeError,
        match=(
            r"trades\[0\]\.pnl "
            r"must be a real number"
        ),
    ):
        StatisticsEngine().calculate(
            [
                item,
            ]
        )


@pytest.mark.parametrize(
    "value",
    [
        nan,
        inf,
        -inf,
    ],
)
def test_rejects_non_finite_pnl(
    value: float,
) -> None:
    item = trade(value)

    with pytest.raises(
        ValueError,
        match=(
            r"trades\[0\]\.pnl "
            r"must be finite"
        ),
    ):
        StatisticsEngine().calculate(
            [
                item,
            ]
        )


def test_result_is_immutable() -> None:
    result = StatisticsEngine().calculate(
        [
            trade(1.0),
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
    values = zero_statistics_values()
    values[field] = True

    with pytest.raises(
        TypeError,
        match=rf"{field} must be an integer",
    ):
        BacktestStatistics(
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
    values = zero_statistics_values()
    values[field] = -1

    with pytest.raises(
        ValueError,
        match=rf"{field} must be greater",
    ):
        BacktestStatistics(
            **values,  # type: ignore[arg-type]
        )


def test_result_rejects_count_mismatch() -> None:
    values = valid_statistics_values()
    values["total_trades"] = 3

    with pytest.raises(
        ValueError,
        match=(
            "wins, losses, and breakevens "
            "must sum to total_trades"
        ),
    ):
        BacktestStatistics(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value", "error", "message"),
    [
        (
            "win_rate",
            "50",
            TypeError,
            "win_rate must be a real number",
        ),
        (
            "gross_profit",
            True,
            TypeError,
            "gross_profit must be a real number",
        ),
        (
            "gross_loss",
            nan,
            ValueError,
            "gross_loss must be finite",
        ),
        (
            "net_profit",
            inf,
            ValueError,
            "net_profit must be finite",
        ),
        (
            "average_win",
            None,
            TypeError,
            "average_win must be a real number",
        ),
        (
            "sharpe_ratio",
            -inf,
            ValueError,
            "sharpe_ratio must be finite",
        ),
    ],
)
def test_result_validates_numeric_fields(
    field: str,
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    values = zero_statistics_values()
    values[field] = value

    with pytest.raises(
        error,
        match=message,
    ):
        BacktestStatistics(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        100.01,
    ],
)
def test_result_rejects_out_of_range_win_rate(
    value: float,
) -> None:
    values = zero_statistics_values()
    values["win_rate"] = value

    with pytest.raises(
        ValueError,
        match=(
            "win_rate must be between "
            "0.0 and 100.0"
        ),
    ):
        BacktestStatistics(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "gross_profit",
        "gross_loss",
        "average_win",
        "average_loss",
        "profit_factor",
        "max_drawdown",
    ],
)
def test_result_rejects_negative_non_negative_metrics(
    field: str,
) -> None:
    values = zero_statistics_values()
    values[field] = -0.01

    with pytest.raises(
        ValueError,
        match=rf"{field} must be greater",
    ):
        BacktestStatistics(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "win_rate",
            40.0,
        ),
        (
            "net_profit",
            9.0,
        ),
        (
            "average_win",
            9.0,
        ),
        (
            "average_loss",
            4.0,
        ),
        (
            "profit_factor",
            3.0,
        ),
        (
            "expectancy",
            4.0,
        ),
    ],
)
def test_result_rejects_inconsistent_derived_metrics(
    field: str,
    value: float,
) -> None:
    values = valid_statistics_values()
    values[field] = value

    with pytest.raises(
        ValueError,
        match=rf"{field} is inconsistent",
    ):
        BacktestStatistics(
            **values,  # type: ignore[arg-type]
        )


def test_backward_compatible_construction_without_breakevens() -> None:
    result = BacktestStatistics(
        total_trades=1,
        wins=1,
        losses=0,
        win_rate=100.0,
        gross_profit=10.0,
        gross_loss=0.0,
        net_profit=10.0,
        average_win=10.0,
        average_loss=0.0,
        profit_factor=0.0,
        expectancy=10.0,
        max_drawdown=0.0,
        sharpe_ratio=0.0,
    )

    assert result.breakevens == 0


def test_result_properties_for_profitable_statistics() -> None:
    result = BacktestStatistics(
        **valid_statistics_values(),  # type: ignore[arg-type]
    )

    assert result.profitable is True
    assert result.unprofitable is False
    assert result.flat is False

    assert result.loss_rate == 50.0
    assert result.breakeven_rate == 0.0
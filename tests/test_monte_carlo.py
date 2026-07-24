"""Tests for bootstrap Monte Carlo backtest analysis."""

from dataclasses import FrozenInstanceError
from math import inf, nan
import random

import pytest

from src.ai.performance_tracker import TradePerformance
from src.backtesting.monte_carlo import (
    MonteCarloEngine,
    MonteCarloResult,
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


def zero_result_values() -> dict[str, object]:
    return {
        "simulations": 0,
        "average_profit": 0.0,
        "best_profit": 0.0,
        "worst_profit": 0.0,
        "median_profit": 0.0,
        "profit_probability": 0.0,
        "percentile_5_profit": 0.0,
        "percentile_95_profit": 0.0,
        "average_max_drawdown": 0.0,
        "worst_max_drawdown": 0.0,
    }


def valid_result_values() -> dict[str, object]:
    return {
        "simulations": 100,
        "average_profit": 10.0,
        "best_profit": 30.0,
        "worst_profit": -20.0,
        "median_profit": 8.0,
        "profit_probability": 60.0,
        "percentile_5_profit": -10.0,
        "percentile_95_profit": 25.0,
        "average_max_drawdown": 5.0,
        "worst_max_drawdown": 15.0,
    }


def test_empty_trades_return_zero_result() -> None:
    result = MonteCarloEngine().run(
        [],
        seed=7,
    )

    assert result == MonteCarloResult(
        simulations=0,
        average_profit=0.0,
        best_profit=0.0,
        worst_profit=0.0,
    )

    assert result.profit_range == 0.0
    assert result.profitable_on_average is False


def test_seeded_bootstrap_is_deterministic() -> None:
    trades = [
        trade(100.0),
        trade(-50.0),
        trade(80.0),
    ]

    first = MonteCarloEngine().run(
        trades,
        simulations=100,
        seed=7,
    )

    second = MonteCarloEngine().run(
        trades,
        simulations=100,
        seed=7,
    )

    assert first == second

    assert first == MonteCarloResult(
        simulations=100,
        average_profit=131.0,
        best_profit=300.0,
        worst_profit=-150.0,
        median_profit=130.0,
        profit_probability=75.0,
        percentile_5_profit=-20.0,
        percentile_95_profit=300.0,
        average_max_drawdown=48.0,
        worst_max_drawdown=150.0,
    )


def test_different_seeds_can_produce_different_results() -> None:
    trades = [
        trade(100.0),
        trade(-50.0),
        trade(80.0),
    ]

    first = MonteCarloEngine().run(
        trades,
        simulations=50,
        seed=1,
    )

    second = MonteCarloEngine().run(
        trades,
        simulations=50,
        seed=2,
    )

    assert first != second


def test_bootstrap_changes_total_profit_distribution() -> None:
    result = MonteCarloEngine().run(
        [
            trade(10.0),
            trade(20.0),
            trade(-5.0),
        ],
        simulations=100,
        seed=42,
    )

    assert result.average_profit == 25.15
    assert result.best_profit == 60.0
    assert result.worst_profit == -15.0
    assert result.median_profit == 25.0
    assert result.profit_probability == 86.0

    assert result.percentile_5_profit == 0.0
    assert result.percentile_95_profit == 50.0

    assert result.average_max_drawdown == 4.45
    assert result.worst_max_drawdown == 15.0

    assert result.profit_range == 75.0
    assert result.profitable_on_average is True


def test_single_trade_is_constant_across_simulations() -> None:
    result = MonteCarloEngine().run(
        [
            trade(10.0),
        ],
        simulations=10,
        seed=1,
    )

    assert result.average_profit == 10.0
    assert result.best_profit == 10.0
    assert result.worst_profit == 10.0

    assert result.median_profit == 10.0
    assert result.profit_probability == 100.0

    assert result.percentile_5_profit == 10.0
    assert result.percentile_95_profit == 10.0

    assert result.average_max_drawdown == 0.0
    assert result.worst_max_drawdown == 0.0

    assert result.profitable_on_average is True


def test_all_losing_trades_have_zero_profit_probability() -> None:
    result = MonteCarloEngine().run(
        [
            trade(-5.0),
            trade(-10.0),
        ],
        simulations=100,
        seed=2,
    )

    assert result.average_profit == -15.1
    assert result.best_profit == -10.0
    assert result.worst_profit == -20.0

    assert result.median_profit == -15.0
    assert result.profit_probability == 0.0

    assert result.percentile_5_profit == -20.0
    assert result.percentile_95_profit == -10.0

    assert result.average_max_drawdown == 15.1
    assert result.worst_max_drawdown == 20.0

    assert result.profitable_on_average is False


def test_all_breakeven_trades_return_zero_metrics() -> None:
    result = MonteCarloEngine().run(
        [
            trade(0.0),
            trade(0.0),
        ],
        simulations=20,
        seed=5,
    )

    assert result.simulations == 20

    assert result.average_profit == 0.0
    assert result.best_profit == 0.0
    assert result.worst_profit == 0.0

    assert result.median_profit == 0.0
    assert result.profit_probability == 0.0

    assert result.percentile_5_profit == 0.0
    assert result.percentile_95_profit == 0.0

    assert result.average_max_drawdown == 0.0
    assert result.worst_max_drawdown == 0.0


def test_accepts_tuple() -> None:
    result = MonteCarloEngine().run(
        (
            trade(10.0),
            trade(-5.0),
        ),
        simulations=10,
        seed=1,
    )

    assert result.simulations == 10


def test_accepts_generator_once() -> None:
    consumed: list[int] = []

    def generate():
        for index, pnl in enumerate(
            (
                10.0,
                -5.0,
                2.0,
            )
        ):
            consumed.append(index)
            yield trade(pnl)

    result = MonteCarloEngine().run(
        generate(),
        simulations=10,
        seed=1,
    )

    assert consumed == [
        0,
        1,
        2,
    ]

    assert result.simulations == 10


def test_integer_pnl_is_normalized_for_calculation() -> None:
    result = MonteCarloEngine().run(
        [
            trade(
                10,  # type: ignore[arg-type]
            ),
            trade(
                -5,  # type: ignore[arg-type]
            ),
        ],
        simulations=10,
        seed=1,
    )

    assert isinstance(
        result.average_profit,
        float,
    )

    assert isinstance(
        result.best_profit,
        float,
    )

    assert isinstance(
        result.worst_profit,
        float,
    )


def test_local_generator_does_not_mutate_global_random_state() -> None:
    random.seed(12345)
    state = random.getstate()

    MonteCarloEngine().run(
        [
            trade(10.0),
            trade(-5.0),
        ],
        simulations=10,
        seed=9,
    )

    assert random.getstate() == state


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_rejects_non_positive_simulations(
    value: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="simulations must be greater than zero",
    ):
        MonteCarloEngine().run(
            [],
            simulations=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        1.5,
        "10",
        None,
        object(),
    ],
)
def test_rejects_non_integer_simulations(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="simulations must be an integer",
    ):
        MonteCarloEngine().run(
            [],
            simulations=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        1.5,
        "7",
        object(),
    ],
)
def test_rejects_invalid_seed(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="seed must be an integer or None",
    ):
        MonteCarloEngine().run(
            [],
            seed=value,  # type: ignore[arg-type]
        )


def test_accepts_negative_integer_seed() -> None:
    result = MonteCarloEngine().run(
        [
            trade(10.0),
        ],
        simulations=2,
        seed=-10,
    )

    assert result.simulations == 2


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
        MonteCarloEngine().run(
            values,  # type: ignore[arg-type]
            simulations=10,
        )


def test_rejects_invalid_trade_element_with_index() -> None:
    with pytest.raises(
        TypeError,
        match=(
            r"trades\[1\] must be "
            r"a TradePerformance instance"
        ),
    ):
        MonteCarloEngine().run(
            [
                trade(1.0),
                object(),
            ],  # type: ignore[list-item]
            simulations=10,
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
        MonteCarloEngine().run(
            [
                item,
            ],
            simulations=10,
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
    with pytest.raises(
        ValueError,
        match=(
            r"trades\[0\]\.pnl "
            r"must be finite"
        ),
    ):
        MonteCarloEngine().run(
            [
                trade(value),
            ],
            simulations=10,
        )


def test_result_is_immutable() -> None:
    result = MonteCarloResult(
        **valid_result_values(),  # type: ignore[arg-type]
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        result.average_profit = 0.0  # type: ignore[misc]


@pytest.mark.parametrize(
    "value",
    [
        True,
        1.5,
        "10",
        None,
    ],
)
def test_result_rejects_non_integer_simulation_count(
    value: object,
) -> None:
    values = zero_result_values()
    values["simulations"] = value

    with pytest.raises(
        TypeError,
        match="simulations must be an integer",
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


def test_result_rejects_negative_simulation_count() -> None:
    values = zero_result_values()
    values["simulations"] = -1

    with pytest.raises(
        ValueError,
        match=(
            "simulations must be greater "
            "than or equal to zero"
        ),
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "average_profit",
        "best_profit",
        "worst_profit",
        "median_profit",
        "profit_probability",
        "percentile_5_profit",
        "percentile_95_profit",
        "average_max_drawdown",
        "worst_max_drawdown",
    ],
)
def test_result_rejects_non_numeric_metrics(
    field: str,
) -> None:
    values = zero_result_values()
    values[field] = "0"

    with pytest.raises(
        TypeError,
        match=rf"{field} must be a real number",
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "average_profit",
        "best_profit",
        "worst_profit",
        "median_profit",
        "profit_probability",
        "percentile_5_profit",
        "percentile_95_profit",
        "average_max_drawdown",
        "worst_max_drawdown",
    ],
)
def test_result_rejects_non_finite_metrics(
    field: str,
) -> None:
    values = zero_result_values()
    values[field] = nan

    with pytest.raises(
        ValueError,
        match=rf"{field} must be finite",
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        100.01,
    ],
)
def test_result_rejects_invalid_profit_probability(
    value: float,
) -> None:
    values = valid_result_values()
    values["profit_probability"] = value

    with pytest.raises(
        ValueError,
        match=(
            "profit_probability must be "
            "between 0.0 and 100.0"
        ),
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field",
    [
        "average_max_drawdown",
        "worst_max_drawdown",
    ],
)
def test_result_rejects_negative_drawdown(
    field: str,
) -> None:
    values = valid_result_values()
    values[field] = -0.01

    with pytest.raises(
        ValueError,
        match=(
            rf"{field} must be greater than "
            rf"or equal to zero"
        ),
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


def test_zero_simulation_result_requires_zero_metrics() -> None:
    values = zero_result_values()
    values["average_profit"] = 1.0

    with pytest.raises(
        ValueError,
        match=(
            "all metrics must be zero "
            "when simulations is zero"
        ),
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "message",
    ),
    [
        (
            "best_profit",
            5.0,
            (
                "best_profit must be greater than "
                "or equal to average_profit"
            ),
        ),
        (
            "worst_profit",
            15.0,
            (
                "average_profit must be greater than "
                "or equal to worst_profit"
            ),
        ),
        (
            "median_profit",
            31.0,
            (
                "median_profit must be between "
                "worst_profit and best_profit"
            ),
        ),
        (
            "percentile_5_profit",
            26.0,
            (
                "percentile_5_profit must be less than "
                "or equal to percentile_95_profit"
            ),
        ),
        (
            "percentile_95_profit",
            31.0,
            (
                "percentile_95_profit must be between "
                "worst_profit and best_profit"
            ),
        ),
        (
            "average_max_drawdown",
            16.0,
            (
                "average_max_drawdown must be less than "
                "or equal to worst_max_drawdown"
            ),
        ),
    ],
)
def test_result_rejects_inconsistent_metrics(
    field: str,
    value: float,
    message: str,
) -> None:
    values = valid_result_values()
    values[field] = value

    with pytest.raises(
        ValueError,
        match=message,
    ):
        MonteCarloResult(
            **values,  # type: ignore[arg-type]
        )


def test_backward_compatible_four_field_construction() -> None:
    result = MonteCarloResult(
        simulations=10,
        average_profit=10.0,
        best_profit=20.0,
        worst_profit=5.0,
    )

    assert result.median_profit == 10.0
    assert result.percentile_5_profit == 5.0
    assert result.percentile_95_profit == 20.0
    assert result.profit_probability == 100.0
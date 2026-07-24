"""Bootstrap Monte Carlo analysis for completed trade results.

Each simulation resamples the historical trade PnL values with replacement.
The sample length equals the original number of trades, producing a
distribution of possible total profits and path-dependent maximum drawdowns.

A local random-number generator is used so a supplied seed is deterministic
without mutating Python's process-wide random state.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import floor, isfinite
from numbers import Real
from random import Random

from src.ai.performance_tracker import TradePerformance


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    """Immutable aggregate result of bootstrap simulations."""

    simulations: int
    average_profit: float
    best_profit: float
    worst_profit: float
    median_profit: float = 0.0
    profit_probability: float = 0.0
    percentile_5_profit: float = 0.0
    percentile_95_profit: float = 0.0
    average_max_drawdown: float = 0.0
    worst_max_drawdown: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.simulations, bool) or not isinstance(
            self.simulations,
            int,
        ):
            raise TypeError("simulations must be an integer")

        if self.simulations < 0:
            raise ValueError(
                "simulations must be greater than or equal to zero"
            )

        average_profit = _validate_number(
            "average_profit",
            self.average_profit,
        )
        best_profit = _validate_number(
            "best_profit",
            self.best_profit,
        )
        worst_profit = _validate_number(
            "worst_profit",
            self.worst_profit,
        )
        median_profit = _validate_number(
            "median_profit",
            self.median_profit,
        )
        profit_probability = _validate_percentage(
            "profit_probability",
            self.profit_probability,
        )
        percentile_5_profit = _validate_number(
            "percentile_5_profit",
            self.percentile_5_profit,
        )
        percentile_95_profit = _validate_number(
            "percentile_95_profit",
            self.percentile_95_profit,
        )
        average_max_drawdown = _validate_non_negative_number(
            "average_max_drawdown",
            self.average_max_drawdown,
        )
        worst_max_drawdown = _validate_non_negative_number(
            "worst_max_drawdown",
            self.worst_max_drawdown,
        )

        if self.simulations == 0:
            metrics = (
                average_profit,
                best_profit,
                worst_profit,
                median_profit,
                profit_probability,
                percentile_5_profit,
                percentile_95_profit,
                average_max_drawdown,
                worst_max_drawdown,
            )

            if any(metric != 0.0 for metric in metrics):
                raise ValueError(
                    "all metrics must be zero when simulations is zero"
                )

        else:
            legacy_extended_metrics = (
                median_profit == 0.0
                and profit_probability == 0.0
                and percentile_5_profit == 0.0
                and percentile_95_profit == 0.0
                and average_max_drawdown == 0.0
                and worst_max_drawdown == 0.0
                and (
                    average_profit != 0.0
                    or best_profit != 0.0
                    or worst_profit != 0.0
                )
            )

            if legacy_extended_metrics:
                median_profit = average_profit
                percentile_5_profit = worst_profit
                percentile_95_profit = best_profit

                if worst_profit > 0.0:
                    profit_probability = 100.0

            if best_profit < average_profit:
                raise ValueError(
                    "best_profit must be greater than or equal "
                    "to average_profit"
                )

            if average_profit < worst_profit:
                raise ValueError(
                    "average_profit must be greater than or equal "
                    "to worst_profit"
                )

            if not worst_profit <= median_profit <= best_profit:
                raise ValueError(
                    "median_profit must be between "
                    "worst_profit and best_profit"
                )

            if percentile_5_profit > percentile_95_profit:
                raise ValueError(
                    "percentile_5_profit must be less than or equal to "
                    "percentile_95_profit"
                )

            if not (
                worst_profit
                <= percentile_5_profit
                <= best_profit
            ):
                raise ValueError(
                    "percentile_5_profit must be between "
                    "worst_profit and best_profit"
                )

            if not (
                worst_profit
                <= percentile_95_profit
                <= best_profit
            ):
                raise ValueError(
                    "percentile_95_profit must be between "
                    "worst_profit and best_profit"
                )

            if average_max_drawdown > worst_max_drawdown:
                raise ValueError(
                    "average_max_drawdown must be less than or equal to "
                    "worst_max_drawdown"
                )

        object.__setattr__(
            self,
            "average_profit",
            average_profit,
        )
        object.__setattr__(
            self,
            "best_profit",
            best_profit,
        )
        object.__setattr__(
            self,
            "worst_profit",
            worst_profit,
        )
        object.__setattr__(
            self,
            "median_profit",
            median_profit,
        )
        object.__setattr__(
            self,
            "profit_probability",
            profit_probability,
        )
        object.__setattr__(
            self,
            "percentile_5_profit",
            percentile_5_profit,
        )
        object.__setattr__(
            self,
            "percentile_95_profit",
            percentile_95_profit,
        )
        object.__setattr__(
            self,
            "average_max_drawdown",
            average_max_drawdown,
        )
        object.__setattr__(
            self,
            "worst_max_drawdown",
            worst_max_drawdown,
        )

    @property
    def profit_range(self) -> float:
        """Return the distance between best and worst simulated profit."""

        return _round_money(
            self.best_profit
            - self.worst_profit
        )

    @property
    def profitable_on_average(self) -> bool:
        """Return whether mean simulated total profit is positive."""

        return self.average_profit > 0.0


class MonteCarloEngine:
    """Run bootstrap simulations over completed historical trades."""

    def run(
        self,
        trades: Iterable[TradePerformance],
        simulations: int = 1000,
        *,
        seed: int | None = None,
    ) -> MonteCarloResult:
        """Return bootstrap profit and drawdown distribution statistics."""

        simulation_count = _validate_positive_integer(
            "simulations",
            simulations,
        )

        validated_seed = _validate_seed(seed)
        pnls = _normalize_pnls(trades)

        if not pnls:
            return MonteCarloResult(
                simulations=0,
                average_profit=0.0,
                best_profit=0.0,
                worst_profit=0.0,
            )

        generator = Random(validated_seed)
        sample_size = len(pnls)

        total_profits: list[float] = []
        maximum_drawdowns: list[float] = []

        for _ in range(simulation_count):
            sampled_pnls = generator.choices(
                pnls,
                k=sample_size,
            )

            total_profits.append(
                sum(sampled_pnls)
            )

            maximum_drawdowns.append(
                _maximum_drawdown(
                    sampled_pnls,
                )
            )

        ordered_profits = sorted(total_profits)

        profitable_runs = sum(
            profit > 0.0
            for profit in total_profits
        )

        return MonteCarloResult(
            simulations=simulation_count,
            average_profit=_round_money(
                sum(total_profits)
                / simulation_count
            ),
            best_profit=_round_money(
                max(total_profits)
            ),
            worst_profit=_round_money(
                min(total_profits)
            ),
            median_profit=_round_money(
                _percentile(
                    ordered_profits,
                    50.0,
                )
            ),
            profit_probability=_round_percentage(
                profitable_runs
                / simulation_count
                * 100.0
            ),
            percentile_5_profit=_round_money(
                _percentile(
                    ordered_profits,
                    5.0,
                )
            ),
            percentile_95_profit=_round_money(
                _percentile(
                    ordered_profits,
                    95.0,
                )
            ),
            average_max_drawdown=_round_money(
                sum(maximum_drawdowns)
                / simulation_count
            ),
            worst_max_drawdown=_round_money(
                max(maximum_drawdowns)
            ),
        )


def _normalize_pnls(
    values: object,
) -> tuple[float, ...]:
    if isinstance(
        values,
        (
            str,
            bytes,
            bytearray,
        ),
    ):
        raise TypeError(
            "trades must be an iterable "
            "of TradePerformance instances"
        )

    try:
        iterator = iter(
            values,  # type: ignore[arg-type]
        )
    except TypeError as exc:
        raise TypeError(
            "trades must be an iterable "
            "of TradePerformance instances"
        ) from exc

    pnls: list[float] = []

    for index, trade in enumerate(iterator):
        if not isinstance(
            trade,
            TradePerformance,
        ):
            raise TypeError(
                f"trades[{index}] must be "
                f"a TradePerformance instance"
            )

        pnls.append(
            _validate_number(
                f"trades[{index}].pnl",
                trade.pnl,
            )
        )

    return tuple(pnls)


def _maximum_drawdown(
    pnls: Iterable[float],
) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0

    for pnl in pnls:
        equity += pnl

        peak = max(
            peak,
            equity,
        )

        maximum = max(
            maximum,
            peak - equity,
        )

    return maximum


def _percentile(
    ordered_values: list[float],
    percentile: float,
) -> float:
    if len(ordered_values) == 1:
        return ordered_values[0]

    position = (
        (len(ordered_values) - 1)
        * percentile
        / 100.0
    )

    lower_index = floor(position)

    upper_index = min(
        lower_index + 1,
        len(ordered_values) - 1,
    )

    fraction = (
        position
        - lower_index
    )

    lower_value = ordered_values[
        lower_index
    ]

    upper_value = ordered_values[
        upper_index
    ]

    return (
        lower_value
        + (
            upper_value
            - lower_value
        )
        * fraction
    )


def _validate_seed(
    value: object,
) -> int | None:
    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise TypeError(
            "seed must be an integer or None"
        )

    return value


def _validate_positive_integer(
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise TypeError(
            f"{name} must be an integer"
        )

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return value


def _validate_number(
    name: str,
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            f"{name} must be a real number"
        )

    number = float(value)

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite"
        )

    return number


def _validate_non_negative_number(
    name: str,
    value: object,
) -> float:
    number = _validate_number(
        name,
        value,
    )

    if number < 0.0:
        raise ValueError(
            f"{name} must be greater than or equal to zero"
        )

    return number


def _validate_percentage(
    name: str,
    value: object,
) -> float:
    number = _validate_number(
        name,
        value,
    )

    if not 0.0 <= number <= 100.0:
        raise ValueError(
            f"{name} must be between 0.0 and 100.0"
        )

    return number


def _round_money(
    value: float,
) -> float:
    rounded = float(
        round(
            value,
            2,
        )
    )

    if rounded == 0.0:
        return 0.0

    return rounded


def _round_percentage(
    value: float,
) -> float:
    rounded = float(
        round(
            value,
            2,
        )
    )

    if rounded == 0.0:
        return 0.0

    return rounded


__all__ = [
    "MonteCarloEngine",
    "MonteCarloResult",
]
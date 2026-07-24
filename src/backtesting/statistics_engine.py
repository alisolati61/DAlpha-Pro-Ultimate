"""Validated backtest statistics for completed trades.

The engine consumes completed ``TradePerformance`` records in chronological
order. Positive PnL values are wins, negative values are losses, and zero PnL
values are breakeven trades.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isclose, isfinite, sqrt
from numbers import Real

from src.ai.performance_tracker import TradePerformance


@dataclass(frozen=True, slots=True)
class BacktestStatistics:
    """Immutable aggregate statistics for completed trades."""

    total_trades: int
    wins: int
    losses: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_profit: float
    average_win: float
    average_loss: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    sharpe_ratio: float
    breakevens: int = 0

    def __post_init__(self) -> None:
        for name in (
            "total_trades",
            "wins",
            "losses",
            "breakevens",
        ):
            value = getattr(self, name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    f"{name} must be an integer"
                )

            if value < 0:
                raise ValueError(
                    f"{name} must be greater than or equal to zero"
                )

        if (
            self.wins
            + self.losses
            + self.breakevens
            != self.total_trades
        ):
            raise ValueError(
                "wins, losses, and breakevens must sum to total_trades"
            )

        win_rate = _validate_percentage(
            "win_rate",
            self.win_rate,
        )

        gross_profit = _validate_non_negative_number(
            "gross_profit",
            self.gross_profit,
        )

        gross_loss = _validate_non_negative_number(
            "gross_loss",
            self.gross_loss,
        )

        net_profit = _validate_number(
            "net_profit",
            self.net_profit,
        )

        average_win = _validate_non_negative_number(
            "average_win",
            self.average_win,
        )

        average_loss = _validate_non_negative_number(
            "average_loss",
            self.average_loss,
        )

        profit_factor = _validate_non_negative_number(
            "profit_factor",
            self.profit_factor,
        )

        expectancy = _validate_number(
            "expectancy",
            self.expectancy,
        )

        max_drawdown = _validate_non_negative_number(
            "max_drawdown",
            self.max_drawdown,
        )

        sharpe_ratio = _validate_number(
            "sharpe_ratio",
            self.sharpe_ratio,
        )

        _require_close(
            "win_rate",
            win_rate,
            _rate(
                self.wins,
                self.total_trades,
            ),
            tolerance=0.005,
        )

        _require_close(
            "net_profit",
            net_profit,
            _round_money(
                gross_profit
                - gross_loss
            ),
        )

        _require_close(
            "average_win",
            average_win,
            _average(
                gross_profit,
                self.wins,
            ),
        )

        _require_close(
            "average_loss",
            average_loss,
            _average(
                gross_loss,
                self.losses,
            ),
        )

        _require_close(
            "profit_factor",
            profit_factor,
            _profit_factor(
                gross_profit,
                gross_loss,
            ),
        )

        _require_close(
            "expectancy",
            expectancy,
            _average(
                net_profit,
                self.total_trades,
            ),
        )

        object.__setattr__(
            self,
            "win_rate",
            win_rate,
        )

        object.__setattr__(
            self,
            "gross_profit",
            gross_profit,
        )

        object.__setattr__(
            self,
            "gross_loss",
            gross_loss,
        )

        object.__setattr__(
            self,
            "net_profit",
            net_profit,
        )

        object.__setattr__(
            self,
            "average_win",
            average_win,
        )

        object.__setattr__(
            self,
            "average_loss",
            average_loss,
        )

        object.__setattr__(
            self,
            "profit_factor",
            profit_factor,
        )

        object.__setattr__(
            self,
            "expectancy",
            expectancy,
        )

        object.__setattr__(
            self,
            "max_drawdown",
            max_drawdown,
        )

        object.__setattr__(
            self,
            "sharpe_ratio",
            sharpe_ratio,
        )

    @property
    def loss_rate(self) -> float:
        """Return losing trades as a percentage of all trades."""

        return _rate(
            self.losses,
            self.total_trades,
        )

    @property
    def breakeven_rate(self) -> float:
        """Return breakeven trades as a percentage of all trades."""

        return _rate(
            self.breakevens,
            self.total_trades,
        )

    @property
    def profitable(self) -> bool:
        return self.net_profit > 0.0

    @property
    def unprofitable(self) -> bool:
        return self.net_profit < 0.0

    @property
    def flat(self) -> bool:
        return self.net_profit == 0.0


class StatisticsEngine:
    """Calculate deterministic aggregate statistics from completed trades."""

    def calculate(
        self,
        trades: Iterable[TradePerformance],
    ) -> BacktestStatistics:
        """Calculate statistics while preserving chronological trade order."""

        pnls = _normalize_pnls(
            trades,
        )

        total = len(pnls)

        wins = tuple(
            pnl
            for pnl in pnls
            if pnl > 0.0
        )

        losses = tuple(
            pnl
            for pnl in pnls
            if pnl < 0.0
        )

        breakevens = (
            total
            - len(wins)
            - len(losses)
        )

        gross_profit = _round_money(
            sum(wins)
        )

        gross_loss = _round_money(
            -sum(losses)
        )

        net_profit = _round_money(
            gross_profit
            - gross_loss
        )

        return BacktestStatistics(
            total_trades=total,
            wins=len(wins),
            losses=len(losses),
            breakevens=breakevens,
            win_rate=_rate(
                len(wins),
                total,
            ),
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=net_profit,
            average_win=_average(
                gross_profit,
                len(wins),
            ),
            average_loss=_average(
                gross_loss,
                len(losses),
            ),
            profit_factor=_profit_factor(
                gross_profit,
                gross_loss,
            ),
            expectancy=_average(
                net_profit,
                total,
            ),
            max_drawdown=_maximum_drawdown(
                pnls,
            ),
            sharpe_ratio=_sharpe_ratio(
                pnls,
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
            "trades must be an iterable of TradePerformance instances"
        )

    try:
        iterator = iter(
            values,  # type: ignore[arg-type]
        )
    except TypeError as exc:
        raise TypeError(
            "trades must be an iterable of TradePerformance instances"
        ) from exc

    pnls: list[float] = []

    for index, trade in enumerate(iterator):
        if not isinstance(
            trade,
            TradePerformance,
        ):
            raise TypeError(
                f"trades[{index}] must be a TradePerformance instance"
            )

        pnls.append(
            _validate_number(
                f"trades[{index}].pnl",
                trade.pnl,
            )
        )

    return tuple(pnls)


def _maximum_drawdown(
    pnls: tuple[float, ...],
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

    return _round_money(
        maximum,
    )


def _sharpe_ratio(
    pnls: tuple[float, ...],
) -> float:
    if len(pnls) < 2:
        return 0.0

    mean = (
        sum(pnls)
        / len(pnls)
    )

    variance = (
        sum(
            (pnl - mean) ** 2
            for pnl in pnls
        )
        / len(pnls)
    )

    standard_deviation = sqrt(
        variance,
    )

    if standard_deviation == 0.0:
        return 0.0

    return _round_ratio(
        mean
        / standard_deviation,
        decimals=4,
    )


def _profit_factor(
    gross_profit: float,
    gross_loss: float,
) -> float:
    if gross_loss == 0.0:
        return 0.0

    return _round_ratio(
        gross_profit
        / gross_loss,
    )


def _average(
    total: float,
    count: int,
) -> float:
    if count == 0:
        return 0.0

    return _round_money(
        total
        / count,
    )


def _rate(
    count: int,
    total: int,
) -> float:
    if total == 0:
        return 0.0

    return _round_ratio(
        count
        / total
        * 100.0,
    )


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


def _require_close(
    name: str,
    actual: float,
    expected: float,
    *,
    tolerance: float = 1e-9,
) -> None:
    if not isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        raise ValueError(
            f"{name} is inconsistent with aggregate values"
        )


def _round_money(
    value: float,
) -> float:
    return _normalize_zero(
        round(
            float(value),
            2,
        )
    )


def _round_ratio(
    value: float,
    *,
    decimals: int = 2,
) -> float:
    return _normalize_zero(
        round(
            float(value),
            decimals,
        )
    )


def _normalize_zero(
    value: float,
) -> float:
    if value == 0.0:
        return 0.0

    return value


__all__ = [
    "BacktestStatistics",
    "StatisticsEngine",
]
"""Validated aggregation of realized trade profit and loss values.

The engine accepts one realized PnL value per closed trade. Positive values
are wins, negative values are losses, and zero values are breakeven trades.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isclose, isfinite
from numbers import Real


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Immutable aggregate result for a sequence of closed trades."""

    total_trades: int
    wins: int
    losses: int
    win_rate: float
    breakevens: int = 0
    loss_rate: float = 0.0
    breakeven_rate: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0

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

        loss_rate = _validate_percentage(
            "loss_rate",
            self.loss_rate,
        )

        breakeven_rate = _validate_percentage(
            "breakeven_rate",
            self.breakeven_rate,
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

        expected_win_rate = _rate(
            self.wins,
            self.total_trades,
        )

        expected_loss_rate = _rate(
            self.losses,
            self.total_trades,
        )

        expected_breakeven_rate = _rate(
            self.breakevens,
            self.total_trades,
        )

        if not isclose(
            win_rate,
            expected_win_rate,
            abs_tol=0.005,
        ):
            raise ValueError(
                "win_rate does not match wins and total_trades"
            )

        if not isclose(
            loss_rate,
            expected_loss_rate,
            abs_tol=0.005,
        ):
            raise ValueError(
                "loss_rate does not match losses and total_trades"
            )

        if not isclose(
            breakeven_rate,
            expected_breakeven_rate,
            abs_tol=0.005,
        ):
            raise ValueError(
                "breakeven_rate does not match "
                "breakevens and total_trades"
            )

        if not isclose(
            net_profit,
            gross_profit - gross_loss,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError(
                "net_profit must equal gross_profit minus gross_loss"
            )

        object.__setattr__(
            self,
            "win_rate",
            win_rate,
        )

        object.__setattr__(
            self,
            "loss_rate",
            loss_rate,
        )

        object.__setattr__(
            self,
            "breakeven_rate",
            breakeven_rate,
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

    @property
    def profitable(self) -> bool:
        """Return whether aggregate realized PnL is positive."""

        return self.net_profit > 0.0

    @property
    def unprofitable(self) -> bool:
        """Return whether aggregate realized PnL is negative."""

        return self.net_profit < 0.0

    @property
    def flat(self) -> bool:
        """Return whether aggregate realized PnL is zero."""

        return self.net_profit == 0.0


class BacktestEngine:
    """Aggregate validated realized PnL values."""

    def evaluate(
        self,
        trades: Iterable[Real],
    ) -> BacktestResult:
        """Evaluate one realized PnL value per closed trade."""

        normalized_trades = _normalize_trades(
            trades,
        )

        total = len(normalized_trades)

        wins = sum(
            trade > 0.0
            for trade in normalized_trades
        )

        losses = sum(
            trade < 0.0
            for trade in normalized_trades
        )

        breakevens = (
            total
            - wins
            - losses
        )

        gross_profit = sum(
            trade
            for trade in normalized_trades
            if trade > 0.0
        )

        gross_loss = -sum(
            trade
            for trade in normalized_trades
            if trade < 0.0
        )

        return BacktestResult(
            total_trades=total,
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            win_rate=_rate(
                wins,
                total,
            ),
            loss_rate=_rate(
                losses,
                total,
            ),
            breakeven_rate=_rate(
                breakevens,
                total,
            ),
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=(
                gross_profit
                - gross_loss
            ),
        )


def _normalize_trades(
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
            "trades must be an iterable of real numbers"
        )

    try:
        iterator = iter(
            values,  # type: ignore[arg-type]
        )
    except TypeError as exc:
        raise TypeError(
            "trades must be an iterable of real numbers"
        ) from exc

    return tuple(
        _validate_number(
            f"trades[{index}]",
            value,
        )
        for index, value in enumerate(iterator)
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


def _rate(
    count: int,
    total: int,
) -> float:
    if total == 0:
        return 0.0

    return round(
        count / total * 100.0,
        2,
    )


__all__ = [
    "BacktestEngine",
    "BacktestResult",
]
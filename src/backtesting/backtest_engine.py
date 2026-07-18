from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class BacktestResult:
    total_trades: int
    wins: int
    losses: int
    win_rate: float


class BacktestEngine:
    """
    Basic backtesting result evaluator.

    Receives a sequence of trade PnL values and returns
    aggregate performance statistics.
    """

    def evaluate(
        self,
        trades: Iterable[float],
    ) -> BacktestResult:

        trades = list(trades)

        total = len(trades)

        wins = sum(
            1
            for trade in trades
            if trade > 0
        )

        losses = sum(
            1
            for trade in trades
            if trade <= 0
        )

        win_rate = (
            wins / total * 100
            if total
            else 0.0
        )

        return BacktestResult(
            total_trades=total,
            wins=wins,
            losses=losses,
            win_rate=round(
                win_rate,
                2,
            ),
        )
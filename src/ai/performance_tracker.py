from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import mean
from typing import Dict, List


@dataclass(slots=True)
class TradePerformance:
    """
    Represents the outcome of a completed trade.
    """

    strategy: str
    symbol: str
    timeframe: str

    pnl: float
    risk_reward: float

    win: bool

    confidence: float

    duration_minutes: int

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )


class PerformanceTracker:
    """
    Tracks historical trading performance.

    Future versions:

    - AI Learning
    - Weight Optimizer
    - Strategy Ranking
    - Market Regime Statistics
    """

    def __init__(self) -> None:

        self._history: List[TradePerformance] = []

    # --------------------------------------------------

    def add(
        self,
        trade: TradePerformance,
    ) -> None:

        self._history.append(trade)

    # --------------------------------------------------

    @property
    def trades(self) -> int:

        return len(self._history)

    # --------------------------------------------------

    @property
    def wins(self) -> int:

        return sum(
            trade.win
            for trade in self._history
        )

    # --------------------------------------------------

    @property
    def losses(self) -> int:

        return self.trades - self.wins

    # --------------------------------------------------

    @property
    def win_rate(self) -> float:

        if self.trades == 0:
            return 0.0

        return round(
            (self.wins / self.trades) * 100,
            2,
        )

    # --------------------------------------------------

    @property
    def total_profit(self) -> float:

        return round(
            sum(
                trade.pnl
                for trade in self._history
            ),
            2,
        )

    # --------------------------------------------------

    @property
    def average_profit(self) -> float:

        if not self._history:
            return 0.0

        return round(
            mean(
                trade.pnl
                for trade in self._history
            ),
            2,
        )

    # --------------------------------------------------

    @property
    def average_rr(self) -> float:

        if not self._history:
            return 0.0

        return round(
            mean(
                trade.risk_reward
                for trade in self._history
            ),
            2,
        )

    # --------------------------------------------------

    @property
    def average_confidence(self) -> float:

        if not self._history:
            return 0.0

        return round(
            mean(
                trade.confidence
                for trade in self._history
            ),
            2,
        )

    # --------------------------------------------------

    def by_strategy(
        self,
        strategy: str,
    ) -> List[TradePerformance]:

        return [
            trade
            for trade in self._history
            if trade.strategy == strategy
        ]

    # --------------------------------------------------

    def by_symbol(
        self,
        symbol: str,
    ) -> List[TradePerformance]:

        return [
            trade
            for trade in self._history
            if trade.symbol == symbol
        ]

    # --------------------------------------------------

    def summary(self) -> Dict[str, float]:

        return {
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "total_profit": self.total_profit,
            "average_profit": self.average_profit,
            "average_rr": self.average_rr,
            "average_confidence": self.average_confidence,
        }

    # --------------------------------------------------

    def clear(self) -> None:

        self._history.clear()
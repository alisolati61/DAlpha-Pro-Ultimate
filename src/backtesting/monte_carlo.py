from __future__ import annotations

import random
from dataclasses import dataclass

from src.ai.performance_tracker import TradePerformance


@dataclass(slots=True)
class MonteCarloResult:
    simulations: int
    average_profit: float
    best_profit: float
    worst_profit: float


class MonteCarloEngine:
    """
    Monte Carlo simulation for strategy robustness.

    Future
    -------
    - Confidence Intervals
    - Equity Curve Distribution
    - VaR Estimation
    """

    def run(
        self,
        trades: list[TradePerformance],
        simulations: int = 1000,
    ) -> MonteCarloResult:

        if not trades:

            return MonteCarloResult(
                simulations=0,
                average_profit=0.0,
                best_profit=0.0,
                worst_profit=0.0,
            )

        profits: list[float] = []

        pnls = [trade.pnl for trade in trades]

        for _ in range(simulations):

            shuffled = random.sample(
                pnls,
                len(pnls),
            )

            profits.append(float(sum(shuffled)))

        return MonteCarloResult(
            simulations=simulations,
            average_profit=float(round(sum(profits) / len(profits), 2)),
            best_profit=float(round(max(profits), 2)),
            worst_profit=float(round(min(profits), 2)),
        )
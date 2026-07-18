from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from src.ai.performance_tracker import TradePerformance


@dataclass(slots=True)
class BacktestStatistics:

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


class StatisticsEngine:
    """
    Produces professional backtest statistics.

    Future:
        - Sortino Ratio
        - Calmar Ratio
        - Recovery Factor
        - Ulcer Index
        - CAGR
    """

    def calculate(
        self,
        trades: list[TradePerformance],
    ) -> BacktestStatistics:

        total = len(trades)

        if total == 0:

            return BacktestStatistics(
                total_trades=0,
                wins=0,
                losses=0,
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

        wins = [t.pnl for t in trades if t.pnl > 0]

        losses = [t.pnl for t in trades if t.pnl <= 0]

        gross_profit = float(sum(wins))

        gross_loss = abs(float(sum(losses)))

        net_profit = gross_profit - gross_loss

        win_rate = (len(wins) / total) * 100

        average_win = gross_profit / len(wins) if wins else 0.0

        average_loss = (
            gross_loss / len(losses)
            if losses
            else 0.0
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0.0
        )

        expectancy = net_profit / total

        equity = 0.0
        peak = 0.0
        max_dd = 0.0

        returns = []

        for trade in trades:

            equity += trade.pnl

            returns.append(trade.pnl)

            if equity > peak:
                peak = equity

            dd = peak - equity

            if dd > max_dd:
                max_dd = dd

        if len(returns) > 1:

            mean = sum(returns) / len(returns)

            variance = sum(
                (r - mean) ** 2
                for r in returns
            ) / len(returns)

            std = sqrt(variance)

            sharpe = (
                mean / std
                if std > 0
                else 0.0
            )

        else:

            sharpe = 0.0

        return BacktestStatistics(

            total_trades=total,

            wins=len(wins),

            losses=len(losses),

            win_rate=float(round(win_rate, 2)),

            gross_profit=float(round(gross_profit, 2)),

            gross_loss=float(round(gross_loss, 2)),

            net_profit=float(round(net_profit, 2)),

            average_win=float(round(average_win, 2)),

            average_loss=float(round(average_loss, 2)),

            profit_factor=float(round(profit_factor, 2)),

            expectancy=float(round(expectancy, 2)),

            max_drawdown=float(round(max_dd, 2)),

            sharpe_ratio=float(round(sharpe, 4)),
        )
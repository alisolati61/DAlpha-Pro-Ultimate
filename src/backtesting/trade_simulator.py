from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TradeRequest:
    """
    Input required to simulate one trade.
    """

    entry_price: float
    exit_price: float
    quantity: float

    commission: float = 0.0004
    slippage: float = 0.0002


@dataclass(slots=True)
class TradeSimulationResult:
    """
    Result of one simulated trade.
    """

    gross_profit: float
    commission_paid: float
    slippage_cost: float
    net_profit: float
    return_percent: float


class TradeSimulator:
    """
    Simulates one historical trade.

    Responsibilities
    ----------------
    - Gross PnL
    - Commission
    - Slippage
    - Net Profit

    Future
    -------
    - Funding Fee
    - Partial Close
    - Scale In / Scale Out
    """

    def simulate(
        self,
        trade: TradeRequest,
    ) -> TradeSimulationResult:

        gross_profit = float(
            (trade.exit_price - trade.entry_price)
            * trade.quantity
        )

        turnover = float(
            (trade.entry_price + trade.exit_price)
            * trade.quantity
        )

        commission_paid = float(
            turnover * trade.commission
        )

        slippage_cost = float(
            turnover * trade.slippage
        )

        net_profit = float(
            gross_profit
            - commission_paid
            - slippage_cost
        )

        invested = float(
            trade.entry_price
            * trade.quantity
        )

        if invested == 0.0:

            return_percent = 0.0

        else:

            return_percent = float(
                (net_profit / invested)
                * 100
            )

        return TradeSimulationResult(
            gross_profit=float(round(gross_profit, 2)),
            commission_paid=float(round(commission_paid, 2)),
            slippage_cost=float(round(slippage_cost, 2)),
            net_profit=float(round(net_profit, 2)),
            return_percent=float(round(return_percent, 2)),
        )
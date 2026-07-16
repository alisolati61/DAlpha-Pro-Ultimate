from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PortfolioState:
    balance: float
    equity: float
    used_margin: float
    open_positions: int
    daily_loss: float
    total_risk: float


class PortfolioGuard:
    """
    Portfolio-level risk controller.

    Controls:
    - Maximum open positions
    - Maximum portfolio risk
    - Daily loss limit
    - Margin usage
    """

    def __init__(
        self,
        max_positions: int = 5,
        max_portfolio_risk: float = 0.05,
        max_daily_loss: float = 0.03,
        max_margin_usage: float = 0.80,
    ) -> None:

        self.max_positions = max_positions
        self.max_portfolio_risk = max_portfolio_risk
        self.max_daily_loss = max_daily_loss
        self.max_margin_usage = max_margin_usage

    def validate(self, state: PortfolioState) -> bool:

        if state.open_positions >= self.max_positions:
            return False

        if state.total_risk > self.max_portfolio_risk:
            return False

        if state.daily_loss > self.max_daily_loss:
            return False

        if state.balance <= 0:
            return False

        margin_usage = state.used_margin / state.balance

        if margin_usage > self.max_margin_usage:
            return False

        return True
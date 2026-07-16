from __future__ import annotations

from src.risk.circuit_breaker import CircuitBreaker
from src.risk.drawdown_guard import DrawdownGuard
from src.risk.kill_switch import KillSwitch
from src.risk.portfolio_guard import (
    PortfolioGuard,
    PortfolioState,
)
from src.risk.pre_trade_validator import (
    PreTradeValidator,
)


class RiskOrchestrator:
    """
    Main coordinator of the entire Risk Engine.
    Every order must pass through this class.
    """

    def __init__(
        self,
        kill_switch: KillSwitch,
        circuit_breaker: CircuitBreaker,
        drawdown_guard: DrawdownGuard,
        portfolio_guard: PortfolioGuard,
        pre_trade_validator: PreTradeValidator,
    ) -> None:

        self.kill_switch = kill_switch
        self.circuit_breaker = circuit_breaker
        self.drawdown_guard = drawdown_guard
        self.portfolio_guard = portfolio_guard
        self.pre_trade_validator = pre_trade_validator

    def validate_trade(
        self,
        *,
        portfolio: PortfolioState,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> bool:

        # Emergency Stop
        if self.kill_switch.active:
            return False

        # Circuit Breaker
        if not self.circuit_breaker.can_trade():
            return False

        # Portfolio Rules
        if not self.portfolio_guard.validate(portfolio):
            return False

        # Position Rules
        result = self.pre_trade_validator.validate(
            position_size=position_size,
            leverage=leverage,
            entry_price=entry_price,
            stop_loss=stop_loss,
        )

        if not result.approved:
            return False

        return True
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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


class RiskDecision(str, Enum):
    APPROVED = "APPROVED"
    KILL_SWITCH = "KILL_SWITCH"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    PORTFOLIO_REJECTED = "PORTFOLIO_REJECTED"
    TRADE_REJECTED = "TRADE_REJECTED"


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    approved: bool
    decision: RiskDecision
    reason: str = ""


class RiskOrchestrator:
    """
    Central coordinator of the Risk Engine.

    Every order must pass through this class before execution.

    Validation order is deterministic:

    1. Kill Switch
    2. Circuit Breaker
    3. Portfolio-level rules
    4. Position-level rules
    """

    def __init__(
        self,
        kill_switch: KillSwitch,
        circuit_breaker: CircuitBreaker,
        drawdown_guard: DrawdownGuard,
        portfolio_guard: PortfolioGuard,
        pre_trade_validator: PreTradeValidator,
    ) -> None:

        if not isinstance(
            kill_switch,
            KillSwitch,
        ):

            raise TypeError(
                "kill_switch must be a KillSwitch."
            )

        if not isinstance(
            circuit_breaker,
            CircuitBreaker,
        ):

            raise TypeError(
                "circuit_breaker must be a CircuitBreaker."
            )

        if not isinstance(
            drawdown_guard,
            DrawdownGuard,
        ):

            raise TypeError(
                "drawdown_guard must be a DrawdownGuard."
            )

        if not isinstance(
            portfolio_guard,
            PortfolioGuard,
        ):

            raise TypeError(
                "portfolio_guard must be a PortfolioGuard."
            )

        if not isinstance(
            pre_trade_validator,
            PreTradeValidator,
        ):

            raise TypeError(
                "pre_trade_validator must be a PreTradeValidator."
            )

        self.kill_switch = kill_switch
        self.circuit_breaker = circuit_breaker
        self.drawdown_guard = drawdown_guard
        self.portfolio_guard = portfolio_guard
        self.pre_trade_validator = pre_trade_validator

    # --------------------------------------------------

    def evaluate_trade(
        self,
        *,
        portfolio: PortfolioState,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> RiskEvaluation:

        if not isinstance(
            portfolio,
            PortfolioState,
        ):

            raise TypeError(
                "portfolio must be a PortfolioState."
            )

        # 1. Emergency stop
        if self.kill_switch.active:

            return RiskEvaluation(
                approved=False,
                decision=RiskDecision.KILL_SWITCH,
                reason=(
                    self.kill_switch.reason
                    or "Kill switch is active."
                ),
            )

        # 2. Circuit breaker
        if not self.circuit_breaker.can_trade():

            return RiskEvaluation(
                approved=False,
                decision=RiskDecision.CIRCUIT_BREAKER,
                reason=(
                    "Circuit breaker is active."
                ),
            )

        # 3. Portfolio rules
        if not self.portfolio_guard.validate(
            portfolio
        ):

            return RiskEvaluation(
                approved=False,
                decision=RiskDecision.PORTFOLIO_REJECTED,
                reason=(
                    "Portfolio risk rules rejected the trade."
                ),
            )

        # 4. Position rules
        result = self.pre_trade_validator.validate(
            position_size=position_size,
            leverage=leverage,
            entry_price=entry_price,
            stop_loss=stop_loss,
        )

        if not result.approved:

            return RiskEvaluation(
                approved=False,
                decision=RiskDecision.TRADE_REJECTED,
                reason=(
                    result.reason
                    or "Pre-trade validation failed."
                ),
            )

        return RiskEvaluation(
            approved=True,
            decision=RiskDecision.APPROVED,
        )

    # --------------------------------------------------

    def validate_trade(
        self,
        *,
        portfolio: PortfolioState,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> bool:

        return self.evaluate_trade(
            portfolio=portfolio,
            position_size=position_size,
            leverage=leverage,
            entry_price=entry_price,
            stop_loss=stop_loss,
        ).approved
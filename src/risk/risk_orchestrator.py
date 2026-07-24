"""Central orchestration for pre-execution risk controls.

Every new order must pass through this coordinator before execution.
Validation order is deterministic and fail-closed:

1. Kill switch
2. Circuit breaker
3. Portfolio-level rules
4. Balance-to-equity drawdown
5. Position-level pre-trade rules

The drawdown check treats ``PortfolioState.balance`` as the reference balance
and ``PortfolioState.equity`` as the current account value. Historical
high-water-mark drawdown remains the responsibility of ``RiskManager``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real

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

_MAX_REASON_LENGTH = 500


class RiskDecision(str, Enum):
    """Possible pre-execution risk decisions."""

    APPROVED = "APPROVED"
    KILL_SWITCH = "KILL_SWITCH"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    PORTFOLIO_REJECTED = "PORTFOLIO_REJECTED"
    DRAWDOWN_REJECTED = "DRAWDOWN_REJECTED"
    TRADE_REJECTED = "TRADE_REJECTED"


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    """Immutable result of one orchestrated risk evaluation."""

    approved: bool
    decision: RiskDecision
    reason: str = ""
    drawdown: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.approved, bool):
            raise TypeError(
                "approved must be a bool"
            )

        if not isinstance(
            self.decision,
            RiskDecision,
        ):
            raise TypeError(
                "decision must be a RiskDecision"
            )

        if not isinstance(self.reason, str):
            raise TypeError(
                "reason must be a string"
            )

        reason = self.reason.strip()

        if len(reason) > _MAX_REASON_LENGTH:
            raise ValueError(
                "reason must not exceed "
                f"{_MAX_REASON_LENGTH} characters"
            )

        if self.decision is RiskDecision.APPROVED:
            if not self.approved:
                raise ValueError(
                    "APPROVED decision must be approved"
                )

            if reason:
                raise ValueError(
                    "APPROVED decision must not have a reason"
                )
        else:
            if self.approved:
                raise ValueError(
                    "rejection decision cannot be approved"
                )

            if not reason:
                raise ValueError(
                    "rejection decision requires a reason"
                )

        drawdown = self.drawdown

        if drawdown is not None:
            drawdown = _validate_unit_interval(
                drawdown,
                "drawdown",
            )

        object.__setattr__(
            self,
            "reason",
            reason,
        )
        object.__setattr__(
            self,
            "drawdown",
            drawdown,
        )

    @property
    def rejected(self) -> bool:
        """Return whether risk controls rejected the trade."""

        return not self.approved


class RiskOrchestrator:
    """Coordinate all pre-execution risk gates."""

    KILL_SWITCH_FALLBACK_REASON = (
        "Kill switch is active."
    )
    CIRCUIT_BREAKER_FALLBACK_REASON = (
        "Circuit breaker is active."
    )
    CIRCUIT_BREAKER_ERROR_REASON = (
        "Circuit breaker state could not be evaluated."
    )
    PORTFOLIO_FALLBACK_REASON = (
        "Portfolio risk rules rejected the trade."
    )
    DRAWDOWN_REASON = (
        "Maximum drawdown reached or exceeded."
    )
    DRAWDOWN_ERROR_REASON = (
        "Drawdown state could not be evaluated."
    )
    TRADE_FALLBACK_REASON = (
        "Pre-trade validation failed."
    )

    __slots__ = (
        "circuit_breaker",
        "drawdown_guard",
        "kill_switch",
        "portfolio_guard",
        "pre_trade_validator",
    )

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
                "pre_trade_validator must be a "
                "PreTradeValidator."
            )

        self.kill_switch = kill_switch
        self.circuit_breaker = circuit_breaker
        self.drawdown_guard = drawdown_guard
        self.portfolio_guard = portfolio_guard
        self.pre_trade_validator = (
            pre_trade_validator
        )

    def evaluate_trade(
        self,
        *,
        portfolio: PortfolioState,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> RiskEvaluation:
        """Evaluate a new trade in deterministic risk-gate order."""

        if self.kill_switch.active:
            return RiskEvaluation(
                approved=False,
                decision=RiskDecision.KILL_SWITCH,
                reason=(
                    self.kill_switch.reason
                    or self.KILL_SWITCH_FALLBACK_REASON
                ),
            )

        try:
            circuit_allows_trade = (
                self.circuit_breaker.can_trade()
            )
        except (TypeError, ValueError):
            return RiskEvaluation(
                approved=False,
                decision=(
                    RiskDecision.CIRCUIT_BREAKER
                ),
                reason=(
                    self.CIRCUIT_BREAKER_ERROR_REASON
                ),
            )

        if not circuit_allows_trade:
            return RiskEvaluation(
                approved=False,
                decision=(
                    RiskDecision.CIRCUIT_BREAKER
                ),
                reason=(
                    self.circuit_breaker.reason
                    or (
                        self
                        .CIRCUIT_BREAKER_FALLBACK_REASON
                    )
                ),
            )

        if not isinstance(
            portfolio,
            PortfolioState,
        ):
            raise TypeError(
                "portfolio must be a PortfolioState."
            )

        portfolio_result = (
            self.portfolio_guard.evaluate(
                portfolio
            )
        )

        if not portfolio_result.approved:
            return RiskEvaluation(
                approved=False,
                decision=(
                    RiskDecision.PORTFOLIO_REJECTED
                ),
                reason=(
                    portfolio_result.reason
                    or self.PORTFOLIO_FALLBACK_REASON
                ),
            )

        try:
            drawdown_status = (
                self.drawdown_guard.check(
                    peak_balance=portfolio.balance,
                    current_balance=portfolio.equity,
                )
            )
        except (TypeError, ValueError):
            return RiskEvaluation(
                approved=False,
                decision=(
                    RiskDecision.DRAWDOWN_REJECTED
                ),
                reason=self.DRAWDOWN_ERROR_REASON,
            )

        if not drawdown_status.allowed:
            return RiskEvaluation(
                approved=False,
                decision=(
                    RiskDecision.DRAWDOWN_REJECTED
                ),
                reason=self.DRAWDOWN_REASON,
                drawdown=drawdown_status.drawdown,
            )

        trade_result = (
            self.pre_trade_validator.validate(
                position_size=position_size,
                leverage=leverage,
                entry_price=entry_price,
                stop_loss=stop_loss,
            )
        )

        if not trade_result.approved:
            return RiskEvaluation(
                approved=False,
                decision=RiskDecision.TRADE_REJECTED,
                reason=(
                    trade_result.reason
                    or self.TRADE_FALLBACK_REASON
                ),
                drawdown=drawdown_status.drawdown,
            )

        return RiskEvaluation(
            approved=True,
            decision=RiskDecision.APPROVED,
            drawdown=drawdown_status.drawdown,
        )

    def validate_trade(
        self,
        *,
        portfolio: PortfolioState,
        position_size: float,
        leverage: float,
        entry_price: float,
        stop_loss: float,
    ) -> bool:
        """Return whether all risk gates approve the trade."""

        return self.evaluate_trade(
            portfolio=portfolio,
            position_size=position_size,
            leverage=leverage,
            entry_price=entry_price,
            stop_loss=stop_loss,
        ).approved


def _validate_unit_interval(
    value: object,
    name: str,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, Real)
    ):
        raise TypeError(
            f"{name} must be a number"
        )

    number = float(value)

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite"
        )

    if not 0.0 <= number <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1"
        )

    return number


__all__ = (
    "RiskDecision",
    "RiskEvaluation",
    "RiskOrchestrator",
)